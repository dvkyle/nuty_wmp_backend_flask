

from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.websocket import websocket_connect
import json

class WebsocketClient(object):
    def __init__(self, url, callback, timeout):
        print(url)
        self.connect_url = url
        self.callback = callback
        self.timeout = timeout

    def start_chat(self):
        self.ioloop = IOLoop.instance()
        self.ws = None
        self.connect()
        PeriodicCallback(self.keep_alive, 20000).start()
        self.ioloop.start()

    @gen.coroutine
    def connect(self):
        print("trying to connect", self.connect_url)
        try:
            self.ws = yield websocket_connect(self.connect_url)
        except Exception as e:
            print("connection error", e)
        else:
            print("connected", self.connect_url)
            self.run()

    @gen.coroutine
    def run(self):
        while True:
            msg = yield self.ws.read_message()
            if msg is None:
                print("connection closed", self.connect_url)
                self.callback(None)
                break
            else:
                self.callback(msg)

    def keep_alive(self):
        if self.ws is None:
            self.connect()
        else:
            self.ws.write_message("keep alive")
