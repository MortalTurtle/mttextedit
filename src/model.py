from asyncio import Lock
from functools import wraps
import time
from view import View


class Model:
    users: list = list()
    user_positions: dict = {}
    shift_user_positions: dict = {}
    _text_m = Lock()
    _users_m = Lock()
    _users_pos_m = Lock()
    _buffer = ""
    _action_stack_m = Lock()
    _action_stack_by_user = {}
    # each stack stores (undo_func: couritine, undo_kwargs: dict,
    #  redo_func: courutine, redo_args: list)
    _reverted_action_stack_by_user = {}
    # each stack stores (redo_func: courutine, redo_args: list)
    # redo_func must crate new action frame for action stack

    def __init__(self, text: str, owner_username, permissions_file = 'permissions.txt', file_path=None):
        self._stop = False
        self._owner_username = owner_username
        self._file_path = file_path
        self.users.append(owner_username)
        self.user_positions[owner_username] = (0, 0)
        self._action_stack_by_user[owner_username] = []
        self._reverted_action_stack_by_user[owner_username] = []
        self.text_lines = text.splitlines()
        if text == "":
            self.text_lines = [""]
        self._permissions = {}
        self._permissions_file = permissions_file
        self._load_permissions()

    def _load_permissions(self):
        try:
            with open(self._permissions_file, 'r') as f:
                for line in f:
                    if ':' in line:
                        user, rights = line.strip().split(':')
                        self._permissions[user] = rights
        except FileNotFoundError:
            pass
            
    async def _check_permission(self, username, required_right):
        if username == self._owner_username:
            return True
        if username not in self._permissions:
            return False
        user_rights = self._permissions[username]
        if required_right == 'read':
            return user_rights in ['r', 'rw']
        if required_right == 'write':
            return user_rights == 'rw'
        return False

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
            self._action_stack_by_user.pop(username)
            self._reverted_action_stack_by_user.pop(username)
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

    async def _get_correct_top_bot_orientation(self, pos1, pos2):
        if pos2[1] < pos1[1] or pos2[1] == pos1[1] and pos2[0] < pos1[0]:
            t = pos2
            pos2 = pos1
            pos1 = t
        return (pos1, pos2)

    async def _get_user_top_bot_selected(self, username):
        top = self.user_positions[username]
        bot = self.shift_user_positions[username]
        return await self._get_correct_top_bot_orientation(top, bot)

    async def _cut_selected_text(self, top, bot):
        top, bot = await self._get_correct_top_bot_orientation(top, bot)
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

    async def _get_range(self, top, bot):
        if bot[1] < top[1] or \
                bot[1] == top[1] and bot[0] < top[0]:
            t = top
            top = bot
            bot = t
        top_x, top_y = top
        bot_x, bot_y = bot
        if bot_y == top_y:
            return self.text_lines[bot_y][top_x:bot_x]
        t = '' if bot_y - \
            top_y <= 1 else '\n'.join(self.text_lines[top_y + 1: bot_y]) + '\n'
        return self.text_lines[top_y][top_x:] + '\n' + \
            t + \
            self.text_lines[bot_y][:bot_x]

    async def _insert(self, text, pos):
        lines_to_paste = text.split('\n')
        user_x, user_y = pos
        moved_user_x, moved_user_y = pos
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
        return (moved_user_x, moved_user_y)

    async def _set_user_pos(self, username, user_pos, shifted_pos=None):
        async with self._users_pos_m:
            self.user_positions[username] = user_pos
            if shifted_pos:
                self.shift_user_positions[username] = shifted_pos

    async def _append_to_action_stack(self, username,
                                      undo_func,
                                      undo_kwargs,
                                      redo_func,
                                      redo_kwargs):
        async with self._action_stack_m:
            self._reverted_action_stack_by_user[username].clear()
            self._action_stack_by_user[username].append(
                (undo_func, undo_kwargs, redo_func, redo_kwargs))

    async def _undo_selected_cut(self, username, user_pos, shifted_pos, text_cut):
        if not shifted_pos:
            return
        top = user_pos
        bot = shifted_pos
        if shifted_pos[1] < user_pos[1] or \
                shifted_pos[1] == user_pos[1] and shifted_pos[0] < user_pos[0]:
            t = bot
            bot = top
            top = t
        await self._insert(text_cut, top)

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
            self._action_stack_by_user[username] = []
            self._reverted_action_stack_by_user[username] = []

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

    def _make_pos_inbounds(func):
        async def wrapper(self, user_pos, username, user_shifted):
            user_x, user_y = user_pos
            user_y = min(user_y, len(self.text_lines) - 1)
            user_x = min(user_x, len(self.text_lines[user_y]))
            await func(self, (user_x, user_y), username, user_shifted)
        return wrapper

    @_make_pos_inbounds
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

    # all functions using this decorator, must have this arguments in specified order:
    # self, username, user_pos, shifted_pos for making correct action frames
    def _handle_edit_decorator(undo_func, redo_func_name):
        def dec(func):
            @wraps(func)
            async def wrapper(*args):
                self, username, user_pos, shifted_pos, *rest = args
                undo_kwargs = {'username': username,
                               'user_pos': user_pos,
                               'self': self}
                if not shifted_pos:
                    await self._append_to_action_stack(username, undo_func,
                                                       undo_kwargs, getattr(
                                                           Model, redo_func_name),
                                                       args)
                    await func(*args)
                    return
                top, bot = await self._get_correct_top_bot_orientation(user_pos, shifted_pos)
                undo_kwargs['shifted_pos'] = shifted_pos
                undo_kwargs['text_cut'] = await self._get_range(top, bot)
                await self._append_to_action_stack(username, undo_func,
                                                   undo_kwargs, getattr(
                                                       Model, redo_func_name),
                                                   args)
                await self._cut_selected_text(top, bot)
                async with self._users_pos_m:
                    self.shift_user_positions.pop(username)
                    self.user_positions[username] = top
                await func(*args)
            return wrapper
        return dec

    async def copy_to_buffer(self):
        if self._owner_username not in self.shift_user_positions:
            return
        top, bot = await self._get_user_top_bot_selected(self._owner_username)
        self._buffer = await self._get_range(top, bot)

    async def _undo_paste(self, username, user_pos, new_pos, shifted_pos=None, text_cut=None):
        top = user_pos
        if shifted_pos:
            if shifted_pos[1] < user_pos[1] or \
                    shifted_pos[1] == user_pos[1] and shifted_pos[0] < user_pos[0]:
                top = shifted_pos
        await self._cut_selected_text(top, new_pos)
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        await self._set_user_pos(username, user_pos, shifted_pos)

    @_handle_edit_decorator(_undo_paste, '_make_paste')
    async def _make_paste(self, username, user_pos, shifted_pos, text_to_paste):
        new_pos = await self._insert(text_to_paste, self.user_positions[username])
        async with self._action_stack_m:
            self._action_stack_by_user[username][-1][1]['new_pos'] = new_pos
        async with self._users_pos_m:
            self.user_positions[username] = new_pos

    async def paste(self, username, text_to_paste):
        async with self._action_stack_m:
            self._reverted_action_stack_by_user[username].clear()
        user_pos = self.user_positions[username]
        shifted_pos = self.shift_user_positions.get(username, None)
        await self._make_paste(username, user_pos, shifted_pos, text_to_paste)

    async def paste_from_buffer(self):
        if self._buffer == "":
            return
        await self.paste(self._owner_username, self._buffer)

    async def cut(self, username):
        if username not in self.shift_user_positions:
            return
        if username == self._owner_username:
            await self.copy_to_buffer()
        await self.user_deleted_char(username)

    async def _undo_user_wrote_char(self, username, user_pos, shift_pos=None, text_cut=None):
        await self._cut_selected_text(user_pos, await self._shift_pos_right(user_pos))
        await self._undo_selected_cut(username, user_pos, shift_pos, text_cut)
        await self._set_user_pos(username, user_pos, shift_pos)

    @_handle_edit_decorator(_undo_user_wrote_char, '_make_write_char')
    async def _make_write_char(self, username, user_pos, shifted_pos, char):
        user_x, user_y = user_pos
        async with self._text_m:
            if user_y == len(self.text_lines):
                self.text_lines.append(char)
            else:
                self.text_lines[user_y] = self.text_lines[user_y][:user_x] + \
                    char + self.text_lines[user_y][user_x:]
        await self.user_pos_shifted_right(username)

    async def user_wrote_char(self, username, char):
        async with self._action_stack_m:
            self._reverted_action_stack_by_user[username].clear()
        user_pos = self.user_positions[username]
        shifted_pos = self.shift_user_positions.get(username, None)
        await self._make_write_char(username, user_pos, shifted_pos, char)

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

    async def _undo_delete_char(self, username, text_cut, user_pos, shifted_pos=None):
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        if not shifted_pos:
            await self._insert(text_cut, await self._shift_pos_left(user_pos))
        await self._set_user_pos(username, user_pos, shifted_pos)

    @_handle_edit_decorator(_undo_delete_char, '_make_delete_char')
    async def _make_delete_char(self, username, user_pos, shifted_pos):
        if shifted_pos:
            return
        self._action_stack_by_user[username][-1][1]['text_cut'] = await self._get_range(
            await self._shift_pos_left(user_pos), user_pos)
        user_x, user_y = user_pos
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

    async def user_deleted_char(self, username):
        async with self._action_stack_m:
            self._reverted_action_stack_by_user[username].clear()
        await self._make_delete_char(
            username, self.user_positions[username],
            self.shift_user_positions[username] if username in self.shift_user_positions
            else None)

    async def _undo_new_line(self, username, user_pos, shifted_pos=None, text_cut=None):
        await self._cut_selected_text(user_pos, (0, user_pos[1] + 1))
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        await self._set_user_pos(username, user_pos, shifted_pos)

    @_handle_edit_decorator(_undo_new_line, '_make_new_line')
    async def _make_new_line(self, username, user_pos, shifted_pos):
        user_x, user_y = user_pos
        async with self._text_m:
            self.text_lines.insert(user_y, "")
            self.text_lines[user_y] = self.text_lines[user_y + 1][:user_x]
            self.text_lines[user_y + 1] = self.text_lines[user_y + 1][user_x:]
        async with self._users_pos_m:
            self.user_positions[username] = (0, user_y + 1)

    async def user_added_new_line(self, username):
        async with self._action_stack_m:
            # TODO: clear forall users in all functions
            self._reverted_action_stack_by_user[username].clear()

        user_pos = self.user_positions[username]
        if username in self.shift_user_positions:
            shifted_pos = self.shift_user_positions[username]
        else:
            shifted_pos = None
        await self._make_new_line(username, user_pos, shifted_pos)

    async def undo(self, username):
        if len(self._action_stack_by_user[username]) == 0:
            return
        async with self._action_stack_m:
            revert_func, revert_kwargs, redo_func, redo_args = \
                self._action_stack_by_user[username].pop()
            self._reverted_action_stack_by_user[username].append(
                (redo_func, redo_args))
        await revert_func(**revert_kwargs)

    async def redo(self, username):
        if len(self._reverted_action_stack_by_user[username]) == 0:
            return
        async with self._action_stack_m:
            redo_func, redo_args = \
                self._reverted_action_stack_by_user[username].pop()
        await redo_func(*redo_args)
