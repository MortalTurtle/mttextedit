from asyncio import Lock
from functools import wraps
import time
from history_handler import HistoryHandler
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

    def __init__(self, text: str, owner_username, file_path=None):
        self._stop = False
        self._owner_username = owner_username
        self._file_path = file_path
        self.users.append(owner_username)
        self.user_positions[owner_username] = (0, 0)
        self._action_stack_by_user[owner_username] = []
        self._reverted_action_stack_by_user[owner_username] = []
        self.text_lines = text.splitlines()
        self._history_handler = HistoryHandler(file_path)
        if text == "":
            self.text_lines = [""]
        if file_path:
            self._history_handler.load_blame(self.text_lines, owner_username)

    async def get_user_pos(self, username):
        async with self._users_pos_m:
            return self.user_positions[username]

    async def save_file(self):
        async with self._text_m:
            await self._history_handler.save_file(self.text_lines)

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

    async def _correct_all_frames_and_pos_on_cut(self, username, top, bot):
        for user in self.users:
            if user == username:
                continue
            for frame in self._action_stack_by_user[user]:
                await self._correct_undo_frame_on_cut(frame, top, bot)
            for frame in self._reverted_action_stack_by_user[user]:
                await self._correct_redo_frame_on_cut(frame, top, bot)
            await self._correct_pos_on_cut(user, top, bot)

    async def _make_pos_correct_after_cut(self, top, bot, pos, shifted_pos=None):
        if await self._is_pos_in_range(pos, top, bot):
            pos = top
        if pos[1] > bot[1]:
            pos = (pos[0], pos[1] - (bot[1] - top[1]))
        if pos[1] == bot[1] and pos[0] >= bot[0]:
            pos = (pos[0] - (bot[0] - top[0]), top[1])
        if shifted_pos:
            if await self._is_pos_in_range(shifted_pos, top, bot):
                shifted_pos = top
            if shifted_pos[1] > bot[1]:
                shifted_pos = (
                    shifted_pos[0], shifted_pos[1] - (bot[1] - top[1]))
            if shifted_pos[1] == bot[1] and shifted_pos[0] >= bot[0]:
                shifted_pos = (
                    shifted_pos[0] - (bot[0] - top[0]), top[1])
        return (pos, shifted_pos)

    async def _correct_pos_on_cut(self, username_to_correct, top, bot):
        user_pos = self.user_positions[username_to_correct]
        user_shifted_pos = self.shift_user_positions.get(username_to_correct)
        new_pos = await self._make_pos_correct_after_cut(top, bot, user_pos, user_shifted_pos)
        await self._set_user_pos(username_to_correct, *new_pos)

    async def _correct_redo_frame_on_cut(self, frame, top, bot):
        s, frame_username, frame_pos, frame_shifted_pos = frame[1]
        new_pos = await self._make_pos_correct_after_cut(top, bot, frame_pos, frame_shifted_pos)
        frame[1] = [s, frame_username, new_pos[0], new_pos[1]]

    async def _correct_undo_frame_on_cut(self, frame, top, bot):
        undo_func, undo_kwargs, redo_func, redo_args = frame
        frame_pos = undo_kwargs['user_pos']
        frame_shifted_pos = undo_kwargs.get('shifted_pos')
        new_pos = await self._make_pos_correct_after_cut(top, bot, frame_pos, frame_shifted_pos)
        undo_kwargs['user_pos'] = new_pos[0]
        undo_kwargs['shifted_pos'] = new_pos[1]
        frame[3] = (redo_args[0], redo_args[1], new_pos[0], new_pos[1])

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

    async def _is_pos_in_range(self, pos, top, bot):
        return top[1] < pos[1] and pos[1] < bot[1] or \
            top[1] == pos[1] and top[0] < pos[0] and \
            (bot[1] > pos[1] or bot[1] == pos[1] and pos[0] < bot[0]) or \
            bot[1] == pos[1] and bot[0] > pos[0] and \
            (top[1] < pos[1] or top[1] == pos[1] and top[0] < pos[0])

    async def _get_bot_pos_on_insert(self, pos, text):
        lines = text.split('\n')
        moved_x, moved_y = pos
        moved_x += len(lines[0])
        if len(lines) != 1:
            moved_x = len(lines[-1])
        moved_y += (len(lines) - 1)
        return (moved_x, moved_y)

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

    async def _make_pos_correct_on_insert(self, action_top, action_bot, pos, shifted_pos=None):
        if shifted_pos:
            if shifted_pos[1] == action_top[1] and shifted_pos[0] >= action_top[0]:
                shifted_pos = (shifted_pos[0] + action_bot[0] - action_top[0],
                               shifted_pos[1] + action_bot[1] - action_top[1])
            elif shifted_pos[1] > action_top[1]:
                shifted_pos = (
                    shifted_pos[0], shifted_pos[1] + action_bot[1] - action_top[1])
        if pos[1] == action_top[1] and pos[0] >= action_top[0]:
            pos = (pos[0] + action_bot[0] - action_top[0],
                   pos[1] + action_bot[1] - action_top[1])
        elif pos[1] > action_top[1]:
            pos = (pos[0], pos[1] + action_bot[1] - action_top[1])
        return (pos, shifted_pos)

    async def _correct_redo_frame_on_insert(self, frame, action_top, action_bot):
        s, frame_username, frame_pos, frame_shifted_pos = frame[1]
        new_pos = await self._make_pos_correct_on_insert(action_top, action_bot, frame_pos, frame_shifted_pos)
        frame[1] = [s, frame_username, new_pos[0], new_pos[1]]

    async def _correct_undo_frame_on_insert(self, frame, action_top, action_bot):
        undo_func, undo_kwargs, redo_func, redo_args = frame
        frame_pos = undo_kwargs['user_pos']
        frame_shifted_pos = undo_kwargs.get('shifted_pos')
        new_pos = await self._make_pos_correct_on_insert(action_top, action_bot, frame_pos, frame_shifted_pos)
        undo_kwargs['user_pos'] = new_pos[0]
        undo_kwargs['shifted_pos'] = new_pos[1]
        frame[3] = (redo_args[0], redo_args[1], new_pos[0], new_pos[1])

    async def _correct_all_frames_and_pos_on_insert(self, username, text_top, text_bot):
        for user in self.users:
            if user == username:
                continue
            for frame in self._action_stack_by_user[user]:
                await self._correct_undo_frame_on_insert(frame, text_top, text_bot)
            for frame in self._reverted_action_stack_by_user[user]:
                await self._correct_redo_frame_on_insert(frame, text_top, text_bot)
            new_pos = await self._make_pos_correct_on_insert(
                text_top, text_bot, self.user_positions[user],
                self.shift_user_positions.get(user))
            await self._set_user_pos(user, *new_pos)

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
            self._action_stack_by_user[username].append(
                [undo_func, undo_kwargs, redo_func, redo_kwargs])

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

    async def _correct_user_pos(self, username_to_correct, username, pos_correction_func, args):
        new_pos = await pos_correction_func(
            self,
            self.user_positions[username],
            self.user_positions[username_to_correct],
            self.shift_user_positions.get(username_to_correct),
            args
        )
        await self._set_user_pos(username_to_correct, *new_pos)

    async def _correct_redo_frame(self, frame, action_pos, pos_correction_func, args):
        s, frame_username, frame_pos, frame_shifted_pos = frame[1]
        new_pos = await pos_correction_func(
            self,
            action_pos, frame_pos, frame_shifted_pos,
            args
        )
        frame[1] = [s, frame_username, new_pos[0], new_pos[1]]

    async def _correct_undo_frame(self, username, pos_correction_func, frame, args):
        undo_kwargs = frame[1]
        redo_args = frame[3]
        frame_pos = undo_kwargs['user_pos']
        frame_shifted_pos = undo_kwargs['shifted_pos']
        new_pos = await pos_correction_func(
            self,
            self.user_positions[username],
            frame_pos,
            frame_shifted_pos,
            args)
        undo_kwargs['user_pos'] = new_pos[0]
        undo_kwargs['shifted_pos'] = new_pos[1]
        frame[3] = (redo_args[0], redo_args[1], new_pos[0], new_pos[1])

    async def _correct_frames_and_posision(
            self, username,
            pos_correction_func,
            action_pos,
            args):
        for user in self.users:
            if user == username:
                continue
            for frame in self._action_stack_by_user[user]:
                await self._correct_undo_frame(username, pos_correction_func, frame, args)
            for frame in self._reverted_action_stack_by_user[user]:
                await self._correct_redo_frame(frame, action_pos, pos_correction_func, args)
            await self._correct_user_pos(user, username, pos_correction_func, args)

    async def _correct_frames_and_posisitions_shifted(
            self, username,
            pos_correction_func,
            action_top, action_bot,
            args):
        for user in self.users:
            if user == username:
                continue
            for frame in self._action_stack_by_user[user]:
                await self._correct_undo_frame_on_cut(frame, action_top, action_bot)
                await self._correct_undo_frame(username, pos_correction_func, frame, args)
            for frame in self._reverted_action_stack_by_user[user]:
                await self._correct_redo_frame_on_cut(frame, action_top, action_bot)
                await self._correct_redo_frame(frame, action_top, pos_correction_func, args)
            await self._correct_pos_on_cut(user, action_top, action_bot)
            await self._correct_user_pos(user, username, pos_correction_func, args)

    # all functions using this decorator, must have this arguments in specified order:
    # self, username, user_pos, shifted_pos for making correct action frames
    # pos_correction func must take (self, action_pos: tuple, pos: tuple, shifted_pos: tuple, args: list)
    def _handle_edit_decorator(undo_func, redo_func_name, pos_correction_func):
        def dec(func):
            @wraps(func)
            async def wrapper(*args):
                self, username, user_pos, shifted_pos, *rest = args
                undo_kwargs = {'username': username,
                               'user_pos': user_pos,
                               'self': self}
                undo_kwargs['op_cnt'] = self._history_handler._op_cnt + 1
                if not shifted_pos:
                    await self._correct_frames_and_posision(
                        username, pos_correction_func,
                        user_pos, args)
                    await self._append_to_action_stack(username, undo_func,
                                                       undo_kwargs, getattr(
                                                           Model, redo_func_name),
                                                       args)
                    await func(*args)
                    return
                top, bot = await self._get_correct_top_bot_orientation(user_pos, shifted_pos)
                undo_kwargs['shifted_pos'] = shifted_pos
                undo_kwargs['text_cut'] = await self._get_range(top, bot)
                await self._history_handler.user_cut_save_history(username, self.text_lines, top, bot)
                await self._append_to_action_stack(username, undo_func,
                                                   undo_kwargs, getattr(
                                                       Model, redo_func_name),
                                                   args)
                await self._cut_selected_text(top, bot)
                await self._correct_frames_and_posisitions_shifted(
                    username, pos_correction_func,
                    top, bot, args)
                async with self._users_pos_m:
                    if username in self.shift_user_positions:
                        self.shift_user_positions.pop(username)
                    self.user_positions[username] = top
                await func(*args)
            return wrapper
        return dec

    def _after_edit_corrector_decor(func):
        async def wrapper(*args):
            self, username, *rest = args
            async with self._action_stack_m:
                self._reverted_action_stack_by_user[username].clear()
            await func(*args)
        return wrapper

    async def copy_to_buffer(self):
        if self._owner_username not in self.shift_user_positions:
            return
        top, bot = await self._get_user_top_bot_selected(self._owner_username)
        self._buffer = await self._get_range(top, bot)

    async def _undo_paste(self, username, user_pos, new_pos, op_cnt=-1, shifted_pos=None, text_cut=None):
        top = user_pos
        if shifted_pos:
            if shifted_pos[1] < user_pos[1] or \
                    shifted_pos[1] == user_pos[1] and shifted_pos[0] < user_pos[0]:
                top = shifted_pos
        await self._cut_selected_text(top, new_pos)
        await self._history_handler.correct_history_on_undo_paste(username, op_cnt + 1 if shifted_pos else op_cnt)
        if shifted_pos:
            await self._history_handler.correct_history_on_undo_cut(username, op_cnt)
        await self._correct_all_frames_and_pos_on_cut(username, top, new_pos)
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        await self._set_user_pos(username, user_pos, shifted_pos)

    async def _make_pos_correct_after_paste(self, action_pos, pos, shifted_pos, args):
        text = args[4]
        return await self._make_pos_correct_on_insert(
            action_pos,
            await self._get_bot_pos_on_insert(action_pos, text),
            pos, shifted_pos)

    @_handle_edit_decorator(_undo_paste, '_make_paste', _make_pos_correct_after_paste)
    async def _make_paste(self, username, user_pos, shifted_pos, text_to_paste):
        new_pos = await self._insert(text_to_paste, self.user_positions[username])
        await self._history_handler.new_text_save_history(username, user_pos, new_pos)
        async with self._action_stack_m:
            self._action_stack_by_user[username][-1][1]['new_pos'] = new_pos
        async with self._users_pos_m:
            self.user_positions[username] = new_pos

    @_after_edit_corrector_decor
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

    async def _undo_user_wrote_char(self, username, user_pos, op_cnt, shifted_pos=None, text_cut=None):
        top = user_pos
        bot = await self._shift_pos_right(user_pos)
        await self._cut_selected_text(top, bot)
        await self._correct_all_frames_and_pos_on_cut(username, top, bot)
        await self._history_handler.correct_history_on_undo_paste(username, op_cnt + 1 if shifted_pos else op_cnt)
        if shifted_pos:
            top, bot = await self._get_correct_top_bot_orientation(user_pos, shifted_pos)
            await self._correct_all_frames_and_pos_on_insert(username, top, bot)
            await self._history_handler.correct_history_on_undo_cut(username, op_cnt)
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        await self._set_user_pos(username, user_pos, shifted_pos)

    async def _make_pos_correct_after_write(self, action_pos, pos, shifted_pos, args):
        if shifted_pos:
            if action_pos[1] == shifted_pos[1] and action_pos[0] <= shifted_pos[0]:
                shifted_pos = (shifted_pos[0] + 1, shifted_pos[1])
        if action_pos[1] == pos[1] and action_pos[0] <= pos[0]:
            pos = (pos[0] + 1, pos[1])
        return (pos, shifted_pos)

    @_handle_edit_decorator(_undo_user_wrote_char, '_make_write_char',
                            _make_pos_correct_after_write)
    async def _make_write_char(self, username, user_pos, shifted_pos, char):
        user_x, user_y = user_pos
        await self._history_handler.new_text_save_history(
            username, user_pos, await self._shift_pos_right(user_pos))
        async with self._text_m:
            if user_y == len(self.text_lines):
                self.text_lines.append(char)
            else:
                self.text_lines[user_y] = self.text_lines[user_y][:user_x] + \
                    char + self.text_lines[user_y][user_x:]
        await self.user_pos_shifted_right(username)

    @_after_edit_corrector_decor
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

    async def _undo_delete_char(self, username, text_cut, user_pos, op_cnt, shifted_pos=None, line_cut_pos=None):
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        if shifted_pos:
            top, bot = await self._get_correct_top_bot_orientation(user_pos, shifted_pos)
            await self._correct_all_frames_and_pos_on_insert(username, top, bot)
        else:
            if text_cut == '\n':
                top = line_cut_pos
                bot = await self._get_bot_pos_on_insert(line_cut_pos, '\n')
                await self._insert(text_cut, line_cut_pos)
                await self._correct_all_frames_and_pos_on_insert(
                    username, top,
                    bot)
            else:
                top = await self._shift_pos_left(user_pos)
                bot = user_pos
                await self._insert(text_cut, top)
                await self._correct_all_frames_and_pos_on_insert(
                    username,
                    top, bot)
        await self._history_handler.correct_history_on_undo_cut(username, op_cnt)
        await self._set_user_pos(username, user_pos, shifted_pos)

    async def _make_pos_correct_after_del(self, action_pos, user_pos, shifted_pos, args):
        if args[3]:
            return (user_pos, shifted_pos)
        if shifted_pos:
            if action_pos[0] == 0 and action_pos[1] > 0:
                if action_pos[1] < shifted_pos[1]:
                    shifted_pos = (shifted_pos[0], shifted_pos[1] - 1)
                elif action_pos[1] == shifted_pos[1]:
                    shifted_pos = (
                        len(self.text_lines[action_pos[1] - 1]) + shifted_pos[0], shifted_pos[1] - 1)
            elif action_pos[1] == shifted_pos[1] and shifted_pos[0] >= action_pos[0]:
                shifted_pos = await self._shift_pos_left(shifted_pos)
            pass
        if action_pos[0] == 0 and action_pos[1] > 0:
            if action_pos[1] < user_pos[1]:
                user_pos = (user_pos[0], user_pos[1] - 1)
            elif action_pos[1] == user_pos[1]:
                user_pos = (
                    len(self.text_lines[action_pos[1] - 1]) + user_pos[0], user_pos[1] - 1)
        elif action_pos[1] == user_pos[1] and user_pos[0] >= action_pos[0]:
            user_pos = await self._shift_pos_left(user_pos)
        return (user_pos, shifted_pos)

    @_handle_edit_decorator(_undo_delete_char, '_make_delete_char', _make_pos_correct_after_del)
    async def _make_delete_char(self, username, user_pos, shifted_pos):
        if shifted_pos:
            return
        self._action_stack_by_user[username][-1][1]['text_cut'] = await self._get_range(
            await self._shift_pos_left(user_pos), user_pos)
        if self._action_stack_by_user[username][-1][1]['text_cut'] == '\n':
            self._action_stack_by_user[username][-1][1]['line_cut_pos'] = await self._shift_pos_left(user_pos)
        await self._history_handler.user_cut_save_history(
            username, self.text_lines, await self._shift_pos_left(user_pos), user_pos)
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
        await self._set_user_pos(username, await self._shift_pos_left(user_pos))

    @_after_edit_corrector_decor
    async def user_deleted_char(self, username):
        async with self._action_stack_m:
            self._reverted_action_stack_by_user[username].clear()
        await self._make_delete_char(
            username, self.user_positions[username],
            self.shift_user_positions[username] if username in self.shift_user_positions
            else None)

    async def _undo_new_line(self, username, user_pos, op_cnt, shifted_pos=None, text_cut=None):
        top = user_pos
        bot = (0, user_pos[1] + 1)
        await self._cut_selected_text(top, bot)
        await self._history_handler.correct_history_on_undo_cut(username, op_cnt + 1 if shifted_pos else op_cnt)
        await self._correct_all_frames_and_pos_on_cut(username, top, bot)
        if shifted_pos:
            top, bot = await self._get_correct_top_bot_orientation(user_pos, shifted_pos)
            await self._correct_all_frames_and_pos_on_insert(username, top, bot)
            await self._history_handler.correct_history_on_undo_cut(username, op_cnt)
        await self._undo_selected_cut(username, user_pos, shifted_pos, text_cut)
        await self._set_user_pos(username, user_pos, shifted_pos)

    # returns (corrected_user_pos, corrected_user_shift_pos)

    async def _make_pos_correct_after_new_line(self, action_pos, user_pos, shifted_pos, args):
        if shifted_pos:
            top, bot = await self._get_correct_top_bot_orientation(
                user_pos, shifted_pos)
            top_is_user_pos = top == user_pos
            if action_pos[1] < top[1]:
                top = (top[0], top[1] + 1)
                bot = (bot[0], bot[1] + 1)
            if action_pos[1] == top[1] and top[0] > action_pos[0]:
                if bot[1] == top[1]:
                    bot = (bot[0] - action_pos[0], bot[1] + 1)
                else:
                    bot = (bot[0], bot[1] + 1)
                top = (top[0] - action_pos[0], top[1] + 1)
            if await self._is_pos_in_range(action_pos, top, bot):
                if bot[1] == action_pos[1]:
                    bot = (bot[0] - action_pos[0], bot[1] + 1)
                else:
                    bot = (bot[0], bot[1] + 1)
            return (top, bot) if top_is_user_pos else (bot, top)
        if action_pos[1] < user_pos[1]:
            user_pos = (user_pos[0], user_pos[1] + 1)
        elif action_pos[1] == user_pos[1] and user_pos[0] > action_pos[0]:
            user_pos = (user_pos[0] - action_pos[0], user_pos[1] + 1)
        return (user_pos, shifted_pos)

    @_handle_edit_decorator(_undo_new_line, '_make_new_line',
                            _make_pos_correct_after_new_line)
    async def _make_new_line(self, username, user_pos, shifted_pos):
        user_x, user_y = user_pos
        bot = (0, user_y + 1)
        await self._history_handler.new_text_save_history(username, user_pos, bot)
        async with self._text_m:
            self.text_lines.insert(user_y, "")
            self.text_lines[user_y] = self.text_lines[user_y + 1][:user_x]
            self.text_lines[user_y + 1] = self.text_lines[user_y + 1][user_x:]
        async with self._users_pos_m:
            self.user_positions[username] = bot

    @_after_edit_corrector_decor
    async def user_added_new_line(self, username):
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
                [redo_func, redo_args])
        await revert_func(**revert_kwargs)

    async def redo(self, username):
        if len(self._reverted_action_stack_by_user[username]) == 0:
            return
        async with self._action_stack_m:
            redo_func, redo_args = \
                self._reverted_action_stack_by_user[username].pop()
        await redo_func(*redo_args)

    async def save_changes_history(self):
        if not self._file_path:
            return
        await self._history_handler.session_ended()
