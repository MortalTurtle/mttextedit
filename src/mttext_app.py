import asyncio
import curses
from message_parser import MessageParser
from model import Model
from convert import TextExporter


class MtTextEditApp():
    _model: Model
    _username: str
    _writer = None
    _writers = []
    _reader_to_writer = {}
    _DELIMITER = b' \n\x1E'
    _PERMISSION_FILE_PATH = "/tmp/lib/mttext/permissions"

    def __init__(self, username: str, filetext: str = "", debug=False, file_path=None):
        self.debug = debug
        self._model = Model(filetext, username, file_path)
        self._file_path = None
        self._is_host = file_path != None
        self._can_write = True
        self._converter = TextExporter(self._model.text_lines)
        self._non_edit_func_by_key = {
            curses.KEY_LEFT: self._model.user_pos_shifted_left,
            curses.KEY_RIGHT: self._model.user_pos_shifted_right,
            curses.KEY_DOWN: self._model.user_pos_shifted_down,
            curses.KEY_UP: self._model.user_pos_shifted_up,
            337: self._model.user_shifted_up,  # SHIFT + UP
            336: self._model.user_shifted_down,  # SHIFT + DOWN
            393: self._model.user_shifted_left,  # SHIFT + LEFT
            402: self._model.user_shifted_right,  # SHIFT + RIGHT
        }
        self._edit_func_by_user_key = {
            curses.KEY_BACKSPACE: self._model.user_deleted_char,
            10: self._model.user_added_new_line,  # ENTER
            26: self._model.undo,  # CTRL + Z
            24: self._model.cut,  # CTRL + X
            25: self._model.redo , # CTRL + Y
            16: self.save_as_pdf, #+p
            8: self.save_as_html,#+h
            4:  self.save_as_doc #+d

        }
        self._get_msg_by_key = {
            curses.KEY_BACKSPACE: lambda x: f"{x} -D",
            curses.KEY_LEFT: lambda x: f"{x} -M l",
            curses.KEY_RIGHT: lambda x: f"{x} -M r",
            curses.KEY_DOWN: lambda x: f"{x} -M d",
            curses.KEY_UP: lambda x:  f"{x} -M u",
            10: lambda x: f"{x} -NL",  # ENTER,
            337: lambda x: f"{x} -MS u",  # SHIFT + UP
            336: lambda x: f"{x} -MS d",  # SHIFT + DOWN
            393: lambda x: f"{x} -MS l",  # SHIFT + LEFT
            402: lambda x: f"{x} -MS r",  # SHIFT + RIGHT
            22: lambda x: f"{x} -PASTE {self._model._buffer}",  # CTRL + V
            24: lambda x: f"{x} -CUT",  # CTRL + X
            26: lambda x: f"{x} -UNDO",  # CTRL + Z
            25: lambda x: f"{x} -REDO"  # CTRL + Y
        }
        self._func_by_special_key = {
            19: self._model.save_file,  # CTRL + S
            27: self.stop,  # ESC
            3: self._model.copy_to_buffer,  # CTRL + C
            22: self._model.paste_from_buffer,  # CTRL + V

        }
        self._username = username
        self._msg_parser = MessageParser(self._model, self._is_host, username)
        self._send_queue = asyncio.Queue()
        self._msg_queue = asyncio.Queue()
        self._load_permissions()
       

    async def save_as_pdf(self):
        if not self.file_path:
            return 
        self._converter.to_pdf(file_path)

    async def save_as_html(self):
        if not self.file_path:
            return 
        self._converter.to_html(file_path)


    async def save_as_doc(self):
        if not self.file_path:
            return 
        self._converter.to_doc(file_path)


    def _load_permissions(self):
        if not self._is_host:
            return
        self._permissions = {}
        try:
            with open(self._PERMISSION_FILE_PATH, 'r') as f:
                for line in f:
                    if ':' in line:
                        user, rights = line.strip().split(':')
                        self._permissions[user] = rights
        except FileNotFoundError:
            with open(self._PERMISSION_FILE_PATH, 'w') as f:
                f.write('')

    def run(self):
        curses.wrapper(self._main)

    def connect(self, conn_ip):
        curses.wrapper(self._main, True, conn_ip)

    async def stop(self):
        await self.send(f"{self._username} " + ("-DCH" if self._is_host else "-DC"))
        await asyncio.sleep(0.1)
        if self._writer:
            self._writer.close()
        self._stop = True
        await self._model.stop_view()

    async def send(self, item):
        await self._send_queue.put(item)

    async def _parse_key(self, key):
        if key in self._non_edit_func_by_key:
            await self._non_edit_func_by_key[key](self._username)
            await self.send(self._get_msg_by_key[key](self._username))
        if key in self._edit_func_by_user_key.keys() and self._can_write:
            await self._edit_func_by_user_key[key](self._username)
            await self.send(self._get_msg_by_key[key](self._username))
        elif key in self._func_by_special_key and (self._can_write or key != 22):
            await self._func_by_special_key[key]()
            if key in self._get_msg_by_key:
                await self.send(self._get_msg_by_key[key](self._username))
        else:
            if 32 <= key <= 126 and self._can_write:
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
        while True:
            if self._stop:
                return
            key = self.stdscr.getch()
            if key != -1:
                if self.debug:
                    print(key)
                await self._parse_key(key)
            await asyncio.sleep(0.01)

    async def _consumer_handler(self, reader):
        while True:
            if self._stop:
                return
            try:
                data = await reader.readuntil(self._DELIMITER)
            except:
                if self._is_host:
                    self._writers.remove(self._reader_to_writer[reader])
                break
            message = data.decode()
            args = message.split(' ')
            if self.debug:
                print(message)
            if args[1] == '-DCH':
                await self.stop()
                return
            if args[1] == '-WNACK' and not self._is_host:
                self._can_write = False
                self._msg_parser.can_write = False
            await self._msg_parser.parse_message(args)
            if self._is_host:
                await self.send(message)

    async def _producer_handler(self, writer):
        while True:
            if self._stop:
                return
            try:
                message = self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.15)
                continue
            try:
                writer.write(message.encode() + self._DELIMITER)
                await writer.drain()
            except:
                break

    async def _server_producer_handler(self):
        while True:
            if self._stop:
                return
            try:
                message = self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.15)
                continue
            for connection in self._writers:
                try:
                    connection.write(message.encode() + self._DELIMITER)
                    await connection.drain()
                except:
                    connection.close()
                    self._writers.remove(connection)

    async def _connection_handler(self, reader, writer):
        user_pos = [await self._model.get_user_pos(
            x) for x in self._model.users]
        user_pos_strings = [f"{x[0]} {x[1]}" for x in user_pos]
        can_write = False
        try:
            data = await reader.readuntil(self._DELIMITER)
            message = data.decode()
            args = message.split(' ')
            if args[1] != '-C':
                return
            permissions = self._permissions.get(args[0], "")
            if permissions == "":
                try:
                    writer.write(
                        f'{self._username} -DCH'.encode() + self._DELIMITER)
                    await writer.drain()
                except:
                    writer.close()
                return
            if "r" in permissions:
                self._writers.append(writer)
                self._reader_to_writer[reader] = writer
                if "w" in permissions:
                    can_write = True
                else:
                    try:
                        writer.write(
                            f'{self._username} -WNACK'.encode() + self._DELIMITER)
                        await writer.drain()
                    except:
                        writer.close()
        except:
            if self._is_host:
                self._writers.remove(self._reader_to_writer[reader])
            return
        await self.send(f"{self._username} -U {' '.join([f"{x[0]} {x[1]}" for x in zip(self._model.users, user_pos_strings)])}")
        await self.send(f"{self._username} -T {'\n'.join(self._model.text_lines)}")
        if can_write:
            await self._consumer_handler(reader)

    def _main(self, *args, **kwargs):
        asyncio.run(self._async_main(*args, **kwargs))

    async def _async_main(self, stdscr, should_connect=False, conn_ip=''):
        self.stdscr = stdscr
        self._stop = False
        if not self.debug:
            asyncio.get_event_loop().run_in_executor(None, self._model.run_view, stdscr)
        if not should_connect:
            server = await asyncio.start_server(
                self._connection_handler, '127.0.0.1', 12000)
            await asyncio.gather(
                self._input_handler(),
                self._server_producer_handler()
            )
        else:
            reader, writer = await asyncio.open_connection(
                conn_ip, 12000)
            self._writer = writer
            await self.send(f"{self._username} -C {self._username}")
            await asyncio.gather(
                self._consumer_handler(reader),
                self._producer_handler(writer),
                self._input_handler()
            )
