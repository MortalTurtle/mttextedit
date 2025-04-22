from asyncio import Lock
import time
from view import View


class Model:
    users: list = list()
    user_positions: dict = {}
    shift_user_positions: dict = {}
    _text_m = Lock()
    _users_m = Lock()
    _users_pos_m = Lock()

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

    async def text_upload(self, text: str):
        async with self._text_m:
            self.text_lines = text.splitlines()

    async def user_pos_update(self, username, new_x, new_y):
        async with self._users_pos_m:
            self.user_positions[username] = (new_x, new_y)

    async def stop_view(self):
        self._stop = True

    def run_view(self, stdscr):
        self.view = View(stdscr, self._owner_username)
        while not self._stop:
            self.view.draw_text(
                self.text_lines, self.user_positions, self.users)
            time.sleep(0.05)

    async def add_user(self, username):
        async with self._users_m, self._users_pos_m:
            self.users.append(username)
            self.user_positions[username] = (0, 0)

    async def user_wrote_char(self, username, char):
        user_x, user_y = self.user_positions[username]
        async with self._text_m:
            if user_y == len(self.text_lines):
                self.text_lines.append(char)
            else:
                self.text_lines[user_y] = self.text_lines[user_y][:user_x] + \
                    char + self.text_lines[user_y][user_x:]
        await self.user_pos_shifted_right(username)

    async def user_pos_shifted_left(self, username):
        user_x, user_y = self.user_positions[username]
        if user_y == 0 and user_x == 0:
            return
        if user_x - 1 >= 0:
            user_x -= 1
        elif user_y > 0:
            user_y -= 1
            user_x = len(self.text_lines[user_y])
        async with self._users_pos_m:
            self.user_positions[username] = (user_x, user_y)

    async def user_pos_shifted_right(self, username):
        user_x, user_y = self.user_positions[username]
        if user_x + 1 <= len(self.text_lines[user_y]):
            user_x += 1
        elif user_y + 1 != len(self.text_lines):
            user_y += 1
            user_x = 0
        async with self._users_pos_m:
            self.user_positions[username] = (user_x, user_y)

    async def user_pos_shifted_down(self, username):
        user_x, user_y = self.user_positions[username]
        if user_y + 1 < len(self.text_lines):
            user_y += 1
            user_x = min(user_x, len(self.text_lines[user_y]))
        else:
            user_x = len(self.text_lines[user_y])
        async with self._users_pos_m:
            self.user_positions[username] = (user_x, user_y)

    async def user_pos_shifted_up(self, username):
        user_x, user_y = self.user_positions[username]
        if user_y == 0:
            user_x = 0
        if user_y > 0:
            user_y -= 1
            user_x = min(user_x, len(self.text_lines[user_y]))
        async with self._users_pos_m:
            self.user_positions[username] = (user_x, user_y)

    async def user_deleted_char(self, username):
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

    async def user_added_new_line(self, username):
        user_x, user_y = self.user_positions[username]
        async with self._text_m:
            self.text_lines.insert(user_y, "")
            self.text_lines[user_y] = self.text_lines[user_y + 1][:user_x]
            self.text_lines[user_y + 1] = self.text_lines[user_y + 1][user_x:]
        async with self._users_pos_m:
            self.user_positions[username] = (0, user_y + 1)
