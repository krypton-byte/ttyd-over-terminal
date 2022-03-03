import websocket
from sys import stdout
from os import get_terminal_size
from signal import signal, SIGWINCH, SIGINT
import contextlib
import termios
import sys
from codecs import decode
from threading import Thread
import base64
from typing import Optional
import argparse

#websocket.enableTrace(True)
class ttyd(websocket.WebSocketApp):
    def __init__(
        self,
        url: str,
        credential: Optional[str] = None
    ):
        super().__init__(
            url,
            header=['Sec-WebSocket-Protocol: tty'],
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close
        )
        self.credential = credential
        signal(2, lambda x,y : self.send_ctrl('c'))
        signal(20, lambda x,y : self.send_ctrl('z'))
        th = Thread(target=self.send_keys)
        th.start()
        
    def on_close(self, ws, code, msg):
        pass

    def on_message(self, ws, msg: bytes):
        if msg[0] == 48:
            stdout.write(msg[1:].decode())
            stdout.flush()
    def resize(self, d, x):
        self.send('1{"columns":%s,"rows":%s}'%get_terminal_size())

    def send_command(self, c: str):
        self.send('0'+c)

    def send_ctrl(self, q: str):
        code = {
            'c': '3003',
            'z': '301a'
        }
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
                self.send_command(h)

    def on_open(self, ws):
        self.send('{"AuthToken":"%s"}' % (base64.b64encode(self.credential.encode()) if self.credential else b'').decode())
        signal(SIGWINCH, self.resize)
        self.resize(*get_terminal_size())

arg = argparse.ArgumentParser()
arg.add_argument('--url', type=str, help='example --url=ws://example.com', required=True)
arg.add_argument('--credential', type=str, help='example --credential="a:b"')
parse = arg.parse_args()
ttyd(parse.url, parse.credential).run_forever()