import curses
import sys


def err_print(text: str) -> None:
    """Prints text in red to stderr."""
    print(f"\033[1;31merror: {text}\033[0m", file=sys.stderr)


def select_options(
    options: list[str], title: str, default_selected: bool = False
) -> list[str]:
    """an interactive selector for the terminal user interface"""
    selected = [default_selected] * len(options)
    current_pos = 0

    def draw_menu(stdscr, color_pair):
        stdscr.clear()
        h, _ = stdscr.getmaxyx()

        # instructions
        instructions = "[↑ ↓] navigate  [space] toggle  [enter] confirm  [esc] cancel"
        stdscr.addstr(0, 0, title)
        stdscr.attron(color_pair)
        stdscr.addstr(h - 1, 0, instructions)
        stdscr.attroff(color_pair)

        # options rendering starts from line 2
        for i, option in enumerate(options):
            if (i + 2) >= (h - 1):  # check against available height
                break

            display_str = option
            if selected[i]:
                stdscr.attron(color_pair)
                stdscr.addstr(i + 2, 0, "[x] ")
                stdscr.attroff(color_pair)
                stdscr.addstr(i + 2, 4, display_str)
            else:
                stdscr.addstr(i + 2, 0, f"[ ] {display_str}")

            if i == current_pos:
                stdscr.attron(curses.A_REVERSE)
                # need to redraw the line content inside the reverse block
                if selected[i]:
                    stdscr.attron(color_pair)
                    stdscr.addstr(i + 2, 0, "[x] ")
                    stdscr.attroff(color_pair)
                    stdscr.addstr(i + 2, 4, display_str)
                else:
                    stdscr.addstr(i + 2, 0, f"[ ] {display_str}")
                stdscr.attroff(curses.A_REVERSE)

        stdscr.refresh()

    def main_loop(stdscr):
        nonlocal current_pos
        curses.curs_set(0)
        stdscr.keypad(True)

        # initialize color
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        color_pair = curses.color_pair(1)

        while True:
            draw_menu(stdscr, color_pair)
            key = stdscr.getch()

            if key == curses.KEY_UP:
                current_pos = max(0, current_pos - 1)
            elif key == curses.KEY_DOWN:
                current_pos = min(len(options) - 1, current_pos + 1)
            elif key == ord(" "):
                selected[current_pos] = not selected[current_pos]
            elif key == curses.KEY_ENTER or key in [10, 13]:
                break
            elif key == 27:  # escape key
                return []  # cancel selection

    curses.wrapper(main_loop)

    return [options[i] for i, is_selected in enumerate(selected) if is_selected]


# example h0w use
if __name__ == "__main__":
    test_options = [
        "name",
        "email",
        "phone_number",
        "address",
        "city",
        "state",
        "zip_code",
    ]
    try:
        print(" running selector with default off ")
        chosen_options = select_options(
            test_options, "select fields to export (default off):"
        )
        print("\nselected options:")
        if chosen_options:
            for opt in chosen_options:
                print(f"- {opt}")

        print("\n running selector with default on ")
        chosen_options_on = select_options(
            test_options, "select fields to export (default on):", default_selected=True
        )
        print("\nselected options:")
        if chosen_options_on:
            for opt in chosen_options_on:
                print(f"- {opt}")

    except Exception as e:
        err_print(f"{e}, this test requires a terminal that supports curses")
