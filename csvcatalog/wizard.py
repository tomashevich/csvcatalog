import os

from tabulate import tabulate

from .storage import Storage
from .termutils import err_print, select_options


class ExtractionWizard:
    """a step-by-step wizard to guide the user through data extraction"""

    def __init__(self, storage: Storage, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"file not found: '{file_path}'")
        if os.path.isdir(file_path):
            raise IsADirectoryError(f"not a file: '{file_path}'")

        self.storage = storage
        self.file_path = file_path

        # configuration state
        self.separator: str = ","
        self.csv_headers: list[str] = []
        self.column_map: dict[str, str] = {}
        self.columns: list[str] = []
        self.table_name: str = os.path.splitext(os.path.basename(file_path))[0].strip()

    def run(self) -> None:
        """runs the entire extraction wizard workflow"""
        print(f"starting extraction for '{self.file_path}'")
        if not self._step_initial_preview():
            return
        if not self._step_set_separator():
            return
        if not self._step_define_columns():
            return
        if not self._step_select_columns_to_import():
            return
        if not self._step_set_table_name():
            return
        if not self._step_preview_data():
            return
        if not self._step_confirm_and_run():
            return
        print("extraction finished")

    def _read_raw_lines(self, count: int) -> list[str]:
        """reads a number of raw lines from the source file"""
        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            lines = [line.strip() for i, line in enumerate(f) if i < count]
        return lines

    def _read_lines(self, count: int) -> list[list[str]]:
        """reads a number of lines from the source file and splits them"""
        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            lines = [
                line.strip().split(self.separator)
                for i, line in enumerate(f)
                if i < count and line.strip()
            ]
        return lines

    def _step_initial_preview(self) -> bool:
        """shows an initial raw preview of the file"""
        print("\nraw preview:")
        try:
            raw_lines = self._read_raw_lines(5)
            if not raw_lines:
                err_print("file appears to be empty")
                return False
            for line in raw_lines:
                print(line)
        except Exception as e:
            err_print(f"could not read file: {e}")
            return False
        print("\n")
        return True

    def _step_set_separator(self) -> bool:
        """asks the user to define the csv separator"""
        prompt = "enter csv separator (or 'q' to quit) [default: ',']: "
        user_input = input(prompt).strip()
        if user_input.lower() == "q":
            err_print("aborted")
            return False
        if user_input:
            self.separator = user_input
        print(f"using separator: '{self.separator}'")
        return True

    def _step_define_columns(self) -> bool:
        """asks the user to map csv headers to database column names"""
        try:
            preview = self._read_lines(1)
            if not preview:
                err_print("file is empty")
                return False
            self.csv_headers = preview[0]
        except Exception as e:
            err_print(f"could not read file: {e}")
            return False

        print("\nplease define database column names for each csv header")
        print("press enter to accept the default name")

        temp_column_map = {}
        for header in self.csv_headers:
            prompt = f"  csv header '{header}' -> column name [default: {header}]: "
            user_input = input(prompt).strip()
            if user_input.lower() == "q":
                err_print("aborted")
                return False

            column_name = user_input if user_input else header
            temp_column_map[header] = column_name

        self.column_map = temp_column_map
        print("column mapping complete")
        return True

    def _step_select_columns_to_import(self) -> bool:
        """allows user to select a subset of columns to import"""
        columns = list(self.column_map.values())
        print("\nselect the columns you want to import")

        chosen_columns = select_options(
            columns,
            title="use [space] to toggle columns and [enter] to confirm",
            default_selected=True,
        )

        if not chosen_columns:
            err_print("no columns selected, aborting")
            return False

        self.columns = chosen_columns
        print(f"selected columns: {', '.join(self.columns)}")
        return True

    def _step_set_table_name(self) -> bool:
        """confirms the target database table name"""
        prompt = f"\nenter table name (or 'q' to quit) [default: '{self.table_name}']: "
        user_input = input(prompt).strip()

        if user_input.lower() == "q":
            err_print("aborted")
            return False
        if user_input:
            self.table_name = user_input
        print(f"target table will be: '{self.table_name}'")
        return True

    def _step_preview_data(self) -> bool:
        """shows a preview of the data based on final selected columns"""
        try:
            lines = self._read_lines(6)
            if len(lines) < 2:
                print("not enough lines to preview")
                return True

            header_to_idx = {header: i for i, header in enumerate(self.csv_headers)}

            data_to_preview = []
            for line in lines[1:]:
                row_data = {}
                for csv_header, column_name in self.column_map.items():
                    if column_name in self.columns:
                        idx = header_to_idx.get(csv_header)
                        if idx is not None and idx < len(line):
                            row_data[column_name] = line[idx]
                if row_data:
                    data_to_preview.append(row_data)

            if data_to_preview:
                print(tabulate(data_to_preview, headers="keys", tablefmt="grid"))

        except Exception as e:
            err_print(f"could not generate preview: {e}")
        return True

    def _step_confirm_and_run(self) -> bool:
        """shows a summary and runs the final extraction"""
        print("\nsummary")
        print(f"  file:       {self.file_path}")
        print(f"  table:      {self.table_name}")
        print(f"  separator:  '{self.separator}'")
        print(f"  columns:    {', '.join(self.columns)}")
        print("\ncolumn mapping:")
        for csv_h, db_f in self.column_map.items():
            if db_f in self.columns:
                print(f"  - '{csv_h}' -> '{db_f}'")

        prompt = "proceed with extraction? (Y/n): "
        user_input = input(prompt).strip().lower()

        if user_input not in ("y", ""):
            err_print("aborted")
            return False

        try:
            print("starting extraction...")
            self.storage.create_table(self.table_name, self.columns)

            header_to_idx = {header: i for i, header in enumerate(self.csv_headers)}

            with open(self.file_path, "r", encoding="utf-8-sig") as f:
                f.readline()

                values_to_save = []
                for line in f:
                    if not line.strip():
                        continue

                    parts = line.strip().split(self.separator)

                    row_data = {}
                    for csv_header, column_name in self.column_map.items():
                        if column_name in self.columns:
                            idx = header_to_idx.get(csv_header)
                            if idx is not None and idx < len(parts):
                                row_data[column_name] = parts[idx]

                    if row_data:
                        values_to_save.append(row_data)

                if values_to_save:
                    self.storage.save(self.table_name, values_to_save)
            print("extraction complete")
            return True
        except Exception as e:
            err_print(f"an error occurred during extraction: {e}")
            return False
