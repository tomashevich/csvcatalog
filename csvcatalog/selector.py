import curses


def select_options(options: list[str], title: str) -> list[str]:
    selected = [False] * len(options)
    current_pos = 0

    def draw_menu(stdscr):
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Instructions
        instructions = "[↑ ↓] navigate  [space] toggle  [enter] confirm  [esc] cancel"
        stdscr.addstr(0, 0, title)
        stdscr.addstr(h - 1, 0, instructions)

        # Options rendering starts from line 2
        for i, option in enumerate(options):
            if (i + 2) >= (h - 1):  # Check against available height
                break

            prefix = "[x] " if selected[i] else "[ ] "
            display_str = f"{prefix}{option}"

            if i == current_pos:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(i + 2, 0, display_str)
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(i + 2, 0, display_str)

        stdscr.refresh()

    def main_loop(stdscr):
        nonlocal current_pos
        curses.curs_set(0)
        stdscr.keypad(True)

        while True:
            draw_menu(stdscr)
            key = stdscr.getch()

            if key == curses.KEY_UP:
                current_pos = max(0, current_pos - 1)
            elif key == curses.KEY_DOWN:
                current_pos = min(len(options) - 1, current_pos + 1)
            elif key == ord(" "):
                selected[current_pos] = not selected[current_pos]
            elif key == curses.KEY_ENTER or key in [10, 13]:
                break
            elif key == 27:  # Escape key
                return []  # Cancel selection

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
        chosen_options = select_options(test_options, "Select fields to export:")
        print("\nSelected options:")
        if chosen_options:
            for opt in chosen_options:
                print(f"- {opt}")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("This test requires a terminal that supports curses.")
