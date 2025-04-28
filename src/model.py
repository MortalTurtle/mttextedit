from asyncio import Lock
from functools import wraps
import time
from view import View

# TODO check user pos to be always in bounds


class Model:
    users: list = list()
    user_positions: dict = {}
    shift_user_positions: dict = {}
    _text_m = Lock()
    _users_m = Lock()
    _users_pos_m = Lock()
    _buffer = ""

    def __init__(self, text: str, owner_username, file_path=None):
        self._stop = False
        self._owner_username = owner_username
        self._file_path = file_path
        self.users.append(owner_username)
        self.user_positions[owner_username] = (0, 0)
        self.text_lines = text.splitlines()
        if text == "":
            self.text_lines = [""]

    async def get_user_pos(self, username):
        async with self._users_pos_m:
            return self.user_positions[username]

    async def save_file(self):
        if self._file_path == None:
            return
        async with self._text_m:
            with open(self._file_path, "w") as f:
                text = "\n".join(self.text_lines)
                f.write(text)

    async def user_disconnected(self, username):
        async with self._users_m, self._users_pos_m:
            self.users.remove(username)
            self.user_positions.pop(username)
            if username in self.shift_user_positions:
                self.shift_user_positions.pop(username)

    async def text_upload(self, text: str):
        async with self._text_m:
            self.text_lines = text.splitlines()

    async def user_pos_update(self, username, new_x, new_y):
        async with self._users_pos_m:
            self.user_positions[username] = (new_x, new_y)

    async def stop_view(self):
        self._stop = True

    async def _get_user_top_bot_selected(self, username):
        top = self.user_positions[username]
        bot = self.shift_user_positions[username]
        if bot[1] < top[1] or bot[1] == top[1] and bot[0] < top[0]:
            t = bot
            bot = top
            top = t
        return (top, bot)

    async def _cut_selected_text(self, top, bot):
        bot_x, bot_y = bot
        top_x, top_y = top
        async with self._text_m:
            if bot_y == top_y:
                self.text_lines[bot_y] = self.text_lines[bot_y][:top_x] + \
                    self.text_lines[bot_y][bot_x:]
            else:
                self.text_lines[top_y] = self.text_lines[top_y][:top_x] + \
                    self.text_lines[bot_y][bot_x:]
                self.text_lines.pop(bot_y)
            for y in range(bot_y - 1, top_y, -1):
                self.text_lines.pop(y)

    async def copy_to_buffer(self):
        if self._owner_username not in self.shift_user_positions:
            return
        top, bot = await self._get_user_top_bot_selected(self._owner_username)
        top_x, top_y = top
        bot_x, bot_y = bot
        if bot_y == top_y:
            self._buffer = self.text_lines[bot_y][top_x:bot_x]
            return
        t = '' if bot_y - \
            top_y <= 1 else '\n'.join(self.text_lines[top_y + 1: bot_y]) + '\n'
        self._buffer = self.text_lines[top_y][top_x:] + '\n' + \
            t + \
            self.text_lines[bot_y][:bot_x]

    async def paste(self, username, tex_to_paste):
        if username in self.shift_user_positions:
            await self._user_deleted_char_shifted(username)
        lines_to_paste = tex_to_paste.split('\n')
        user_x, user_y = self.user_positions[username]
        moved_user_x, moved_user_y = self.user_positions[username]
        moved_user_x += len(lines_to_paste[0])
        if len(lines_to_paste) != 1:
            moved_user_x = len(lines_to_paste[-1])
        lines_to_paste[-1] = lines_to_paste[-1] + \
            self.text_lines[user_y][user_x:]
        async with self._text_m:
            self.text_lines[user_y] = self.text_lines[user_y][:user_x] + \
                lines_to_paste[0]
            for i in range(1, len(lines_to_paste)):
                user_y += 1
                self.text_lines.insert(user_y, lines_to_paste[i])
        moved_user_y = user_y
        async with self._users_pos_m:
            self.user_positions[username] = (
                moved_user_x, moved_user_y)

    async def paste_from_buffer(self):
        await self.paste(self._owner_username, self._buffer)

    async def cut_to_buffet(self):
        if self._owner_username not in self.shift_user_positions:
            return
        await self.copy_to_buffer()
        await self._user_deleted_char_shifted(self._owner_username)

    async def cut(self, username):
        if username not in self.shift_user_positions:
            return
        await self._user_deleted_char_shifted(username)

    def run_view(self, stdscr):
        self.view = View(stdscr, self._owner_username)
        while not self._stop:
            self.view.draw_text(
                self.text_lines, self.user_positions, self.users, self.shift_user_positions)
            time.sleep(0.05)

    async def add_user(self, username):
        async with self._users_m, self._users_pos_m:
            self.users.append(username)
            self.user_positions[username] = (0, 0)

    async def _restore_user_pos(self, username, direction, user_pos_sh, user_pos):
        if direction == "u" and \
            (user_pos_sh[1] == user_pos[1] and user_pos_sh[0] <= user_pos[0]
                or user_pos_sh[1] < user_pos[1]) \
            or direction == "d" and \
            (user_pos_sh[1] > user_pos[1] or
                user_pos_sh[1] == user_pos_sh[1] and user_pos_sh[0] >= user_pos[0]):
            user_pos = user_pos_sh
        if direction == "l" and (user_pos_sh[1] < user_pos[1] or user_pos_sh[0] < user_pos[0]):
            user_pos = (user_pos_sh[0] + 1, user_pos_sh[1])
        if direction == "r" and (user_pos_sh[1] > user_pos[1] or user_pos_sh[0] > user_pos[0]):
            user_pos = (user_pos_sh[0] - 1, user_pos_sh[1])
        async with self._users_pos_m:
            self.shift_user_positions.pop(username)
        return user_pos

    async def _change_user_pos(self, user_pos, username, user_shifted=False):
        async with self._users_pos_m:
            if user_shifted:
                self.shift_user_positions[username] = user_pos
            else:
                self.user_positions[username] = user_pos

    def _user_pos_shifted_decor(new_pos_func, direction):
        def dec(func):
            @wraps(func)
            async def wrapper(self, username, user_shifted=False):
                if user_shifted and username not in self.shift_user_positions:
                    self.shift_user_positions[username] = self.user_positions[username]
                user_pos = self.user_positions[username] if not user_shifted else \
                    self.shift_user_positions[username]
                if not user_shifted and username in self.shift_user_positions:
                    user_pos_sh = self.shift_user_positions[username]
                    user_pos = await self._restore_user_pos(username,
                                                            direction,
                                                            user_pos_sh,
                                                            user_pos)
                await self._change_user_pos(await new_pos_func(self, user_pos), username, user_shifted)
            return wrapper
        return dec

    def _handle_edit_if_user_shifted(func):
        async def wrapper(self, username, *args, **kwargs):
            if username not in self.shift_user_positions:
                await func(self, username, *args, *kwargs)
                return
            top, bot = await self._get_user_top_bot_selected(username)
            await self._cut_selected_text(top, bot)
            async with self._users_pos_m:
                self.shift_user_positions.pop(username)
                self.user_positions[username] = top
            await func(self, username, *args, *kwargs)
        return wrapper

    @_handle_edit_if_user_shifted
    async def user_wrote_char(self, username, char):
        user_x, user_y = self.user_positions[username]
        async with self._text_m:
            if user_y == len(self.text_lines):
                self.text_lines.append(char)
            else:
                self.text_lines[user_y] = self.text_lines[user_y][:user_x] + \
                    char + self.text_lines[user_y][user_x:]
        await self.user_pos_shifted_right(username)

    async def _shift_pos_left(self, user_pos):
        user_x, user_y = user_pos
        if user_y == 0 and user_x == 0:
            return (user_x, user_y)
        if user_x - 1 >= 0:
            user_x -= 1
        elif user_y > 0:
            user_y -= 1
            user_x = len(self.text_lines[user_y])
        return (user_x, user_y)

    async def _shift_pos_right(self, user_pos):
        user_x, user_y = user_pos
        if user_x + 1 <= len(self.text_lines[user_y]):
            user_x += 1
        elif user_y + 1 != len(self.text_lines):
            user_y += 1
            user_x = 0
        return (user_x, user_y)

    async def _shift_pos_down(self, user_pos):
        user_x, user_y = user_pos
        if user_y + 1 < len(self.text_lines):
            user_y += 1
            user_x = min(user_x, len(self.text_lines[user_y]))
        else:
            user_x = len(self.text_lines[user_y])
        return (user_x, user_y)

    async def _shift_pos_up(self, user_pos):
        user_x, user_y = user_pos
        if user_y == 0:
            user_x = 0
        if user_y > 0:
            user_y -= 1
            user_x = min(user_x, len(self.text_lines[user_y]))
        return (user_x, user_y)

    @_user_pos_shifted_decor(_shift_pos_left, "l")
    async def user_pos_shifted_left(self, username, user_shifted=False):
        pass

    @_user_pos_shifted_decor(_shift_pos_right, "r")
    async def user_pos_shifted_right(self, username, user_shifted=False):
        pass

    @_user_pos_shifted_decor(_shift_pos_down, "d")
    async def user_pos_shifted_down(self, username, user_shifted=False):
        pass

    @_user_pos_shifted_decor(_shift_pos_up, "u")
    async def user_pos_shifted_up(self, username, user_shifted=False):
        pass

    async def user_shifted_left(self, username):
        await self.user_pos_shifted_left(username, True)

    async def user_shifted_right(self, username):
        await self.user_pos_shifted_right(username, True)

    async def user_shifted_up(self, username):
        await self.user_pos_shifted_up(username, True)

    async def user_shifted_down(self, username):
        await self.user_pos_shifted_down(username, True)

    @_handle_edit_if_user_shifted
    async def _user_deleted_char_shifted(self, username):
        pass

    async def user_deleted_char(self, username):
        if username in self.shift_user_positions:
            await self._user_deleted_char_shifted(username)
            return
        user_x, user_y = self.user_positions[username]
        if user_x == 0:
            if user_y == 0:
                return
            user_x = len(self.text_lines[user_y - 1])
            async with self._text_m:
                self.text_lines[user_y - 1] += self.text_lines.pop(user_y)
            user_y -= 1
            async with self._users_pos_m:
                self.user_positions[username] = (user_x, user_y)
            return
        else:
            async with self._text_m:
                self.text_lines[user_y] = self.text_lines[user_y][:user_x - 1] + \
                    self.text_lines[user_y][user_x:]
        await self.user_pos_shifted_left(username)

    @_handle_edit_if_user_shifted
    async def user_added_new_line(self, username):
        user_x, user_y = self.user_positions[username]
        async with self._text_m:
            self.text_lines.insert(user_y, "")
            self.text_lines[user_y] = self.text_lines[user_y + 1][:user_x]
            self.text_lines[user_y + 1] = self.text_lines[user_y + 1][user_x:]
        async with self._users_pos_m:
            self.user_positions[username] = (0, user_y + 1)
