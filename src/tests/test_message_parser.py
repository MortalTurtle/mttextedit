# test_view_module.py
import unittest
from core.model import Model
from core.message_parser import MessageParser
import asyncio


class TestMessageParser(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.model = Model("qwer\nqwer\nqwer", "oo")
        asyncio.run(self.model.add_user("owner"))
        self.model.user_positions["owner"] = (0, 0)
        self.msg_parser = MessageParser(self.model, True, "oo")

    async def test_user_moved(self):
        await self.msg_parser.parse_message("owner -M r".split(' '))
        await self.msg_parser.parse_message("owner -M l".split(' '))
        await self.msg_parser.parse_message("owner -M d".split(' '))
        await self.msg_parser.parse_message("owner -M u".split(' '))
        self.assertEqual(self.model.user_positions["owner"], (0, 0))

    async def test_user_shifted(self):
        await self.msg_parser.parse_message("owner -MS r".split(' '))
        await self.msg_parser.parse_message("owner -MS l".split(' '))
        await self.msg_parser.parse_message("owner -MS d".split(' '))
        await self.msg_parser.parse_message("owner -MS u".split(' '))
        self.assertEqual(self.model.shift_user_positions["owner"], (0, 0))

    async def test_text_upload(self):
        await self.msg_parser.parse_message("owner -T text\n text".split(' '))
        self.assertEqual(self.model.text_lines[0], "text")

    async def test_user_wrote(self):
        await self.msg_parser.parse_message("owner -E z".split(' '))
        self.assertEqual(self.model.text_lines[0][0], 'z')

    async def test_user_deleted(self):
        await self.msg_parser.parse_message("owner -MS r".split(' '))
        await self.msg_parser.parse_message("owner -D".split(' '))
        self.assertEqual(self.model.text_lines[0][0], 'w')

    async def test_user_connected(self):
        await self.msg_parser.parse_message("client -C client".split(' '))
        self.assertTrue("client" in self.model.users)

    async def test_user_dcd(self):
        await self.msg_parser.parse_message("client -DC".split(' '))
        self.assertTrue("client" not in self.model.users)

    async def test_new_line(self):
        await self.msg_parser.parse_message("owner -NL".split(' '))
        self.assertEqual(len(self.model.text_lines), 4)

    async def test_paste(self):
        await self.msg_parser.parse_message(
            "owner -PASTE pasted\n pasted".split(' '))
        self.assertEqual(self.model.text_lines[0], "pasted")

    async def test_cut(self):
        await self.msg_parser.parse_message("owner -MS r".split(' '))
        await self.msg_parser.parse_message("owner -CUT".split(' '))
        self.assertEqual(self.model.text_lines[0][0], 'w')

    async def test_undo_redo(self):
        await self.msg_parser.parse_message("owner -MS r".split(' '))
        await self.msg_parser.parse_message("owner -CUT".split(' '))
        await self.msg_parser.parse_message("owner -UNDO".split(' '))
        self.assertEqual(self.model.text_lines[0][0], 'q')
        await self.msg_parser.parse_message("owner -REDO".split(' '))
        self.assertEqual(self.model.text_lines[0][0], 'w')


if __name__ == '__main__':
    unittest.main()
