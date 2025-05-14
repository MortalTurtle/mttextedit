import datetime
import os
import shutil


class FileHandler:
    _HISTORY_FILE_PATH = "/tmp/lib/mttext/history/"
    _CACHE_PATH = "/tmp/lib/mttext/cache/"
    _BASE_CACHE_PATH = _CACHE_PATH + 'base.cache'
    _CHANGES_CACHE_PATH = _CACHE_PATH + 'changes.cache'

    def __init__(self, file_path=None):
        self._file_path = file_path
        file_name = file_path[file_path.rfind("/"):]
        self._HISTORY_FILE_PATH += file_name + '/'
        os.makedirs(os.path.dirname(self._HISTORY_FILE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(self._CACHE_PATH), exist_ok=True)
        self._save_base_version()

    def _save_base_version(self):
        with open(self._file_path, 'r') as f:
            filetext = f.read()
            with open(self._BASE_CACHE_PATH, 'w') as f:
                f.write(filetext)

    async def _save_changes(self, text_lines):
        with open(self._BASE_CACHE_PATH, 'r') as f:
            base = f.read()
        base_lines = base.split('\n')
        changes = []
        for y in range(len(base_lines)):
            if y >= len(text_lines):
                for dy in range(y, len(base_lines)):
                    changes.append(f"-dl {dy}")  # line deleted
                break
            x = 0
            base_len = len(base_lines[y])
            actual_len = len(text_lines[y])
            while x < base_len:
                if x >= actual_len:
                    # text deleted
                    changes.append(f"-dt {y} {x} {base_lines[y][x:]}")
                    break
                if text_lines[y][x] == base_lines[y][x]:
                    x += 1
                    continue
                dx = 1
                while x + dx < min(base_len, actual_len) and \
                        base_lines[y][x + dx] != text_lines[y][x + dx]:
                    dx += 1
                changes.append(f"-mt {y} {x} {x + dx - 1}")  # text modified
                x += dx
            if actual_len > base_len:
                changes.append(
                    f"-at {y} {base_len}")  # added text
        if len(text_lines) > len(base_lines):
            for y in range(len(base_lines), len(text_lines)):
                changes.append(f'-nl {y} ')  # line added
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
