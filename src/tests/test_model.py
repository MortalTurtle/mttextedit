import unittest
from unittest import mock
from core.model import Model


class TestModel(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.model = Model("qwer\nqwer\nqwer", "owner", "./testfile")

    @mock.patch('builtins.open', new_callable=mock.mock_open)
    async def test_(self, mock_open):
        await self.model.add_user("client")
        await self.model.user_shifted_right("owner")
        pos = await self.model.get_user_pos("owner")
        self.assertEqual(pos, (0, 0))
        await self.model.copy_to_buffer()
        await self.model.cut("owner")
        await self.model.paste_from_buffer()
        self.assertEqual(self.model.text_lines[0][0], 'q')
        await self.model.undo("owner")
        await self.model.redo("owner")
        self.assertEqual(self.model.text_lines[0][0], 'q')
        with mock.patch("shutil.copy") as mock_copy:
            with mock.patch("os.remove") as mock_os_remove:
                await self.model.save_file()
                await self.model.save_changes_history()
                mock_open.assert_called()
                mock_copy.assert_called()
                mock_os_remove.assert_called()

    @mock.patch('builtins.open', new_callable=mock.mock_open)
    async def test_undo_redo(self, mock_open):
        await self.model.add_user("client")
        await self.model.user_shifted_down("client")
        await self.model.user_wrote_char("client", "c")
        await self.model.user_wrote_char("client", "c")
        await self.model.undo("client")
        await self.model.user_shifted_right("owner")
        await self.model.cut("owner")
        await self.model.paste("owner", "pasted\n")
        await self.model.user_added_new_line("owner")
        await self.model.user_wrote_char("owner", "c")
        for i in range(4):
            await self.model.undo("owner")
        for i in range(4):
            await self.model.redo("owner")
        await self.model.undo("client")
        self.assertEqual(self.model.text_lines[0], "qwer")
        self.assertEqual(self.model.text_lines[1], "pasted")
        self.assertEqual(self.model.text_lines[2], "")
        self.assertEqual(self.model.text_lines[3], "cwer")
        self.assertEqual(self.model.text_lines[4], "qwer")
        with mock.patch("shutil.copy") as mock_copy:
            with mock.patch("os.remove") as mock_os_remove:
                await self.model.save_file()
                await self.model.save_changes_history()
                mock_open.assert_called()
                mock_copy.assert_called()
                mock_os_remove.assert_called()
        await self.model.user_disconnected("client")
        self.assertTrue("client" not in self.model.users)


if __name__ == '__main__':
    unittest.main()
