# -*- coding: utf-8 -*-
import requests
import os
from urllib.parse import urljoin

URL_LOGIN=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url="/register-user")

req = {
    "openid": "911234567890",
    "platform": "wechat",
    "nickname": "abc",
    "avatar": "http://s.jpg",
    "gender": "male"}
response = requests.post(URL_LOGIN, json=req)
print(response)
