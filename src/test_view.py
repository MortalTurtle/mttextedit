import curses
import unittest
from unittest.mock import MagicMock, patch
from view import View


class TestView(unittest.TestCase):
    def setUp(self):
        self.mock_stdscr = MagicMock()
        self.mock_stdscr.getmaxyx.return_value = (24, 80)
        # Замокировать curses и инициализировать
        with patch('curses.initscr'), \
                patch('curses.curs_set'), \
                patch('curses.start_color'), \
                patch('curses.init_pair'), \
                patch('curses.color_pair'):
            self.view = View(self.mock_stdscr, "owner")
            self.view._user_color_index = {
                "user1": 2,
                "user2": 3,
            }

    def test_init(self):
        self.assertEqual(self.view._owner_username, "owner")
        self.assertEqual(self.view._offset_y, 0)
        self.assertEqual(self.view._offset_x, 0)
        self.mock_stdscr.bkgd.assert_called_once_with(" ", 0)

    def test_init_colors(self):
        with patch('curses.start_color'), \
                patch('curses.init_pair'), \
                patch('curses.color_pair'):
            self.view._init_colors()
            curses.init_pair.assert_any_call(
                1, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair.assert_any_call(
                2, curses.COLOR_BLACK, curses.COLOR_WHITE)
            self.assertEqual(curses.init_pair.call_count, 7)

    def test_correct_offset_by_owner_pos(self):
        self.view._correct_offset_by_owner_pos(10, 10)
        self.assertEqual(self.view._offset_x, 0)
        self.assertEqual(self.view._offset_y, 0)

        self.view._correct_offset_by_owner_pos(90, 10)
        self.assertGreater(self.view._offset_x, 0)

        self.view._offset_x = 20
        self.view._correct_offset_by_owner_pos(10, 10)
        self.assertLess(self.view._offset_x, 20)

        self.view._correct_offset_by_owner_pos(10, 30)
        self.assertGreater(self.view._offset_y, 0)

        self.view._offset_y = 20
        self.view._correct_offset_by_owner_pos(10, 10)
        self.assertLess(self.view._offset_y, 20)

    def test_draw_users_colors(self):
        users = ["user1", "user2", "user3"]

        # Замокировать curses.color_pair
        with patch('curses.color_pair') as mock_color_pair:
            self.view._draw_users_colors(users)

            # Проверка, что цвета были назначены правильно
            self.assertEqual(self.view._user_color_index["user1"], 2)
            self.assertEqual(self.view._user_color_index["user2"], 3)
            self.assertEqual(self.view._user_color_index["user3"], 4)

            # Проверка, что addstr был вызван
            self.assertGreater(
                self.mock_stdscr.addstr.call_count, len(users) * 3)

            # Проверка, что color_pair был вызван с правильными аргументами
            mock_color_pair.assert_any_call(2)
            mock_color_pair.assert_any_call(3)
            mock_color_pair.assert_any_call(4)

    def test_draw_single_selected_line(self):
        text_lines = ["line1", "line2", "line3"]

        # Тестируем, когда offset_x меньше 10
        self.view._draw_single_selected_line(text_lines, 0, 1, 1, 3)
        self.mock_stdscr.addstr.assert_called()  # Ожидаем, что addstr был вызван
        self.view._offset_x = 2
        self.view._draw_single_selected_line(text_lines, 0, 1, 1, 3)
        self.mock_stdscr.addstr.assert_called()  # Ожидаем, что addstr был вызван
        self.view._offset_x = 10
        self.view._draw_single_selected_line(text_lines, 0, 1, 1, 3)
        self.mock_stdscr.addstr.assert_not_called()  # Ожидаем, что addstr не был вызван

    def test_paint_range(self):
        text_lines = ["line1", "line2", "line3"]
        # Первый вызов
        self.view._paint_range(text_lines, 0, (1, 1), (3, 1))
        self.mock_stdscr.addstr.assert_called()  # Проверяем, что addstr вызван
        # Сброс мок-объекта
        self.mock_stdscr.reset_mock()
        # Второй вызов с другим диапазоном
        self.view._paint_range(text_lines, 0, (1, 0), (3, 2))
        # Теперь проверим, что вызовов addstr не меньше 3
        self.assertGreaterEqual(self.mock_stdscr.addstr.call_count, 3)

    def test_draw_user_shift_pos(self):
        text_lines = ["line1", "line2"]
        user = "user1"
        top = (0, 0)
        bot = (1, 1)
        # задаём индекс цвета пользователя
        self.view._user_color_index = {user: 5}
        with patch('curses.color_pair') as mock_color_pair, \
                patch.object(self.view, '_paint_range') as mock_paint_range:
            mock_color_pair.return_value = 10  # фиктивный цвет
            self.view._draw_user_shift_pos(text_lines, user, top, bot)
            mock_color_pair.assert_called_once_with(5)
            mock_paint_range.assert_called_once_with(text_lines, 10, top, bot)

    def test_draw_user_positions(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"user1": (1, 1), "user2": (2, 2)}
        users_shift_pos = {"user1": (3, 1)}
        with patch('curses.color_pair') as mock_color_pair, \
                patch.object(self.view, '_draw_user_shift_pos') as mock_draw_user_shift_pos:
            mock_color_pair.side_effect = lambda x: x  # Возвращаем индекс цвета
            self.view._draw_user_positions(
                text_lines, user_positions, users_shift_pos)
            # Проверка, что _draw_user_shift_pos был вызван для user1
            mock_draw_user_shift_pos.assert_called_once_with(
                text_lines, "user1", (1, 1), (3, 1)
            )
            # Проверка, что addstr был вызван для user2
            self.mock_stdscr.addstr.assert_any_call(
                2 - self.view._offset_y, 2 - self.view._offset_x, "line2", 3)
            # Проверка, что addstr был вызван для user1 с пробелом
            self.mock_stdscr.addstr.assert_any_call(
                1 - self.view._offset_y, 1 - self.view._offset_x, " ", 2)

    def test_draw_changes(self):
        text_lines = ["line1", "line2", "line3"]
        changes_frames = [
            ("insert", (1, 1), (3, 1)),
            ("delete", (0, 0), (2, 0))
        ]
        with patch('curses.color_pair') as mock_color_pair:
            mock_color_pair.side_effect = lambda x: x  # Возвращаем индекс цвета
            self.view._draw_changes(text_lines, changes_frames)
            # Проверка, что addstr был вызван более 2 раз
            self.assertGreater(self.mock_stdscr.addstr.call_count, 2)

    def test_draw_text(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"owner": (1, 1), "user2": (2, 2)}
        users = ["owner", "user2"]
        with patch('curses.color_pair') as mock_color_pair:
            mock_color_pair.side_effect = lambda x: x  # Возвращаем индекс цвета
            self.view.draw_text(text_lines, user_positions, users, {})
            # Проверка, что addstr был вызван более 5 раз
            self.assertGreater(self.mock_stdscr.addstr.call_count, 5)

    def test_draw_blame(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"owner": (1, 1), "user2": (2, 2)}
        users = ["owner", "user2"]
        blame = ["owner", "user2", "owner"]
        # Убедитесь, что метод draw_blame существует
        if hasattr(self.view, 'draw_blame'):
            self.view.draw_blame(
                text_lines, user_positions, users, {}, blame, 10)
            # Проверка, что addstr был вызван более 5 раз
            self.assertGreater(self.mock_stdscr.addstr.call_count, 5)
        else:
            self.fail("Method draw_blame does not exist in View class.")


if __name__ == '__main__':
    unittest.main()
