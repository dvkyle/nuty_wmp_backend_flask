# -*- coding: utf-8 -*-
import requests
import os
from urllib.parse import urljoin

#in customer_contact put the openid
req = {
    "customer_contact": "918008271515",
    "days": "1",
}
# URL_USER_INFO=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url="/user-info")
URL_USER_INFO="http://127.0.0.1:4100/user-info"
response = requests.post(URL_USER_INFO, json=req)
print(response.json())
