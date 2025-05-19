import asyncio
import datetime
import os
import shutil
import time
from view import View


class HistoryHandler:
    _HISTORY_DIR_PATH = "/tmp/lib/mttext/history/"
    _BLAME_DIR_PATH = "/tmp/lib/mttext/blame/"
    _CACHE_PATH = "/tmp/lib/mttext/cache/"
    _BASE_CACHE_PATH = _CACHE_PATH + 'base.cache'
    _CHANGES_CACHE_PATH = _CACHE_PATH + 'changes.cache'
    _changes_frames = []
    _last_edited_by = []
    _DELIMITER = b' \n\x1E'
    _op_cnt = 0
    _file_path = None

    def __init__(self, file_path=None):
        self._session_start = datetime.datetime.now()
        if not file_path:
            return
        self._file_path = file_path
        self._file_name = file_path[file_path.rfind("/"):]
        self._HISTORY_DIR_PATH += self._file_name + '/'
        os.makedirs(os.path.dirname(self._HISTORY_DIR_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(self._CACHE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(self._BLAME_DIR_PATH), exist_ok=True)

    def load_blame(self, text_lines, owner_username):
        try:
            with open(self._BLAME_DIR_PATH + self._file_name, 'r') as f:
                for line in f.readlines():
                    self._last_edited_by.append(line)
        except:
            for line in text_lines:
                self._last_edited_by.append(owner_username)

    async def _is_pos_in_range(self, pos, top, bot):
        return top[1] < pos[1] and pos[1] < bot[1] or \
            top[1] == pos[1] and top[0] <= pos[0] and \
            (bot[1] > pos[1] or bot[1] == pos[1] and pos[0] <= bot[0]) or \
            bot[1] == pos[1] and bot[0] >= pos[0] and \
            (top[1] < pos[1] or top[1] == pos[1] and top[0] <= pos[0])

    async def _make_pos_correct_on_insert(self, action_top, action_bot, pos):
        if pos[1] == action_top[1] and pos[0] >= action_top[0]:
            pos = (pos[0] + action_bot[0] - action_top[0],
                   pos[1] + action_bot[1] - action_top[1])
        elif pos[1] > action_top[1]:
            pos = (pos[0], pos[1] + action_bot[1] - action_top[1])
        return pos

    async def _make_pos_correct_after_cut(self, top, bot, pos):
        if await self._is_pos_in_range(pos, top, bot):
            pos = top
        if pos[1] > bot[1]:
            pos = (pos[0], pos[1] - (bot[1] - top[1]))
        if pos[1] == bot[1] and pos[0] >= bot[0]:
            pos = (pos[0] - (bot[0] - top[0]), top[1])
        return pos

    async def _cut_selected(self, top, bot, text_lines):
        bot_x, bot_y = bot
        top_x, top_y = top
        if bot_y == top_y:
            text_lines[bot_y] = text_lines[bot_y][:top_x] + \
                text_lines[bot_y][bot_x:]
        else:
            text_lines[top_y] = text_lines[top_y][:top_x] + \
                text_lines[bot_y][bot_x:]
            text_lines.pop(bot_y)
        for y in range(bot_y - 1, top_y, -1):
            text_lines.pop(y)
        return text_lines

    async def _get_range(self, text_lines, top, bot):
        if bot[1] < top[1] or \
                bot[1] == top[1] and bot[0] < top[0]:
            t = top
            top = bot
            bot = t
        top_x, top_y = top
        bot_x, bot_y = bot
        if bot_y == top_y:
            return text_lines[bot_y][top_x:bot_x]
        t = '' if bot_y - \
            top_y <= 1 else '\n'.join(text_lines[top_y + 1: bot_y]) + '\n'
        return text_lines[top_y][top_x:] + '\n' + \
            t + \
            text_lines[bot_y][:bot_x]

    async def _normalize_pos(self, pos, offset_pos):
        if pos[1] == offset_pos[1]:
            pos = (pos[0] - offset_pos[0], pos[1] - offset_pos[1])
        else:
            pos = (pos[0], pos[1] - offset_pos[1])
        return pos

    async def _currect_frame_and_op_on_cut(self, frame, top, bot, cut_text: str):
        cut_lines = cut_text.split('\n')
        if len(cut_lines) == 1:
            bot = (len(cut_lines[0]) + top[0], top[1])
        else:
            bot = (len(cut_lines[-1]), top[1] + len(cut_lines) - 1)
        type, frame_top, frame_bot, *rest = frame
        if type == 'cut':
            return (top, bot, cut_text)
        if await self._is_pos_in_range(top, frame_top, frame_bot) and await self._is_pos_in_range(bot, frame_top, frame_bot):
            frame[2] = await self._make_pos_correct_after_cut(top, bot, frame_bot)
            return [(0, 0), (0, 0), '']
        elif await self._is_pos_in_range(frame_top, top, bot) and await self._is_pos_in_range(frame_bot, top, bot):
            frame[1] = frame[2]
            cut_top = frame_top
            cut_bot = frame_bot
            cut_top = await self._normalize_pos(cut_top, top)
            cut_bot = await self._normalize_pos(cut_bot, top)
            return [top, bot, '\n'.join(await self._cut_selected(cut_top, cut_bot, cut_text.split('\n')))]
        elif await self._is_pos_in_range(frame_top, top, bot):
            frame[1] = top
            frame[2] = await self._make_pos_correct_after_cut(top, bot, frame_bot)
            cut_top = top
            cut_bot = frame_top
            cut_bot = await self._normalize_pos(cut_bot, top)
            cut_top = (0, 0)
            bot = frame_top
            return [top, bot, '\n'.join(await self._get_range(cut_lines, cut_top, cut_bot))]
        elif await self._is_pos_in_range(frame_bot, top, bot):
            frame[2] = top
            cut_top = frame_bot
            cut_bot = bot
            cut_top = await self._normalize_pos(cut_top, top)
            cut_bot = await self._normalize_pos(cut_bot, top)
            bot = await self._make_pos_correct_after_cut(top, frame_bot, bot)
            return [top, bot, '\n'.join(await self._get_range(cut_lines, cut_top, cut_bot))]
        else:
            frame[1] = await self._make_pos_correct_on_insert(top, bot, frame_top)
            frame[2] = await self._make_pos_correct_on_insert(top, bot, frame_bot)
        return [top, bot, cut_text]

    async def user_cut_save_history(self, username, text_lines, top, bot):
        if not self._file_path:
            return
        self._op_cnt += 1
        self._changes_frames.append(
            ['cut', top, bot, await self._get_range(text_lines, top, bot), username])
        return self._op_cnt

    async def correct_history_on_undo_cut(self, username, op_cnt):
        if not self._file_path:
            return
        self._changes_frames.pop(op_cnt - 1)

    async def new_text_save_history(self, username, top, bot):
        if not self._file_path:
            return
        self._op_cnt += 1
        self._changes_frames.append(
            ['insert', top, bot, username]
        )
        return self._op_cnt

    async def correct_history_on_undo_paste(self, username, op_cnt):
        if not self._file_path:
            return
        self._changes_frames.pop(op_cnt - 1)

    def _save_base_version(self):
        with open(self._file_path, 'r') as f:
            filetext = f.read()
            with open(self._BASE_CACHE_PATH, 'w') as f:
                f.write(filetext)

    async def _save_changes(self, text_lines):
        with open(self._CHANGES_CACHE_PATH, 'w') as f:
            for frame in self._changes_frames:
                frame_str = f"{frame[0]} {frame[1][0]} {frame[1][1]} {frame[2][0]} {frame[2][1]} {frame[3].replace(' ', '/s') if frame[0] == 'cut' else frame[3]} {frame[4] if frame[0] == 'cut' else ""} {self._DELIMITER}"
                f.write(frame_str)
        shutil.copy(self._file_path, self._HISTORY_DIR_PATH +
                    str(self._session_start) + '.o.cache')

    async def save_file(self, text_lines):
        if self._file_path == None:
            return
        with open(self._file_path, "w") as f:
            text = "\n".join(text_lines)
            f.write(text)
        await self._save_changes(text_lines)

    async def _read_changes(self, history_file):
        with open(history_file, 'r') as f:
            changes_text = f.read()
            changes = changes_text.split(str(self._DELIMITER))
            for change in changes:
                args = change.split(' ')
                if len(args) < 5:
                    continue
                op_type, top_x, top_y, bot_x, bot_y, *rest = args
                top = (int(top_x), int(top_y))
                bot = (int(bot_x), int(bot_y))
                self._changes_frames.append(
                    [op_type, top, bot])
                if op_type == 'cut':
                    cut_text = rest[0].replace('/s', ' ')
                    self._changes_frames[-1].append(cut_text)
                    self._changes_frames[-1].append(rest[1])
                else:
                    self._changes_frames[-1].append(rest[0])

    async def show_changes(self, filename, history_file: str, model, stdscr):
        history_file = history_file.replace('.o.cache', '.cache')
        await self._read_changes(self._HISTORY_DIR_PATH + filename + '/' + history_file)
        for i in range(len(self._changes_frames) - 1, -1, -1):
            frame = self._changes_frames[i]
            if frame[0] == 'cut':
                op_type, top, bot, cut_text, *rest = frame
                await model._insert(cut_text, top)
            else:
                continue
        await self._show_changes_view(stdscr, model)

    async def _show_changes_view(self, stdscr, model):
        view = View(stdscr, 'view_changes')
        while True:
            view.draw_text(
                model.text_lines, model.user_positions, model.users, model.shift_user_positions, self._changes_frames)
            await asyncio.sleep(0.05)
        pass

    async def session_ended(self):
        if not self._file_path:
            return
        self._changes_frames.clear()
        await self._read_changes(self._CHANGES_CACHE_PATH)
        for i in range(len(self._changes_frames) - 1, -1, -1):
            frame = self._changes_frames[i]
            if frame[0] != 'cut':
                continue
            op_type, top, bot, cut_text, *rest = frame
            for j in range(i - 1, -1, -1):
                top, bot, cut_text = await self._currect_frame_and_op_on_cut(self._changes_frames[j], top, bot, cut_text)
            for j in range(i + 1, len(self._changes_frames)):
                frame_to_correct = self._changes_frames[j]
                if frame[0] != 'cut':
                    break
                frame_to_correct[1] = await self._make_pos_correct_on_insert(top, bot, frame_to_correct[1])
                frame_to_correct[2] = await self._make_pos_correct_on_insert(top, bot, frame_to_correct[2])
            frame[1] = top
            frame[2] = bot
            frame[3] = cut_text
        # TODO: correct blame
        for frame in self._changes_frames:
            op_type, top, bot, *rest = frame
            if op_type == 'cut':
                cut_text = rest[0]
                username = rest[1]
                # self._last_edited_by[top[1]] = username
                # self._last_edited_by[bot[1]] = username
                for y in range(top[1] + 1, bot[1]):
                    # self._last_edited_by.pop(y)
                    pass
            if op_type == 'insert':
                username = rest[0]
                for y in range(top[1], bot[1] + 1):
                    pass
                    # self._last_edited_by.insert(y, username)
        with open(self._HISTORY_DIR_PATH + str(self._session_start) + '.cache', 'w') as f:
            for frame in self._changes_frames:
                frame_str = f"{frame[0]} {frame[1][0]} {frame[1][1]} {frame[2][0]} {frame[2][1]} {frame[3].replace(' ', '/s') if frame[0] == 'cut' else frame[3]} {frame[4] if frame[0] == 'cut' else ""}{self._DELIMITER}"
                f.write(frame_str)
        with open(self._HISTORY_DIR_PATH + str(self._session_start) + 'blame.cache', 'w') as f:
            for line in self._last_edited_by:
                f.write(line + '\n')
        os.remove(self._CHANGES_CACHE_PATH)
