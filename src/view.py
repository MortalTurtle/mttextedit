import curses


class View:
    def __init__(self, stdscr, owner_username):
        self._owner_username = owner_username
        curses.curs_set(0)
        self.stdscr = stdscr
        self._user_color_index = {}
        self._init_colors()
        self._draw_interface()
        self._offset_y = 0
        self._offset_x = 0

    def _init_colors(self):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        # also used for showing new text
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_GREEN)
        # also used for showing deleted text
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_RED)
        self.stdscr.bkgd(" ", curses.color_pair(1))

    def _correct_offset_by_owner_pos(
            self, owner_x, owner_y, max_uername_len=None):
        height, width = self.stdscr.getmaxyx()
        if max_uername_len:
            width -= max_uername_len
        while owner_x - self._offset_x >= width - 1:
            self._offset_x += 1
        while owner_x - self._offset_x < 0:
            self._offset_x -= 1
        while owner_y - self._offset_y >= height - 3:
            self._offset_y += 1
        while owner_y - self._offset_y < 0:
            self._offset_y -= 1

    def _draw_users_colors(self, users):
        height, width = self.stdscr.getmaxyx()
        line_offset = 0
        x_offset = 1
        for i in range(1, len(users) + 1):
            if x_offset + 3 + len(users[i - 1]) >= width:
                x_offset = 2
                line_offset += 1
            self.stdscr.addstr(height - 2 + line_offset, x_offset, " ")
            self.stdscr.addstr(
                height - 2 + line_offset,
                x_offset + 1,
                "@",
                curses.color_pair(i + 1),
            )
            self.stdscr.addstr(height - 2 + line_offset, x_offset + 2, "-")
            self.stdscr.addstr(
                height - 2 + line_offset, x_offset + 3, users[i - 1]
            )
            x_offset += 3 + len(users[i - 1])
            self.stdscr.addstr(
                height - 2 + line_offset, x_offset, " " * (width - x_offset)
            )
            self._user_color_index[users[i - 1]] = i + 1

    def _draw_single_selected_line(self, text_lines, color, y, start, end):
        height, width = self.stdscr.getmaxyx()
        if (
            start > end
            or start - self._offset_x > width - 1
            or end - self._offset_x < 0
            or y - self._offset_y + 1 < 0
            or y - self._offset_y + 1 >= height - 2
        ):
            return
        if start - self._offset_x < 0:
            start += self._offset_x - start
        if end - self._offset_x > width - 1:
            end -= end - self._offset_x - width + 1
        screen_num = y + 1 - self._offset_y
        if screen_num <= 0 or screen_num >= height - 2:
            return
        line = text_lines[y][start:end]
        self.stdscr.addstr(screen_num, start - self._offset_x, line, color)
        return

    def _paint_range(self, text_lines, color, top, bot):
        height, width = self.stdscr.getmaxyx()
        top_x, top_y = top
        bot_x, bot_y = bot
        if bot_y == top_y:
            min_x = min(bot_x, top_x)
            max_x = max(bot_x, top_x)
            self._draw_single_selected_line(
                text_lines, color, top_y, min_x, max_x
            )
            return
        upper_x = top_x if top_y < bot_y else bot_x
        min_y = min(top_y, bot_y)
        lower_x = top_x if top_y > bot_y else bot_x
        max_y = max(top_y, bot_y)
        self._draw_single_selected_line(
            text_lines, color, min_y, upper_x, self._offset_x + width - 1
        )
        self._draw_single_selected_line(
            text_lines, color, max_y, self._offset_x, lower_x
        )
        for y in range(min_y + 1, max_y):
            self._draw_single_selected_line(
                text_lines,
                color,
                y,
                self._offset_x,
                self._offset_x + width - 1,
            )

    def _draw_user_shift_pos(self, text_lines, user, top, bot):
        color = curses.color_pair(self._user_color_index[user])
        self._paint_range(text_lines, color, top, bot)

    def _draw_user_positions(
            self,
            text_lines,
            user_positions,
            users_shift_pos,
            max_username_len=None):
        height, width = self.stdscr.getmaxyx()
        if max_username_len:
            width -= (max_username_len + 1)
        else:
            max_username_len = -1
        for user in user_positions.keys():
            if user in users_shift_pos:
                self._draw_user_shift_pos(
                    text_lines,
                    user,
                    user_positions[user],
                    users_shift_pos[user],
                )
                continue
            user_x, user_y = user_positions[user]
            if (
                user_x - self._offset_x < 0
                or user_x - self._offset_x > width - 1
                or user_y - self._offset_y < 0
                or user_y - self._offset_y > height - 3
            ):
                continue
            if (
                len(text_lines) == 0
                or user_y >= len(text_lines)
                or len(text_lines) != 0
                and user_x >= len(text_lines[user_y])
            ):
                self.stdscr.addstr(
                    user_y + 1 - self._offset_y,
                    user_x - self._offset_x + max_username_len + 1, " ",
                    curses.color_pair(self._user_color_index[user]))
            else:
                self.stdscr.addstr(
                    user_y + 1 - self._offset_y,
                    user_x - self._offset_x + max_username_len + 1,
                    text_lines[user_y][user_x],
                    curses.color_pair(self._user_color_index[user]),
                )

    def _draw_changes(self, text_lines, changes_frames):
        for frame in changes_frames:
            if frame[0] == "insert":
                color = curses.color_pair(6)
            else:
                color = curses.color_pair(7)
            self._paint_range(text_lines, color, frame[1], frame[2])

    def draw_text(
        self,
        text_lines,
        user_positions,
        users,
        users_shift_pos,
        changes_frames=None,
    ):
        height, width = self.stdscr.getmaxyx()
        owner_x, owner_y = (
            user_positions[self._owner_username]
            if self._owner_username not in users_shift_pos
            else users_shift_pos[self._owner_username]
        )
        self._correct_offset_by_owner_pos(owner_x, owner_y)
        for y in range(1, height - 2):
            line_num = y - 1 + self._offset_y
            if line_num < len(text_lines):
                line = text_lines[line_num][
                    self._offset_x: self._offset_x + width - 1
                ]
                self.stdscr.addstr(y, 0, line + " " * (width - len(line)))
            else:
                self.stdscr.addstr(y, 0, " " * (width - 1))
        self._draw_users_colors(users)
        self._draw_user_positions(text_lines, user_positions, users_shift_pos)
        if changes_frames:
            self._draw_changes(text_lines, changes_frames)
        self.stdscr.refresh()

    def draw_blame(
            self,
            text_lines,
            user_positions,
            users,
            users_shift_pos,
            blame,
            max_username_len):
        height, width = self.stdscr.getmaxyx()
        width -= (max_username_len + 1)
        owner_x, owner_y = user_positions[self._owner_username] if \
            self._owner_username not in users_shift_pos else \
            users_shift_pos[self._owner_username]
        self._correct_offset_by_owner_pos(owner_x, owner_y, max_username_len)
        for y in range(1, height-2):
            line_num = y - 1 + self._offset_y
            if line_num < len(text_lines):
                line = text_lines[line_num][self._offset_x:
                                            self._offset_x + width-1]
                self.stdscr.addstr(y, max_username_len + 1,
                                   line + " " * (width - len(line)))
            else:
                self.stdscr.addstr(y, max_username_len + 1, " "*(width-1))
        self._draw_users_colors(users)
        self._draw_user_positions(
            text_lines, user_positions, users_shift_pos, max_username_len)
        for y in range(1, height - 2):
            if y + self._offset_y - 1 >= len(text_lines):
                break
            username = blame[y + self._offset_y - 1]
            self.stdscr.addstr(y, 0, username + " " *
                               (max_username_len - len(username)) + ":")
        self.stdscr.refresh()

    def _draw_interface(self):
        height, width = self.stdscr.getmaxyx()
        title = " MTTEXT " + " " * (width - 8)
        self.stdscr.addstr(0, 0, title, curses.color_pair(2))
