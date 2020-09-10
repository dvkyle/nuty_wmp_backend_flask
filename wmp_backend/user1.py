# -*- coding: utf-8 -*-
import requests
import os
from urllib.parse import urljoin

URL_LOGIN=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url="/user-login")

#in customer_contact put the openid
req = {"customer_contact": "918008271515"}
response = requests.post(URL_LOGIN, json=req)
print(response.json())
