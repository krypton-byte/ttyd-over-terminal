import websocket
from sys import stdout
from os import get_terminal_size
from signal import signal, SIGWINCH, SIGINT, SIGTSTP
import contextlib
import termios
import sys
from codecs import decode
from threading import Thread
import base64
from typing import Optional
import argparse
import sys
term = termios.tcgetattr(sys.stdin.fileno())
from urllib.parse import quote

class ttyd(websocket.WebSocketApp):

    def __init__(self, url: str, credential: Optional[str]=None, args: list=[], cmd: str=''):
        super().__init__(
            url+'?'+''.join([f'arg={quote(x)}' for x in args]),
            header=['Sec-WebSocket-Protocol: tty'],
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close
        )
        self.cmd = cmd
        self.credential = credential
        self.connected = False
        self.__connected = False

    def on_close(self, ws, code, msg):
        if not self.__connected:
            print('connection refushed')
        term[3] &= termios.ECHO | termios.ECHOCTL | termios.BRKINT
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, term)
        self.connected = False

    def on_message(self, ws, msg: bytes):
        if not self.connected:
            self.connected = True
            self.__connected = True
            if self.cmd:
                self.send_command(self.cmd + '\n')
            signal(SIGINT, lambda x, y: self.send_ctrl('c'))
            signal(20, lambda x, y: self.send_ctrl('z'))
            th = Thread(target=self.send_keys)
            th.daemon = True
            th.start()
        if msg[0] == 48:
            stdout.write(msg[1:].decode())
            stdout.flush()

    def resize(self, d, x):
        self.send('1{"columns":%s,"rows":%s}' % get_terminal_size())

    def send_command(self, c: str):
        if not self.connected:
            term[3] &= termios.ECHO | termios.ECHOCTL | termios.BRKINT
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, term)
            sys.exit(0)
        self.send('0' + c)

    def send_ctrl(self, q: str):
        code = {'c': '3003', 'z': '301a'}
        c = code.get(q.lower())
        if c:
            self.send(decode(c, 'hex'))

    @contextlib.contextmanager
    def raw_mode(self, file):
        old_attrs = termios.tcgetattr(file.fileno())
        new_attrs = old_attrs[:]
        new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
        try:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
            yield
        finally:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)

    def send_keys(self):
        with self.raw_mode(sys.stdin):
            while True:
                h = sys.stdin.read(1)
                if not self.connected:
                    break
                self.send_command(h)

    def on_open(self, ws):
        self.send('{"AuthToken":"%s"}' % (base64.b64encode(self.credential.encode()) if self.credential else b'').decode())
        signal(SIGWINCH, self.resize)
        self.resize(*get_terminal_size())


arg = argparse.ArgumentParser()
arg.add_argument('--url', type=str, help='example --url=ws://example.com', required=True)
arg.add_argument('--credential', type=str, help='example --credential="username:password"')
arg.add_argument('args', metavar='ARGS', nargs='*', help='Arguments', default=[])
arg.add_argument('-c', type=str, help='Send command', default='')
parse = arg.parse_args()
ttyd(parse.url, parse.credential, parse.args, parse.c).run_forever()