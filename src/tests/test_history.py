import unittest
from unittest.mock import patch,  mock_open
import os
import shutil
from core.history_handler import HistoryHandler


class TestHistoryHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.file_path = "/tmp/test_file.txt"
        self.handler = HistoryHandler(self.file_path)
        self.handler._last_edited_by = []  # Очищаем список перед каждым тестом

        # Создаем временные директории
        os.makedirs(self.handler._HISTORY_DIR_PATH, exist_ok=True)
        os.makedirs(self.handler._CACHE_PATH, exist_ok=True)

    def tearDown(self):
        # Очищаем временные файлы
        if os.path.exists(self.handler._CACHE_PATH):
            shutil.rmtree(self.handler._CACHE_PATH)
        if os.path.exists(self.handler._HISTORY_DIR_PATH):
            shutil.rmtree(self.handler._HISTORY_DIR_PATH)

    async def test_stop_view(self):
        self.handler.stop_view()
        self.assertTrue(self.handler.stop)

    @patch("builtins.open", new_callable=mock_open)
    async def test_load_blame_with_file(self, mock_open):
        mock_open().readlines.return_value = ["author1\n", "author2\n"]
        text_lines = ["line1", "line2"]
        self.handler.load_blame(
            text_lines, "default_user", "hist_file", "filename")
        self.assertEqual(self.handler._last_edited_by, ["author1", "author2"])

    @patch("builtins.open", side_effect=OSError)
    async def test_load_blame_with_exception(self, mock_open):
        text_lines = ["line1", "line2", "line3"]
        self.handler.load_blame(text_lines, "default_user")
        self.assertEqual(self.handler._last_edited_by, ["default_user"] * 3)

    async def test_load_blame_without_file(self):
        text_lines = ["line1", "line2", "line3"]
        self.handler.load_blame(text_lines, "default_user")
        self.assertEqual(self.handler._last_edited_by, ["default_user"] * 3)

    async def test_is_pos_in_range_edge_cases(self):
        test_cases = [
            # Точка совпадает с началом диапазона
            ((1, 1), (1, 1), (3, 3), True),
            # Точка совпадает с концом диапазона
            ((3, 3), (1, 1), (3, 3), True),
            # Диапазон нулевой длины
            ((2, 2), (2, 2), (2, 2), True),
            # Точка перед началом по строке
            ((0, 0), (1, 1), (3, 3), False),
            # Точка после конца по строке
            ((4, 4), (1, 1), (3, 3), False),
        ]

        for pos, top, bot, expected in test_cases:
            result = await self.handler._is_pos_in_range(pos, top, bot)
            self.assertEqual(result, expected,
                             f"Failed for {pos}, {top}, {bot}")

    async def test_make_pos_correct_after_cut_edge_cases(self):
        test_cases = [
            # Точка в начале вырезанной области
            ((2, 1), (2, 1), (5, 2), (2, 1)),
            # Точка в конце вырезанной области
            ((5, 2), (2, 1), (5, 2), (2, 1)),
            # Точка на той же строке после вырезания
            ((7, 2), (2, 1), (5, 2), (4, 1)),
        ]

        for pos, top, bot, expected in test_cases:
            result = await self.handler._make_pos_correct_after_cut(
                top, bot, pos)
            self.assertEqual(result, expected)

    async def test_cut_selected_edge_cases(self):
        # Вырезание пустого диапазона
        text_lines = ["Hello World"]
        result = await self.handler._cut_selected((5, 0), (5, 0), text_lines)
        self.assertEqual(result, ["Hello World"])

        # Вырезание всего текста
        result = await self.handler._cut_selected((0, 0), (11, 0), text_lines)
        self.assertEqual(result, [""])

        # Вырезание нескольких строк полностью (до начала последней строки)
        text_lines = ["Line 1", "Line 2", "Line 3"]
        result = await self.handler._cut_selected((0, 0), (0, 2), text_lines)
        self.assertEqual(result, ["Line 3"])

    async def test_get_range_edge_cases(self):
        # Пустой диапазон
        text_lines = ["Hello World"]
        result = await self.handler._get_range(text_lines, (5, 0), (5, 0))
        self.assertEqual(result, "")

        # Диапазон в обратном порядке
        result = await self.handler._get_range(text_lines, (11, 0), (6, 0))
        self.assertEqual(result, "World")

        # Получение всего текста
        result = await self.handler._get_range(text_lines, (0, 0), (11, 0))
        self.assertEqual(result, "Hello World")

    async def test_normalize_pos_edge_cases(self):
        test_cases = [
            # Отрицательные координаты
            ((-5, -2), (3, 1), (-5, -3)),
            # Нулевое смещение
            ((5, 2), (0, 0), (5, 2)),
        ]

        for pos, offset, expected in test_cases:
            result = await self.handler._normalize_pos(pos, offset)
            self.assertEqual(result, expected)

    async def test_user_cut_save_history_empty_text(self):
        text_lines = ["Line 1", "Line 2", "Line 3"]
        op_cnt = await self.handler.user_cut_save_history(
            "user", text_lines, (0, 0), (0, 0))
        self.assertEqual(op_cnt, 1)
        self.assertEqual(self.handler._changes_frames_by_op[0][3], "")

    async def test_new_text_save_history_invalid_range(self):
        op_cnt = await self.handler.new_text_save_history(
            "user", (5, 5), (0, 0))
        self.assertEqual(op_cnt, 1)
        self.assertEqual(self.handler._changes_frames_by_op[0][1], (5, 5))
        self.assertEqual(self.handler._changes_frames_by_op[0][2], (0, 0))

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists", return_value=False)
    async def test_save_base_version_file_not_found(
            self, mock_exists, mock_open):
        self.handler._save_base_version()
        mock_open.assert_called_with(self.handler._BASE_CACHE_PATH, 'w')

    @patch("builtins.open", new_callable=mock_open, read_data="invalid_data")
    async def test_read_changes_invalid_format(self, mock_open):
        await self.handler._read_changes("changes_file")
        self.assertEqual(len(self.handler._changes_frames), 0)

    async def test_currect_frame_and_op_on_cut_insert_type(self):
        """Тест коррекции фреймов типа 'insert' при вырезании"""
        frame = ['insert', (3, 2), (5, 4), "user"]
        result = await self.handler._currect_frame_and_op_on_cut(
            frame, (1, 1), (7, 5), "cut text"
        )
        # Ожидаем, что позиции будут скорректированы
        self.assertEqual(result, [(1, 1), (9, 1), "cut text"])

    async def test_constructor_without_file_path(self):
        handler = HistoryHandler()
        self.assertIsNone(handler._file_path)
        self.assertEqual(handler._HISTORY_DIR_PATH,
                         "/tmp/lib/mttext/history/")
        self.assertEqual(handler._CACHE_PATH, "/tmp/lib/mttext/cache/")

    @patch("shutil.copy")
    @patch("os.listdir", return_value=[])
    async def test_save_file_no_history_files(self, mock_listdir, mock_copy):
        text_lines = ["line1", "line2"]
        with patch("builtins.open", new_callable=mock_open):
            await self.handler.save_file(text_lines)
        mock_copy.assert_called()

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.remove")
    async def test_session_ended_no_changes(self, mock_remove, mock_open):
        # Без изменений
        self.handler._changes_frames = []

        # Создаем временный файл изменений
        changes_path = self.handler._CHANGES_CACHE_PATH
        os.makedirs(os.path.dirname(changes_path), exist_ok=True)
        with open(changes_path, 'w') as f:
            f.write("test changes")

        await self.handler.session_ended()

        # Проверяем, что файл изменений удален
        mock_remove.assert_called_with(self.handler._CHANGES_CACHE_PATH)


if __name__ == "__main__":
    unittest.main()
