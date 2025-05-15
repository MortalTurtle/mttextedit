import datetime
import os
import shutil


class HistoryHandler:
    _HISTORY_FILE_PATH = "/tmp/lib/mttext/history/"
    _CACHE_PATH = "/tmp/lib/mttext/cache/"
    _BASE_CACHE_PATH = _CACHE_PATH + 'base.cache'
    _CHANGES_CACHE_PATH = _CACHE_PATH + 'changes.cache'
    _changes_frames = []
    _deleted_lines = []
    _modified_lines = {}

    def __init__(self, file_path=None):
        if not file_path:
            return
        self._file_path = file_path
        file_name = file_path[file_path.rfind("/"):]
        self._HISTORY_FILE_PATH += file_name + '/'
        os.makedirs(os.path.dirname(self._HISTORY_FILE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(self._CACHE_PATH), exist_ok=True)
        self._save_base_version()

    async def _is_pos_in_range(self, pos, top, bot):
        return top[1] < pos[1] and pos[1] < bot[1] or \
            top[1] == pos[1] and top[0] < pos[0] and \
            (bot[1] > pos[1] or bot[1] == pos[1] and pos[0] < bot[0]) or \
            bot[1] == pos[1] and bot[0] > pos[0] and \
            (top[1] < pos[1] or top[1] == pos[1] and top[0] < pos[0])

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

    # TODO: correct all other changes

    async def user_cut_save_history(self, username, text_lines, top, bot):
        for frame in self._changes_frames:
            type, frame_top, frame_bot = frame
            if type == 'cut':
                frame[1] = await self._make_pos_correct_after_cut(top, bot, frame_top)
            if self._is_pos_in_range(frame_top) or self._is_pos_in_range(frame_bot, top, bot):
                pass
        self._changes_frames.append(
            ['cut', top, bot, await self._get_range(top, bot)])

    async def correct_history_on_undo_cut(self, username, text_lines, top, bot):
        pass

    async def new_text_save_history(self, username, top, bot):
        self._changes_frames.append(
            ['insert', top, bot]
        )

    async def correct_history_on_undo_paste(self, username, top, bot):
        pass

    def _save_base_version(self):
        with open(self._file_path, 'r') as f:
            filetext = f.read()
            with open(self._BASE_CACHE_PATH, 'w') as f:
                f.write(filetext)

    # rewrite using new changes history system
    async def _save_changes(self, text_lines):
        with open(self._BASE_CACHE_PATH, 'r') as f:
            base = f.read()
        base_lines = base.split('\n')
        changes = []
        with open(self._CHANGES_CACHE_PATH, 'w') as f:
            for change in changes:
                f.write(change)

    async def save_file(self, text_lines):
        if self._file_path == None:
            return
        await self._save_changes(text_lines)
        with open(self._file_path, "w") as f:
            text = "\n".join(text_lines)
            f.write(text)

    async def session_ended(self):
        if not self._file_path:
            return
        session_end = datetime.datetime.now()
        with open(self._CHANGES_CACHE_PATH, "r") as f:
            changes = f.readlines()
        with open(self._HISTORY_FILE_PATH + str(session_end) + '.cache', 'w') as f:
            f.write('\n'.join(changes))
        shutil.copy(self._file_path, self._HISTORY_FILE_PATH +
                    str(session_end) + '.o.cache')
        os.remove(self._BASE_CACHE_PATH)
        os.remove(self._CHANGES_CACHE_PATH)
