#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import os
import sys
import time
from urllib.parse import urljoin
import json
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.websocket import websocket_connect
from wsct import WebsocketClient

def handle_ui(msg):
    if msg == None:
        sys.exit(0)

    msg_data = json.loads(msg)
    print(msg_data)

    event = msg_data.get("event")
    if event is None:
        print(event, "Bad event.  Not found")
        return

    print(event)
    if event  == 'user-session-not-started':
        chat_client.ws.close()
    elif event == 'scbe-session-done-payment':
        chat_client.ws.close()
 
URL_START=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url='/start-smart-chiller-transaction')
URL_PRE_AUTH=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url='/pre-auth')

if __name__ == "__main__":
    req = { 
        "allowed_time": "1", 
        "platform": "wechat", 
        "openid": "9112345678", 
        "chiller_name": "nuty.multilingual-test-3",
        "nickname": "sw",
        "gender": "male",
        "avatar": "http://xxx.com/xxx.jpg",
        "tenant_id": "nuty"}             

    response = requests.post(URL_START, json=req)
    session = response.json()
    print(session)
    response = requests.post(URL_PRE_AUTH, json=session)
    session = response.json()
    session_id = session.get("session_id") or session.get("otp_session_id")
    chat_client = WebsocketClient(os.environ["WMPBE_WEBHOOK_SERVICE_CHAT"]+"/wmp"+ "?" + "session" + "=" + session_id, handle_ui, 30)
    chat_client.start_chat()
