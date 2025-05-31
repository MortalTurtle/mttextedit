import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import curses
from core.mttext_app import MtTextEditApp


class TestMtTextEditApp(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = MtTextEditApp(
            "test_user", "test\ntext", file_path="/tmp/test.txt")
        self.app.stdscr = MagicMock()
        self.app._stop = False

        self.app._model = MagicMock()
        self.app._model.add_user = AsyncMock()
        self.app._model.user_wrote_char = AsyncMock()
        self.app._model.user_pos_shifted_left = AsyncMock()
        self.app._model.user_pos_shifted_right = AsyncMock()
        self.app._model.user_pos_shifted_down = AsyncMock()
        self.app._model.user_pos_shifted_up = AsyncMock()
        self.app._model.user_deleted_char = AsyncMock()
        self.app._model.user_added_new_line = AsyncMock()
        self.app._model.undo = AsyncMock()
        self.app._model.cut = AsyncMock()
        self.app._model.redo = AsyncMock()
        self.app._model.copy_to_buffer = AsyncMock()
        self.app._model.paste_from_buffer = AsyncMock()
        self.app._model.save_file = AsyncMock()
        self.app._model.save_changes_history = AsyncMock()
        self.app._model.stop_view = AsyncMock()
        self.app._model.get_user_pos = AsyncMock(return_value=(0, 0))
        self.app._model.run_view = MagicMock()
        self.app._msg_parser = MagicMock()
        self.app._msg_parser.parse_message = AsyncMock()
        self.app.stdscr.getch = MagicMock(return_value=65)  # 'A'
        self.app.stdscr.getmaxyx = MagicMock(return_value=(24, 80))

    @patch('curses.wrapper')
    def test_run(self, mock_wrapper):
        self.app.run()
        mock_wrapper.assert_called_once()

    @patch('curses.wrapper')
    def test_connect(self, mock_wrapper):
        self.app.connect("127.0.0.1")
        mock_wrapper.assert_called_once()

    @patch('curses.wrapper')
    def test_show_changes(self, mock_wrapper):
        self.app.show_changes("file.txt", "changes.txt")
        mock_wrapper.assert_called_once()

    @patch('curses.wrapper')
    def test_show_blame(self, mock_wrapper):
        self.app.show_blame("file.txt", "changes.txt")
        mock_wrapper.assert_called_once()

    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_stop(self, mock_sleep):
        self.app._writer = MagicMock()
        await self.app.stop()
        self.assertTrue(self.app._stop)

    async def test_send(self):
        with patch.object(self.app._send_queue,
                          'put', new_callable=AsyncMock) as mock_put:
            await self.app.send("test message")
            mock_put.assert_called_once_with("test message")

    @patch.object(MtTextEditApp, 'send', new_callable=AsyncMock)
    async def test_parse_key_non_edit(self, mock_send):
        await self.app._parse_key(curses.KEY_LEFT)
        mock_send.assert_called_once()

    @patch.object(MtTextEditApp, 'send', new_callable=AsyncMock)
    async def test_parse_key_edit(self, mock_send):
        await self.app._parse_key(curses.KEY_BACKSPACE)
        mock_send.assert_called_once()

    @patch.object(MtTextEditApp, 'send', new_callable=AsyncMock)
    async def test_parse_key_special(self, mock_send):
        await self.app._parse_key(19)  # CTRL+S
        mock_send.assert_not_called()

    @patch.object(MtTextEditApp, 'send', new_callable=AsyncMock)
    async def test_parse_key_char(self, mock_send):
        await self.app._parse_key(65)  # 'A'
        mock_send.assert_called_once()

    @patch('asyncio.sleep', new_callable=AsyncMock)
    @patch('curses.raw')
    @patch('curses.cbreak')
    async def test_input_handler(self, mock_cbreak, mock_raw, mock_sleep):
        self.app.stdscr.getch = MagicMock(side_effect=[65, -1, -1, -1, -1])
        self.app._stop = True
        await self.app._input_handler()

    async def test_consumer_handler(self):
        mock_reader = MagicMock()
        mock_reader.readuntil = AsyncMock(
            side_effect=asyncio.IncompleteReadError(b'', 10))
        self.app._reader_to_writer[mock_reader] = MagicMock()
        self.app._writers = [self.app._reader_to_writer[mock_reader]]
        await self.app._consumer_handler(mock_reader)

    async def test_producer_handler(self):
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        await self.app._send_queue.put("test")
        self.app._stop = True
        await self.app._producer_handler(mock_writer)

    async def test_server_producer_handler(self):
        mock_writer = MagicMock()
        self.app._writers = [mock_writer]
        await self.app._send_queue.put("test")
        self.app._stop = True
        await self.app._server_producer_handler()

    @patch.object(MtTextEditApp, 'send', new_callable=AsyncMock)
    async def test_connection_handler_valid(self, mock_send):
        mock_reader = MagicMock()
        mock_reader.readuntil = AsyncMock(return_value=b"user -C user")
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        self.app._permissions = {"user": "rw"}
        self.app._consumer_handler = AsyncMock()
        await self.app._connection_handler(mock_reader, mock_writer)
        mock_send.assert_called()

    @patch('builtins.open')
    def test_load_permissions_exists(self, mock_open):
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.__iter__.return_value = ["user:rw\n"]
        mock_open.return_value = mock_file

        self.app._is_host = True
        self.app._load_permissions()
        self.assertEqual(self.app._permissions, {"user": "rw"})

    @patch('builtins.open')
    def test_load_permissions_not_exists(self, mock_open):
        mock_open.side_effect = [FileNotFoundError, MagicMock()]
        self.app._is_host = True
        self.app._load_permissions()
        self.assertEqual(self.app._permissions, {})

    @patch('core.text_exporter.TextExporter')
    async def test_save_as_html(self, mock_exporter):
        self.app.text_exporterer = mock_exporter.return_value
        await self.app.save_as_html()

    @patch('core.text_exporter.TextExporter')
    async def test_save_as_doc(self, mock_exporter):
        self.app.text_exporterer = mock_exporter.return_value
        await self.app.save_as_doc()

    @patch('core.text_exporter.TextExporter')
    async def test_save_as_pdf(self, mock_exporter):
        self.app.text_exporterer = mock_exporter.return_value
        await self.app.save_as_pdf()


if __name__ == '__main__':
    unittest.main()
