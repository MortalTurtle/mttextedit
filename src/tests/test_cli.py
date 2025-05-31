import unittest
from unittest.mock import patch, mock_open
import os
import sys

import core.cli as cli


class TestCLIModule(unittest.TestCase):

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch("os.makedirs")
    def test_get_permissions_not_exists(self, mock_makedirs, mock_open):
        permissions = cli.get_permissions()
        self.assertEqual(permissions, {})
        mock_makedirs.assert_called_once_with(
            os.path.dirname(cli.PERMISSION_FILE), exist_ok=True
        )

    @patch("builtins.print")
    @patch("core.cli.get_permissions",
           return_value={"user1": "rw", "user2": "r"})
    def test_list_permissions(self, mock_get, mock_print):
        cli.list_permissions()
        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call("user1:rw")
        mock_print.assert_any_call("user2:r")

    @patch("builtins.open", new_callable=mock_open)
    @patch("core.cli.get_permissions", return_value={"user1": "rw"})
    def test_manage_permissions_add(self, mock_get, mock_open):
        result = cli.manage_permissions("user2", "+rw")
        self.assertTrue(result)

        calls = mock_open().write.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "user1:rw\n")
        self.assertEqual(calls[1][0][0], "user2:rw\n")

    @patch("builtins.open", new_callable=mock_open)
    @patch("core.cli.get_permissions",
           return_value={"user1": "rw", "user2": "r"})
    def test_manage_permissions_remove(self, mock_get, mock_open):
        result = cli.manage_permissions("user2", "-r")
        self.assertTrue(result)
        mock_open().write.assert_called_once_with("user1:rw\n")

    def test_manage_permissions_invalid_format(self):
        result = cli.manage_permissions("user", "invalid")
        self.assertFalse(result)

    @patch("core.cli.MtTextEditApp")
    @patch("re.compile")
    def test_connect_to_session_valid(self, mock_re, mock_app):
        mock_re.return_value.match.return_value = True
        cli.connect_to_session(True, "192.168.0.1", "test_user")
        mock_app.return_value.connect.assert_called_once_with("192.168.0.1")

    @patch("builtins.print")
    @patch("re.compile")
    def test_connect_to_session_invalid(self, mock_re, mock_print):
        mock_re.return_value.match.return_value = False
        cli.connect_to_session(False, "invalid", "user")
        mock_print.assert_called_once_with("Wrong connection ip address")

    @patch("builtins.print")
    @patch("builtins.open", side_effect=IOError)
    def test_host_session_failure(self, mock_open, mock_print):
        cli.host_session(False, "missing.txt", "user")
        mock_print.assert_called_once_with("File does not exist :(")

    @patch("os.makedirs")
    @patch("os.listdir",
           return_value=["file1.o.cache", "file2.o.cache", "other.txt"])
    @patch("builtins.print")
    def test_list_all_saved_history(
            self, mock_print, mock_listdir, mock_makedirs):
        cli.list_all_saved_history("/path/to/file.txt")
        mock_makedirs.assert_called_once_with(
            os.path.dirname(
                cli.HISTORY_FILE_PATH +
                "/file.txt/"), exist_ok=True
        )
        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call("file1\t1")
        mock_print.assert_any_call("file2\t2")

    @patch("core.cli.MtTextEditApp")
    @patch("builtins.open", mock_open(read_data="history content"))
    @patch("os.listdir", return_value=["file1.o.cache", "file2.o.cache"])
    def test_show_changes_success(self, mock_listdir, mock_app):
        cli.show_changes("/path/to/file.txt", "1")
        mock_app.assert_called_once_with("view_changes", "history content")
        mock_app.return_value.show_changes.assert_called_once_with(
            "/file.txt", "file1.o.cache"
        )

    @patch("builtins.print")
    @patch("builtins.open", side_effect=FileExistsError)
    @patch("os.listdir", return_value=["file1.o.cache"])
    def test_show_changes_failure(self, mock_listdir, mock_open, mock_print):
        cli.show_changes("/path/to/file.txt", "1")
        mock_print.assert_called_once_with("no such changes file found, :(")

    @patch("core.cli.MtTextEditApp")
    @patch("builtins.open", mock_open(read_data="blame content"))
    @patch("os.listdir", return_value=["file1.o.cache", "file2.o.cache"])
    def test_show_blame_success(self, mock_listdir, mock_app):
        cli.show_blame("/path/to/file.txt", "1")
        mock_app.assert_called_once_with("view_blame", "blame content")
        mock_app.return_value.show_blame.assert_called_once_with(
            "/file.txt", "file1.o.cache"
        )

    @patch("builtins.print")
    @patch("builtins.open", side_effect=Exception)
    @patch("os.listdir", return_value=["file1.o.cache"])
    def test_show_blame_failure(self, mock_listdir, mock_open, mock_print):
        """Тест просмотра несуществующего blame"""
        cli.show_blame("/path/to/file.txt", "1")
        mock_print.assert_called_once_with("no such changes file found, :(")

    @patch("core.cli.main")
    def test_main_entry(self, mock_main):
        with patch.object(sys, 'argv', ['script.py']):
            cli.main()
            mock_main.assert_called_once()

    @patch("core.cli.list_permissions")
    def test_main_pl(self, mock_list):
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-Pl']):
            cli.main()
            mock_list.assert_called_once()

    @patch("core.cli.manage_permissions", return_value=True)
    def test_main_p(self, mock_manage):
        with patch.object(sys, 'argv', ['prog', '-P', 'user', '+rw']):
            cli.main()
            mock_manage.assert_called_once_with('user', '+rw')

    @patch("core.cli.connect_to_session")
    def test_main_c(self, mock_connect):
        with patch.object(sys, 'argv', ['prog', '-C', '192.168.0.1', 'user']):
            cli.main()
            mock_connect.assert_called_once_with(False, '192.168.0.1', 'user')

    @patch("core.cli.host_session")
    def test_main_h(self, mock_host):
        with patch.object(sys, 'argv', ['prog', '-H', 'file.txt', 'host']):
            cli.main()
            mock_host.assert_called_once_with(False, 'file.txt', 'host')

    @patch("core.cli.list_all_saved_history")
    def test_main_chh(self, mock_list):
        with patch.object(sys, 'argv', ['prog', '-CHH', 'file.txt']):
            cli.main()
            mock_list.assert_called_once_with('file.txt')

    @patch("core.cli.show_changes")
    def test_main_ch(self, mock_show):
        with patch.object(sys, 'argv', ['prog', '-CH', 'file.txt', '1']):
            cli.main()
            mock_show.assert_called_once_with('file.txt', '1')

    @patch("core.cli.show_blame")
    def test_main_b(self, mock_show):
        with patch.object(sys, 'argv', ['prog', '-B', 'file.txt', '1']):
            cli.main()
            mock_show.assert_called_once_with('file.txt', '1')


if __name__ == "__main__":
    unittest.main()
