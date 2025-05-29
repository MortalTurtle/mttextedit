import unittest
from unittest.mock import MagicMock, patch
from core.view import View


class TestView(unittest.TestCase):
    def setUp(self):
        self.mock_stdscr = MagicMock()
        self.mock_stdscr.getmaxyx.return_value = (24, 80)
        self.view = View(self.mock_stdscr, "owner")

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
            curses.init_pair.assert_any_call(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair.assert_any_call(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
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
        self.view._draw_users_colors(users)
        self.assertEqual(self.view._user_color_index["user1"], 2)
        self.assertEqual(self.view._user_color_index["user2"], 3)
        self.assertEqual(self.view._user_color_index["user3"], 4)
        self.assertGreater(self.mock_stdscr.addstr.call_count, len(users) * 3)

    def test_draw_single_selected_line(self):
        text_lines = ["line1", "line2", "line3"]
        self.view._draw_single_selected_line(text_lines, 0, 1, 1, 3)
        self.mock_stdscr.addstr.assert_called()

        self.view._offset_x = 2
        self.view._draw_single_selected_line(text_lines, 0, 1, 1, 3)
        self.mock_stdscr.addstr.assert_called()

        self.view._offset_x = 10
        self.view._draw_single_selected_line(text_lines, 0, 1, 1, 3)
        self.mock_stdscr.addstr.assert_not_called()

    def test_paint_range(self):
        text_lines = ["line1", "line2", "line3"]
        self.view._paint_range(text_lines, 0, (1, 1), (3, 1))
        self.mock_stdscr.addstr.assert_called()

        self.mock_stdscr.reset_mock()
        self.view._paint_range(text_lines, 0, (1, 0), (3, 2))
        self.assertGreater(self.mock_stdscr.addstr.call_count, 3)

    def test_draw_user_shift_pos(self):
        text_lines = ["line1", "line2", "line3"]
        self.view._user_color_index = {"user1": 2}
        self.view._draw_user_shift_pos(text_lines, "user1", (1, 1), (3, 1))
        self.mock_stdscr.addstr.assert_called()

    def test_draw_user_positions(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"user1": (1, 1), "user2": (2, 2)}
        users_shift_pos = {"user1": (3, 1)}
        self.view._user_color_index = {"user1": 2, "user2": 3}
        self.view._draw_user_positions(text_lines, user_positions, users_shift_pos)
        self.assertGreater(self.mock_stdscr.addstr.call_count, 2)

    def test_draw_changes(self):
        text_lines = ["line1", "line2", "line3"]
        changes_frames = [
            ("insert", (1, 1), (3, 1)),
            ("delete", (0, 0), (2, 0))
        ]
        self.view._draw_changes(text_lines, changes_frames)
        self.assertGreater(self.mock_stdscr.addstr.call_count, 2)

    def test_draw_text(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"owner": (1, 1), "user2": (2, 2)}
        users = ["owner", "user2"]
        self.view.draw_text(text_lines, user_positions, users, {})
        self.assertGreater(self.mock_stdscr.addstr.call_count, 5)

    def test_draw_blame(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"owner": (1, 1), "user2": (2, 2)}
        users = ["owner", "user2"]
        blame = ["owner", "user2", "owner"]
        self.view.draw_blame(text_lines, user_positions, users, {}, blame, 10)
        self.assertGreater(self.mock_stdscr.addstr.call_count, 5)


if __name__ == '__main__':
    unittest.main()