import asyncio
import curses
from model import Model
from websockets import connect
from websockets import serve
from websockets.exceptions import ConnectionClosedOK


class MtTextEditApp():
    _model: Model
    _username: str
    _server = None
    _client = None

    def __init__(self, username: str, filetext: str = "", debug=False, file_path=None):
        self.debug = debug
        self._model = Model(filetext, username, file_path)
        self._file_path = None
        self._func_by_user_key = {
            curses.KEY_LEFT: self._model.user_pos_shifted_left,
            curses.KEY_RIGHT: self._model.user_pos_shifted_right,
            curses.KEY_DOWN: self._model.user_pos_shifted_down,
            curses.KEY_UP: self._model.user_pos_shifted_up,
            curses.KEY_BACKSPACE: self._model.user_deleted_char,
            10: self._model.user_added_new_line  # ENTER
        }
        user_pos = self._model.user_positions
        self._get_msg_by_key = {
            curses.KEY_BACKSPACE: lambda x: f"{x} -D",
            curses.KEY_LEFT: lambda x: f"{x} -M {user_pos[x][0]} {user_pos[x][1]}",
            curses.KEY_RIGHT: lambda x: self._get_msg_by_key[curses.KEY_LEFT](x),
            curses.KEY_DOWN: lambda x: self._get_msg_by_key[curses.KEY_LEFT](x),
            curses.KEY_UP: lambda x: self._get_msg_by_key[curses.KEY_LEFT](x),
            10: lambda x: f"{x} -NL"  # ENTER
        }
        self._func_by_special_key = {
            19: self._model.save_file,
            3: self.stop
        }
        self._username = username
        self._send_queue = asyncio.Queue()

    def run(self):
        curses.wrapper(self._main)

    def connect(self, conn_ip):
        curses.wrapper(self._main, True, conn_ip)

    async def stop(self):
        await self._model.stop_view()
        self._stop = True
        if self._client != None:
            self._client.close()
        if self._server != None:
            self._server.close()
        # asyncio.get_event_loop().stop()

    async def send(self, item):
        await self._send_queue.put(item)

    async def _parse_key(self, key):
        if key in self._func_by_user_key.keys():
            await self._func_by_user_key[key](self._username)
            await self.send(self._get_msg_by_key[key](self._username))
        elif key in self._func_by_special_key:
            await self._func_by_special_key[key]()
        else:
            if 32 <= key <= 126:
                key_str = chr(key)
                await self._model.user_wrote_char(self._username, key_str)
                await self.send(
                    f"{self._username} -E " +
                    f"{'/s' if key_str == ' ' else key_str}")

    async def _input_handler(self):
        curses.raw()
        curses.cbreak()
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        while not self._stop:
            key = self.stdscr.getch()
            if key != -1:
                if self.debug:
                    print(key)
                await self._parse_key(key)
            await asyncio.sleep(0.01)
        pass

    async def _consumer_handler(self, websocket):
        async for message in websocket:
            if self._stop:
                return
            args = message.split(' ')
            if self.debug:
                print(message)
            if args[0] not in self._model.users:
                await self._model.add_user(args[0])
            if args[1] == '-T':
                await self._model.text_upload(' '.join(args[2:]))
            if args[1] == '-M':
                await self._model.user_pos_update(args[0],
                                                  int(args[2]), int(args[3]))
            if args[1] == '-E':
                await self._model.user_wrote_char(args[0], args[2] if args[2] != '/s' else ' ')
            if args[1] == '-D':
                await self._model.user_deleted_char(args[0])
            if args[1] == '-NL':
                await self._model.user_added_new_line(args[0])

    async def _producer_handler(self, websocket):
        while not self._stop:
            message = await self._send_queue.get()
            try:
                await websocket.send(message)
            except ConnectionClosedOK:
                break

    async def _connection_handler(self, websocket):
        await self.send(f"{self._username} -T {'\n'.join(self._model.text_lines)}")
        await asyncio.gather(
            self._consumer_handler(websocket),
            self._producer_handler(websocket)
        )
        pass

    def _main(self, *args, **kwargs):
        asyncio.run(self._async_main(*args, **kwargs))

    async def _async_main(self, stdscr, should_connect=False, conn_ip=''):
        self.stdscr = stdscr
        self._stop = False
        if not self.debug:
            asyncio.get_event_loop().run_in_executor(None, self._model.run_view, stdscr)
        if not should_connect:
            self._server = await serve(self._connection_handler, "0.0.0.0", 12000)
            await self._input_handler()
        else:
            self._client = await connect('ws://' + conn_ip + ':12000')
            await self.send(f"{self._username} -C {self._username}")
            await asyncio.gather(
                self._consumer_handler(self._client),
                self._producer_handler(self._client),
                self._input_handler()
            )
