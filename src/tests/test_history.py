import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import shutil
from core.history_handler import HistoryHandler
from core.view import View


class TestHistoryHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.file_path = "/tmp/test_file.txt"
        with open(self.file_path, 'w') as f:
            f.write("test content")

        self.handler = HistoryHandler(self.file_path)
        self.handler._last_edited_by = []
        os.makedirs(self.handler._HISTORY_DIR_PATH, exist_ok=True)
        os.makedirs(self.handler._CACHE_PATH, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.handler._CACHE_PATH):
            shutil.rmtree(self.handler._CACHE_PATH)
        if os.path.exists(self.handler._HISTORY_DIR_PATH):
            shutil.rmtree(self.handler._HISTORY_DIR_PATH)
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

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

    async def test_make_pos_correct_on_insert(self):
        test_cases = [
            # Вставка перед позицией
            ((5, 2), (3, 1), (7, 3), (5, 4)),
            # Вставка на той же строке после позиции
            ((2, 1), (3, 1), (7, 3), (2, 1)),
            # Вставка затрагивает несколько строк
            ((3, 1), (1, 1), (5, 3), (7, 3)),
        ]

        for pos, top, bot, expected in test_cases:
            result = await self.handler._make_pos_correct_on_insert(
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

        # Вырезание нескольких строк полностью
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

    async def test_user_cut_save_history_normal(self):
        text_lines = ["Hello", "World"]
        op_cnt = await self.handler.user_cut_save_history(
            "user", text_lines, (1, 0), (3, 0))
        self.assertEqual(op_cnt, 1)
        self.assertEqual(self.handler._changes_frames_by_op[0][0], 'cut')
        self.assertEqual(self.handler._changes_frames_by_op[0][3], "el")
        self.assertEqual(self.handler._changes_frames_by_op[0][4], "user")

    async def test_new_text_save_history_invalid_range(self):
        op_cnt = await self.handler.new_text_save_history(
            "user", (5, 5), (0, 0))
        self.assertEqual(op_cnt, 1)
        self.assertEqual(self.handler._changes_frames_by_op[0][1], (5, 5))
        self.assertEqual(self.handler._changes_frames_by_op[0][2], (0, 0))

    async def test_new_text_save_history_normal(self):
        op_cnt = await self.handler.new_text_save_history(
            "user", (1, 1), (3, 2))
        self.assertEqual(op_cnt, 1)
        self.assertEqual(self.handler._changes_frames_by_op[0][0], 'insert')
        self.assertEqual(self.handler._changes_frames_by_op[0][3], "user")

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists", return_value=False)
    async def test_save_base_version_file_not_found(self, mock_exists, mock_open):
        self.handler._save_base_version()
        mock_open.assert_called_with(self.handler._BASE_CACHE_PATH, 'w')

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists", return_value=True)
    async def test_save_base_version_file_exists(self, mock_exists, mock_open):
        self.handler._save_base_version()
        mock_open.assert_called_with(self.handler._BASE_CACHE_PATH, 'w')

    @patch("builtins.open", new_callable=mock_open, read_data="invalid_data")
    async def test_read_changes_invalid_format(self, mock_open):
        await self.handler._read_changes("changes_file")
        self.assertEqual(len(self.handler._changes_frames), 0)

    @patch("builtins.open", new_callable=mock_open,
           read_data="cut 1 0 3 0 text user \n\x1E")
    async def test_read_changes_valid_format(self, mock_open):
        await self.handler._read_changes("changes_file")
        self.assertEqual(len(self.handler._changes_frames), 1)
        self.assertEqual(self.handler._changes_frames[0][0], 'cut')
        self.assertEqual(self.handler._changes_frames[0][3], "text")

    async def test_correct_history_on_undo_cut(self):
        self.handler._changes_frames_by_op = {0: ['test_frame']}
        await self.handler.correct_history_on_undo_cut("user", 1)
        self.assertEqual(len(self.handler._changes_frames_by_op), 0)

    async def test_correct_history_on_undo_paste(self):
        self.handler._changes_frames_by_op = {0: ['test_frame']}
        await self.handler.correct_history_on_undo_paste("user", 1)
        self.assertEqual(len(self.handler._changes_frames_by_op), 0)

    def test_constructor_without_file_path(self):
        handler = HistoryHandler()
        self.assertIsNone(handler._file_path)
        self.assertEqual(handler._HISTORY_DIR_PATH,
                         "/tmp/lib/mttext/history/")
        self.assertEqual(handler._CACHE_PATH, "/tmp/lib/mttext/cache/")

    def test_constructor_with_file_path(self):
        handler = HistoryHandler("/tmp/test.txt")
        self.assertEqual(handler._file_path, "/tmp/test.txt")
        self.assertIn("test.txt", handler._HISTORY_DIR_PATH)

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
        self.handler._changes_frames = []
        changes_path = self.handler._CHANGES_CACHE_PATH
        os.makedirs(os.path.dirname(changes_path), exist_ok=True)
        with open(changes_path, 'w') as f:
            f.write("test changes")
        await self.handler.session_ended()
        mock_remove.assert_called_with(self.handler._CHANGES_CACHE_PATH)

    async def test_currect_frame_and_op_on_cut_insert_type(self):
        frame = ['insert', (3, 2), (5, 4), "user"]
        result = await self.handler._currect_frame_and_op_on_cut(
            frame, (1, 1), (7, 5), "cut text"
        )
        self.assertEqual(result, [(1, 1), (9, 1), "cut text"])

    async def test_cut_selected_single_line_middle(self):
        text_lines = ["Hello World"]
        result = await self.handler._cut_selected((6, 0), (11, 0), text_lines)
        self.assertEqual(result, ["Hello "])

    async def test_cut_selected_single_line_beginning(self):
        text_lines = ["Hello World"]
        result = await self.handler._cut_selected((0, 0), (5, 0), text_lines)
        self.assertEqual(result, [" World"])

    async def test_cut_selected_single_line_end(self):
        text_lines = ["Hello World"]
        result = await self.handler._cut_selected((6, 0), (11, 0), text_lines)
        self.assertEqual(result, ["Hello "])

    async def test_cut_selected_multiple_lines_full(self):
        text_lines = ["Line 1", "Line 2", "Line 3"]
        result = await self.handler._cut_selected((0, 0), (5, 2), text_lines)
        self.assertEqual(result, [])

    async def test_cut_selected_multiple_lines_partial(self):
        text_lines = ["First line", "Second line", "Third line"]
        result = await self.handler._cut_selected((3, 0), (6, 1), text_lines)
        self.assertEqual(result, ["Firline", "Third line"])

    async def test_cut_selected_empty_range(self):
        text_lines = ["Some text"]
        result = await self.handler._cut_selected((2, 0), (2, 0), text_lines)
        self.assertEqual(result, ["Some text"])

    async def test_cut_selected_across_multiple_lines(self):
        text_lines = ["12345", "67890", "abcde"]
        result = await self.handler._cut_selected((2, 0), (4, 1), text_lines)
        self.assertEqual(result, ["12", "0", "abcde"])

    async def test_cut_selected_last_line_partial(self):
        text_lines = ["First", "Second", "Third"]
        result = await self.handler._cut_selected((1, 2), (4, 2), text_lines)
        self.assertEqual(result, ["First", "Second", "T"])

    async def test_cut_selected_first_line_partial(self):
        text_lines = ["First", "Second", "Third"]
        result = await self.handler._cut_selected((1, 0), (4, 0), text_lines)
        self.assertEqual(result, ["Ft", "Second", "Third"])

    async def test_cut_selected_reversed_range(self):
        text_lines = ["Hello World"]
        result = await self.handler._cut_selected((11, 0), (6, 0), text_lines)
        self.assertEqual(result, ["Hello "])

    @patch("builtins.open", new_callable=mock_open)
    async def test_save_changes_with_cut_operation(self, mock_open):
        self.handler._changes_frames_by_op = {
            0: ['cut', (1, 0), (3, 0), "test text", "user1"]
        }
        text_lines = ["line1", "line2"]
        await self.handler._save_changes(text_lines)
        mock_open().write.assert_called()

        @patch("builtins.open", new_callable=mock_open)
        async def test_save_changes_with_insert_operation(self, mock_open):
            self.handler._changes_frames_by_op = {
                0: ['insert', (1, 0), (3, 0), "user1"]
            }
            text_lines = ["line1", "line2"]
            await self.handler._save_changes(text_lines)
            mock_open().write.assert_called()

        async def test_show_changes_with_empty_frames(self):
            with patch.object(self.handler, '_show_changes_view') as mock_view:
                await self.handler.show_changes(
                    "test.txt", "history.cache", MagicMock(), MagicMock())
                mock_view.assert_called()

        async def test_show_blame_with_empty_users(self):
            self.handler._last_edited_by = []
            with patch.object(View, 'draw_blame') as mock_draw:
                await self.handler.show_blame(
                    "test.txt", "history.cache", MagicMock(), MagicMock())
                mock_draw.assert_called()

        @patch("os.path.exists", return_value=True)
        @patch("builtins.open", new_callable=mock_open,
               read_data="cut 1 0 3 0 test_text user1 \n\x1E")
        async def test_session_ended_with_cut_operations(self, mock_open, mock_exists):
            await self.handler.session_ended()
            self.assertEqual(len(self.handler._changes_frames), 1)

        @patch("os.path.exists", return_value=True)
        @patch("builtins.open", new_callable=mock_open,
               read_data="insert 1 0 3 0 user1 \n\x1E")
        async def test_session_ended_with_insert_operations(self, mock_open, mock_exists):
            await self.handler.session_ended()
            self.assertEqual(len(self.handler._changes_frames), 1)

        async def test_normalize_pos_with_negative_values(self):
            pos = (-5, -2)
            offset = (3, 1)
            result = await self.handler._normalize_pos(pos, offset)
            self.assertEqual(result, (-5, -3))

        async def test_make_pos_correct_on_insert_with_same_line(self):
            pos = (5, 2)
            top = (3, 2)
            bot = (7, 2)
            result = await self.handler._make_pos_correct_on_insert(top, bot, pos)
            self.assertEqual(result, (9, 2))

        async def test_make_pos_correct_after_cut_with_same_line(self):
            pos = (4, 1)
            top = (2, 1)
            bot = (5, 1)
            result = await self.handler._make_pos_correct_after_cut(top, bot, pos)
            self.assertEqual(result, (2, 1))

        async def test_get_range_with_single_line(self):
            text_lines = ["Hello World"]
            result = await self.handler._get_range(text_lines, (6, 0), (11, 0))
            self.assertEqual(result, "World")

        async def test_get_range_with_multiple_lines(self):
            text_lines = ["Line 1", "Line 2", "Line 3"]
            result = await self.handler._get_range(text_lines, (2, 0), (4, 2))
            self.assertEqual(result, "ne 1\nLine 2\nLine")

        async def test_cut_selected_with_multiple_lines(self):
            text_lines = ["Line 1", "Line 2", "Line 3"]
            result = await self.handler._cut_selected((2, 0), (4, 2), text_lines)
            self.assertEqual(result, ["Li 3"])

        async def test_user_cut_save_history_with_empty_text(self):
            op_cnt = await self.handler.user_cut_save_history(
                "user", [], (0, 0), (0, 0))
            self.assertEqual(op_cnt, 1)
            self.assertEqual(self.handler._changes_frames_by_op[0][3], "")

        async def test_new_text_save_history_with_same_positions(self):
            op_cnt = await self.handler.new_text_save_history(
                "user", (1, 1), (1, 1))
            self.assertEqual(op_cnt, 1)
            self.assertEqual(
                self.handler._changes_frames_by_op[0][0], 'insert')

        @patch("shutil.copy")
        async def test_save_file_with_empty_text(self, mock_copy):
            await self.handler.save_file([])
            mock_copy.assert_called()

        async def test_show_changes_with_real_frames(self):
            self.handler._changes_frames = [
                ['cut', (1, 0), (3, 0), "test", "user1"],
                ['insert', (2, 0), (4, 0), "user2"]
            ]
            with patch.object(self.handler, '_show_changes_view') as mock_view:
                await self.handler.show_changes(
                    "test.txt", "history.cache", MagicMock(), MagicMock())
                mock_view.assert_called()


if __name__ == "__main__":
    unittest.main()
