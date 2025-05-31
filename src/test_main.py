import unittest
from unittest.mock import patch, mock_open
import os
import sys

import main as cli


class TestCLIModule(unittest.TestCase):

    @patch("builtins.open", side_effect=FileNotFoundError)
    @patch("os.makedirs")
    def test_get_permissions_not_exists(self, mock_makedirs, mock_open):
        """Тест получения разрешений при отсутствии файла"""
        permissions = cli.get_permissions()
        self.assertEqual(permissions, {})
        mock_makedirs.assert_called_once_with(
            os.path.dirname(cli.PERMISSION_FILE), exist_ok=True
        )

    @patch("builtins.print")
    @patch("main.get_permissions", return_value={"user1": "rw", "user2": "r"})
    def test_list_permissions(self, mock_get, mock_print):
        """Тест вывода списка разрешений"""
        cli.list_permissions()
        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call("user1:rw")
        mock_print.assert_any_call("user2:r")

    @patch("builtins.open", new_callable=mock_open)
    @patch("main.get_permissions", return_value={"user1": "rw"})
    def test_manage_permissions_add(self, mock_get, mock_open):
        """Тест добавления разрешений"""
        result = cli.manage_permissions("user2", "+rw")
        self.assertTrue(result)

        # Проверяем все вызовы write
        calls = mock_open().write.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "user1:rw\n")
        self.assertEqual(calls[1][0][0], "user2:rw\n")

    @patch("builtins.open", new_callable=mock_open)
    @patch("main.get_permissions", return_value={"user1": "rw", "user2": "r"})
    def test_manage_permissions_remove(self, mock_get, mock_open):
        """Тест удаления разрешений"""
        result = cli.manage_permissions("user2", "-r")
        self.assertTrue(result)
        mock_open().write.assert_called_once_with("user1:rw\n")

    def test_manage_permissions_invalid_format(self):
        """Тест обработки неверного формата разрешений"""
        result = cli.manage_permissions("user", "invalid")
        self.assertFalse(result)

    @patch("main.MtTextEditApp")
    @patch("re.compile")
    def test_connect_to_session_valid(self, mock_re, mock_app):
        """Тест подключения к сессии с валидным IP"""
        mock_re.return_value.match.return_value = True
        cli.connect_to_session(True, "192.168.0.1", "test_user")
        mock_app.return_value.connect.assert_called_once_with("192.168.0.1")

    @patch("builtins.print")
    @patch("re.compile")
    def test_connect_to_session_invalid(self, mock_re, mock_print):
        """Тест подключения с невалидным IP"""
        mock_re.return_value.match.return_value = False
        cli.connect_to_session(False, "invalid", "user")
        mock_print.assert_called_once_with("Wrong connection ip address")

    @patch("builtins.print")
    @patch("builtins.open", side_effect=IOError)
    def test_host_session_failure(self, mock_open, mock_print):
        """Тест запуска сессии с несуществующим файлом"""
        cli.host_session(False, "missing.txt", "user")
        mock_print.assert_called_once_with("File does not exist :(")

    @patch("os.makedirs")
    @patch("os.listdir",
           return_value=["file1.o.cache", "file2.o.cache", "other.txt"])
    @patch("builtins.print")
    def test_list_all_saved_history(
            self, mock_print, mock_listdir, mock_makedirs):
        """Тест вывода истории изменений"""
        cli.list_all_saved_history("/path/to/file.txt")
        mock_makedirs.assert_called_once_with(
            os.path.dirname(
                cli.HISTORY_FILE_PATH +
                "/file.txt/"), exist_ok=True
        )
        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_any_call("file1\t1")
        mock_print.assert_any_call("file2\t2")

    @patch("main.MtTextEditApp")
    @patch("builtins.open", mock_open(read_data="history content"))
    @patch("os.listdir", return_value=["file1.o.cache", "file2.o.cache"])
    def test_show_changes_success(self, mock_listdir, mock_app):
        """Тест просмотра изменений"""
        cli.show_changes("/path/to/file.txt", "1")
        mock_app.assert_called_once_with("view_changes", "history content")
        mock_app.return_value.show_changes.assert_called_once_with(
            "/file.txt", "file1.o.cache"
        )

    @patch("builtins.print")
    @patch("builtins.open", side_effect=FileExistsError)
    # Возвращаем непустой список
    @patch("os.listdir", return_value=["file1.o.cache"])
    def test_show_changes_failure(self, mock_listdir, mock_open, mock_print):
        """Тест просмотра несуществующих изменений"""
        cli.show_changes("/path/to/file.txt", "1")
        mock_print.assert_called_once_with("no such changes file found, :(")

    @patch("main.MtTextEditApp")
    @patch("builtins.open", mock_open(read_data="blame content"))
    @patch("os.listdir", return_value=["file1.o.cache", "file2.o.cache"])
    def test_show_blame_success(self, mock_listdir, mock_app):
        """Тест просмотра blame"""
        cli.show_blame("/path/to/file.txt", "1")
        mock_app.assert_called_once_with("view_blame", "blame content")
        mock_app.return_value.show_blame.assert_called_once_with(
            "/file.txt", "file1.o.cache"
        )

    @patch("builtins.print")
    @patch("builtins.open", side_effect=Exception)
    # Возвращаем непустой список
    @patch("os.listdir", return_value=["file1.o.cache"])
    def test_show_blame_failure(self, mock_listdir, mock_open, mock_print):
        """Тест просмотра несуществующего blame"""
        cli.show_blame("/path/to/file.txt", "1")
        mock_print.assert_called_once_with("no such changes file found, :(")

    @patch("main.main")
    def test_main_entry(self, mock_main):
        """Тест запуска модуля как скрипта"""
        with patch.object(sys, 'argv', ['script.py']):
            cli.main()
            mock_main.assert_called_once()

    @patch("main.list_permissions")
    def test_main_pl(self, mock_list):
        """Тест обработки аргумента -Pl"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-Pl']):
            cli.main()
            mock_list.assert_called_once()

    @patch("main.manage_permissions", return_value=True)
    def test_main_p(self, mock_manage):
        """Тест обработки аргумента -P"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-P', 'user', '+rw']):
            cli.main()
            mock_manage.assert_called_once_with('user', '+rw')

    @patch("main.connect_to_session")
    def test_main_c(self, mock_connect):
        """Тест обработки аргумента -C"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-C', '192.168.0.1', 'user']):
            cli.main()
            mock_connect.assert_called_once_with(False, '192.168.0.1', 'user')

    @patch("main.host_session")
    def test_main_h(self, mock_host):
        """Тест обработки аргумента -H"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-H', 'file.txt', 'host']):
            cli.main()
            mock_host.assert_called_once_with(False, 'file.txt', 'host')

    @patch("main.list_all_saved_history")
    def test_main_chh(self, mock_list):
        """Тест обработки аргумента -CHH"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-CHH', 'file.txt']):
            cli.main()
            mock_list.assert_called_once_with('file.txt')

    @patch("main.show_changes")
    def test_main_ch(self, mock_show):
        """Тест обработки аргумента -CH"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-CH', 'file.txt', '1']):
            cli.main()
            mock_show.assert_called_once_with('file.txt', '1')

    @patch("main.show_blame")
    def test_main_b(self, mock_show):
        """Тест обработки аргумента -B"""
        # Создаем фейковые аргументы командной строки
        with patch.object(sys, 'argv', ['prog', '-B', 'file.txt', '1']):
            cli.main()
            mock_show.assert_called_once_with('file.txt', '1')


if __name__ == "__main__":
    unittest.main()
