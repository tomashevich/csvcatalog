# CSVCatalog

a simple cli tool for wrangling csv files and shoving them into a sqlite database. no more manual scripts, no more headaches

## What's this? 🤔

tired of messing around with csvs and databases separately? me too. that's why i built catalog. it's a simple, no-nonsense tool that lets you:

*   **import csv files** into a sqlite database with an interactive wizard.
*   **search your data** with a powerful, flexible query syntax.
*   **export your data** back to csv whenever you need it.
*   **manage your database** with a set of easy-to-use commands.

## Getting Started 🚀

1.  install

```bash
pip install csvcatalog
```

2.  open the interactive catalog

run `csvcatalog` without arguments to open the **terminal ui**. it shows a searchable table list with a small footer summary. click a table (or press enter) to open it in a new tab below the top bar. everything works with both the keyboard and the mouse:

```bash
csvcatalog
```

if the configured database does not exist yet, the ui asks for a path instead of failing. path inputs suggest existing directories and `.db`/`.sqlite` files: use `↓` to browse suggestions, or just type a new path to create it. the same happens when you change the database path in settings.

opened tables become code-editor style tabs with a close cross, so you can switch between several tables without losing search or sort state. the table editor supports paged loading, server-side search, sorting by clicking column headers, editing a full row, adding and deleting rows, and renaming or deleting columns from the edit modal. large cell values are loaded only when you open a row, while the list uses truncated previews. search lives in a modal, so the table list always gets the full screen. the selected-table actions (view, edit, delete, export) live in the overview footer; the table viewer footer has row/table actions and pagination.

the layout adapts to the terminal size: the table list fills all available space, summary counters live in a small footer at the end of the list, and every scrollable area has its own scrollbar.

| key | action |
| --- | --- |
| `/` | open search |
| `s` | open settings |
| `f` | manage saved filters |
| `e` | edit the selected table |
| `d` | delete the selected table |
| `r` | refresh the catalog |
| `Ctrl+W` | close the active table tab |
| `Ctrl+C` twice | quit |

shortcuts also work on a russian keyboard layout (`s` / `ы`, `f` / `а`, `e` / `у`, `d` / `в`, `r` / `к`, `/` or `.` for search). `Ctrl+F`, `Ctrl+R` and `Ctrl+E` work regardless of layout.

3.  run a command

the basic structure is `csvcatalog COMMAND [ARGS]`. for example, to see all commands:

```bash
csvcatalog --help
```

by default, the database is stored in a user-specific data directory. you can specify a custom database file with the `dbfile` command:

```bash
# Optional
csvcatalog settings dbfile /path/to/your/database.db
```

you can setup aes256 encryption for database file

```bash
# Optional
csvcatalog settings encryption true
```

4.  extract your csv data table

```bash
csvcatalog extract path/to/my/data.csv
```

## Commands 🕹️

`typer` provides help for all commands. just run `csvcatalog --help` or `csvcatalog <command> --help` for more details.

*   `extract <file.csv>`: run an interactive wizard to import a csv file. you can map columns, select which ones to import, apply regex filters to include/exclude specific rows, and optionally keep only the first row for each unique combination of selected columns.
*   `search <value> [targets...]`: search for a value across one or more tables and columns.
*   `rows <table_name>`: show a page of rows with optional search, column selection, sorting, and pagination.
    *   `--limit <n>` / `--page <n>`: page size and page number.
    *   `--search <text>` / `--column <name>`: search text in specific columns.
    *   `--sort <column>` / `--desc`: sort the rows.
*   `replace <table_name> <search> <replacement>`: replace every case-insensitive match in the selected columns.
    *   `--column <name>`: limit replacement to a column; repeat for multiple columns. omitted means all columns.
    *   `--yes`: skip confirmation.
*   `export [table_names...]`: export one or more tables to csv files.
    *   if one table is specified, runs a full interactive wizard.
    *   if multiple tables are specified (or none, for all tables), runs a bulk export. you can choose to configure filters for specific tables.
*   `delete <table_names...>`: delete one or more tables from the database.
*   `sql "<query>"`: execute a raw sql query on the database.
*   `purge`: delete all tables from the database.

### Command Groups

these commands group related functionality.

#### `tables`
manage and view tables.

*   `tables list`: list all tables in the database.
    *   `--description <text>`: filter by text in the description.
    *   `--rows <min_count>`: filter by minimum row count.
    *   `--date <yyyy-mm-dd>`: filter by tables created on or after a certain date.
    *   `--sort <name|rows|date>`: sort the output.
*   `tables edit [table_name]`: interactively edit a table's metadata (name, description, or date). if `table_name` is omitted, a selector will be shown.

#### `settings`
manage application settings. running `csvcatalog settings` will show current settings.

*   `settings dbfile <path>`: set a custom path for the database file.
*   `settings encryption <true|false>`: enable or disable database encryption.

#### `filters`
manage saved reusable regex filters for `extract` and `export`. running `csvcatalog filters` will list all saved filters.

*   `filters add <name> <regex>`: create a new named filter.
*   `filters remove [name]`: remove a filter by name, or run interactively if no name is provided.

### the mighty `search` command

the `search` command lets you specify exactly where to look for your data. a "target" can be a table, a specific column in a table, or a column across all tables.

**search for a value in all tables (default behavior):**
```bash
# looks for 'jane' everywhere
csvcatalog search "jane"
```

**search for a value in specific tables:**
```bash
# looks for 'jane' in the 'users' and 'customers' tables
csvcatalog search "jane" users customers
```

**search for a value in a specific column of a specific table:**
```bash
# looks for the email in the 'email' column of the 'users' table
csvcatalog search "jane.doe@example.com" users.email
```

**search for a value in a specific column across all tables:**
```bash
# finds any entry with a 'status' of 'active' in any table
csvcatalog search "active" "*.status"
```

**combine any of these targets in one command:**
```bash
# a totally valid and powerful query
csvcatalog search "jane" users.name products
```

### inspecting rows

the `rows` command shows one page of a table and supports the same search and
sorting options as the interactive table view:

```bash
# rows 51-100, searching only name and email, newest first
csvcatalog rows customers --limit 50 --page 2 --search "jane" --column name --column email --sort created --desc
```

### replace

`replace` works like find-and-replace in an editor. matching is case-insensitive
and happens only in the selected columns:

```bash
# replace every "Tokyo" with "Osaka" in the city column
csvcatalog replace customers "Tokyo" "Osaka" --column city

# skip the confirmation prompt
csvcatalog replace customers "Tokyo" "Osaka" --column city --yes
```

## contributing are welcome 🤝
