from __future__ import annotations
import websocket
from sys import stdout
from os import get_terminal_size
from signal import (
    signal,
    SIGWINCH,
    SIGINT,
    SIGTSTP
)
import contextlib
import termios
import sys
from codecs import decode
from threading import Thread
from requests import Session
import base64
from typing import (
    Callable,
    Optional
)
import argparse
import sys
from urllib.parse import quote

term = termios.tcgetattr(sys.stdin.fileno())


class InvalidAuthorization(Exception):
    pass

VERIFY = True
class WebPage(Session):
    def __init__(self, url: str, verify: bool) -> None:
        super().__init__()
        self.verify: bool = verify
        self.url = url

    def token(self, username: str, password: str):
        b=base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers['Authorization'] = f'Basic {b}'
        bak = self.get(self.url+'/token', verify=self.verify)
        if bak.status_code == 200:
            return bak.json()['token']
        raise InvalidAuthorization('Credential Invalid')

    def check(self):
        if self.get(self.url).status_code != 200:
            raise InvalidAuthorization()

def Auth(fu: Callable):
    def arg(cls: ttyd, url: str, credential: Optional[str]=None, args: list=[], cmd: str=''):
        page = WebPage(url, VERIFY)
        try:
            page.check()
            return fu(cls, url, None, args, cmd)
        except InvalidAuthorization:
            if credential:
                return fu(cls, url, page.token(*credential.split(':')), args, cmd)
            else:
                raise InvalidAuthorization('Credential Required')
    return arg

class ttyd(websocket.WebSocketApp):
    @Auth
    def __init__(self, url: str, credential: Optional[str]=None, args: list=[], cmd: str=''):
        super().__init__(
            'ws'+url[4:]+'/ws?'+''.join([f'arg={quote(x)}' for x in args]),
            header=['Sec-WebSocket-Protocol: tty', f'Authorization: Basic {credential}'],
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close
        )
        self.credential = credential
        self.cmd = cmd
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
            sys.exit(0 if self.__connected else 1)
        self.send('0' + ('\r' if c == '\n' else c))

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
        self.send('{"AuthToken":"%s"}' % (self.credential or ''))
        signal(SIGWINCH, self.resize)
        self.resize(*get_terminal_size())

if __name__ == '__main__':
    arg = argparse.ArgumentParser()
    arg.add_argument('--url', type=str, help='example --url=ws://example.com', required=True)
    arg.add_argument('--no-verify', action='store_true')
    arg.add_argument('--credential', type=str, help='example --credential="username:password"')
    arg.add_argument('args', metavar='ARGS', nargs='*', help='Arguments', default=[])
    arg.add_argument('-c', type=str, help='Send command', default='')
    parse = arg.parse_args()
    try:
        VERIFY = not parse.no_verify
        ttyd(parse.url, parse.credential, parse.args, parse.c).run_forever()
    except InvalidAuthorization as e:
        sys.stderr.write(f'[*] {e.__str__()}')
        sys.stderr.flush()