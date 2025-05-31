import unittest
import curses
from unittest.mock import MagicMock, patch
from view import View


class TestView(unittest.TestCase):
    def setUp(self):
        self.mock_stdscr = MagicMock()
        self.mock_stdscr.getmaxyx.return_value = (24, 80)

        # Mock all curses functions
        self.curs_set_patcher = patch('curses.curs_set')
        self.start_color_patcher = patch('curses.start_color')
        self.init_pair_patcher = patch('curses.init_pair')
        self.color_pair_patcher = patch('curses.color_pair')

        self.mock_curs_set = self.curs_set_patcher.start()
        self.mock_start_color = self.start_color_patcher.start()
        self.mock_init_pair = self.init_pair_patcher.start()
        self.mock_color_pair = self.color_pair_patcher.start()
        self.mock_color_pair.return_value = 0  # Simplify color handling

        self.view = View(self.mock_stdscr, "owner")

        # Reset mocks after setup
        self.mock_stdscr.reset_mock()
        self.mock_init_pair.reset_mock()
        self.mock_color_pair.reset_mock()

    def tearDown(self):
        self.curs_set_patcher.stop()
        self.start_color_patcher.stop()
        self.init_pair_patcher.stop()
        self.color_pair_patcher.stop()

    def test_init(self):
        self.assertEqual(self.mock_curs_set.call_count, 1)
        self.mock_curs_set.assert_any_call(0)
        self.assertEqual(self.view._owner_username, "owner")
        self.assertEqual(self.view._offset_y, 0)
        self.assertEqual(self.view._offset_x, 0)

    def test_init_colors(self):
        # Re-initialize colors to count calls
        self.view._init_colors()

        # Verify color pairs initialization
        self.assertEqual(self.mock_init_pair.call_count, 7)
        self.mock_init_pair.assert_any_call(
            1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        self.mock_init_pair.assert_any_call(
            2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        self.mock_init_pair.assert_any_call(
            3, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        self.mock_init_pair.assert_any_call(
            4, curses.COLOR_BLACK, curses.COLOR_CYAN)
        self.mock_init_pair.assert_any_call(
            5, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        self.mock_init_pair.assert_any_call(
            6, curses.COLOR_BLACK, curses.COLOR_GREEN)
        self.mock_init_pair.assert_any_call(
            7, curses.COLOR_BLACK, curses.COLOR_RED)

    def test_correct_offset_by_owner_pos(self):
        # Test no change
        self.view._correct_offset_by_owner_pos(10, 10)
        self.assertEqual(self.view._offset_x, 0)
        self.assertEqual(self.view._offset_y, 0)

        # Test right overflow
        self.view._correct_offset_by_owner_pos(90, 10)
        self.assertEqual(self.view._offset_x, 12)

        # Test left underflow
        self.view._offset_x = 20
        self.view._correct_offset_by_owner_pos(10, 10)
        self.assertEqual(self.view._offset_x, 10)

        # Test bottom overflow
        self.view._correct_offset_by_owner_pos(10, 30)
        self.assertEqual(self.view._offset_y, 10)

        # Test top underflow
        self.view._offset_y = 20
        self.view._correct_offset_by_owner_pos(10, 10)
        self.assertEqual(self.view._offset_y, 10)

    def test_draw_users_colors(self):
        users = ["user1", "user2", "user3"]
        self.mock_stdscr.addstr.reset_mock()

        self.view._draw_users_colors(users)

        # Verify user color assignments
        self.assertEqual(self.view._user_color_index["user1"], 2)
        self.assertEqual(self.view._user_color_index["user2"], 3)
        self.assertEqual(self.view._user_color_index["user3"], 4)

        # Verify addstr calls
        self.assertGreater(self.mock_stdscr.addstr.call_count, len(users) * 3)

    def test_draw_single_selected_line(self):
        text_lines = ["line1", "line2", "line3"]
        self.mock_stdscr.addstr.reset_mock()

        # Valid call
        self.view._draw_single_selected_line(text_lines, 0, 0, 1, 3)
        self.mock_stdscr.addstr.assert_called_once_with(1, 1, "in", 0)

        # With x-offset
        self.mock_stdscr.addstr.reset_mock()
        self.view._offset_x = 2
        self.view._draw_single_selected_line(text_lines, 0, 0, 1, 3)
        self.mock_stdscr.addstr.assert_called_once_with(1, 0, "n", 0)

        # Out of bounds
        self.mock_stdscr.addstr.reset_mock()
        self.view._offset_x = 10
        self.view._draw_single_selected_line(text_lines, 0, 0, 1, 3)
        self.mock_stdscr.addstr.assert_not_called()

    def test_paint_range(self):
        text_lines = ["line1", "line2", "line3"]
        self.mock_stdscr.addstr.reset_mock()

        # Single line
        self.view._paint_range(text_lines, 0, (1, 1), (3, 1))
        self.assertEqual(self.mock_stdscr.addstr.call_count, 1)

        # Multi-line
        self.mock_stdscr.addstr.reset_mock()
        self.view._paint_range(text_lines, 0, (1, 0), (3, 2))
        self.assertEqual(self.mock_stdscr.addstr.call_count, 3)

    def test_draw_user_shift_pos(self):
        text_lines = ["line1", "line2", "line3"]
        self.view._user_color_index = {"user1": 2}
        self.mock_stdscr.addstr.reset_mock()

        self.view._draw_user_shift_pos(text_lines, "user1", (1, 1), (3, 1))
        self.mock_stdscr.addstr.assert_called()

    def test_draw_user_positions(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"user1": (1, 1), "user2": (2, 2)}
        users_shift_pos = {"user1": (3, 1)}
        self.view._user_color_index = {"user1": 2, "user2": 3}
        self.mock_stdscr.addstr.reset_mock()

        self.view._draw_user_positions(
            text_lines, user_positions, users_shift_pos)
        self.assertGreater(self.mock_stdscr.addstr.call_count, 1)

    def test_draw_changes(self):
        text_lines = ["line1", "line2", "line3"]
        changes_frames = [
            ("insert", (1, 1), (3, 1)),
            ("delete", (0, 0), (2, 0))
        ]
        self.mock_stdscr.addstr.reset_mock()

        self.view._draw_changes(text_lines, changes_frames)
        self.assertEqual(self.mock_stdscr.addstr.call_count, 2)

    def test_draw_text(self):
        text_lines = ["line1", "line2", "line3"]
        user_positions = {"owner": (1, 1), "user2": (2, 2)}
        users = ["owner", "user2"]
        self.mock_stdscr.addstr.reset_mock()

        self.view.draw_text(text_lines, user_positions, users, {})
        self.assertGreater(self.mock_stdscr.addstr.call_count, 5)


if __name__ == '__main__':
    unittest.main()
