from model import Model


class MessageParser:
    _handler_func_by_arg: dict

    def __init__(self, model: Model, is_host_parser, username):
        self._model = model
        self._username = username
        self._is_host = is_host_parser
        self._move_func_by_dir = {
            "l": self._model.user_pos_shifted_left,
            "r": self._model.user_pos_shifted_right,
            "u": self._model.user_pos_shifted_up,
            "d": self._model.user_pos_shifted_down,
        }
        self._shifted_move_func_by_dir = {
            "l": self._model.user_shifted_left,
            "r": self._model.user_shifted_right,
            "u": self._model.user_shifted_up,
            "d": self._model.user_shifted_down,
        }
        self._handler_func_by_arg = {
            "-M": self._user_moved_cursor,
            "-MS": self._user_moved_cursor_shifted,
            "-T": self._upload_text,
            "-E": self._user_wrote_char,
            "-D": self._user_deleted_char,
            "-DC": self._user_disconnected,
            "-NL": self._user_wrote_new_line,
            "-DCH": self._user_disconnected,
            "-PASTE": self._user_pasted,
            "-CUT": self._user_cut,
            "-UNDO": self._user_undo,
            "-REDO": self._user_redo,
        }

    async def _user_connected(self, args):
        await self._model.add_user(args[2])

    async def _user_moved_cursor(self, args):
        await self._move_func_by_dir[args[2]](args[0])

    async def _user_moved_cursor_shifted(self, args):
        await self._shifted_move_func_by_dir[args[2]](args[0])

    async def _user_wrote_char(self, args):
        await self._model.user_wrote_char(
            args[0], args[2] if args[2] != "/s" else " "
        )

    async def _user_deleted_char(self, args):
        await self._model.user_deleted_char(args[0])

    async def _user_disconnected(self, args):
        await self._model.user_disconnected(args[0])

    async def _user_wrote_new_line(self, args):
        await self._model.user_added_new_line(args[0])

    async def _upload_meta_info(self, args):
        self._initialized = True
        for i in range(2, len(args) - 2, 3):
            if args[i] == self._username:
                await self.stop()
                print("Sorry, server already have user with your username")
            await self._model.add_user(args[i])
            await self._model.user_pos_update(
                args[i], int(args[i + 1]), int(args[i + 2])
            )

    async def _upload_text(self, args):
        await self._model.text_upload(" ".join(args[2:-1]))

    async def _user_pasted(self, args):
        await self._model.paste(args[0], " ".join(args[2:-1]))

    async def _user_cut(self, args):
        await self._model.cut(args[0])

    async def _user_undo(self, args):
        await self._model.undo(args[0])

    async def _user_redo(self, args):
        await self._model.redo(args[0])

    async def parse_message(self, args):
        if args[1] == "-U" and not hasattr(self, "_initialized"):
            await self._upload_meta_info(args)
            return
        if args[1] == "-C" and args[0] not in self._model.users:
            await self._user_connected(args)
            return
        if args[0] == self._username or args[0] not in self._model.users:
            return
        await self._handler_func_by_arg[args[1]](args)
