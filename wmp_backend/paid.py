# -*- coding: utf-8 -*-
import requests
import os
from urllib.parse import urljoin

URL_UPDATE_PURCHASE=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url='/update-purchase')

#ord-75812e18d7-e08a47b 

#in customer_contact put the openid
req = { 
    "order_id": "#ord-75812e18d7-e08a47b", 
    "amount_paid": "99",
    "invoice_data": "test both",
    "customer_contact": "918008271515"}
response = requests.post(URL_UPDATE_PURCHASE, json=req)
print(response.json())

#in customer_contact put the openid
req = { 
    "order_id": "#ord-75812e18d7-e08a47b", 
    "amount_paid": "99",
    "customer_contact": "918008271515"}
response = requests.post(URL_UPDATE_PURCHASE, json=req)
print(response.json())

#in customer_contact put the openid
req = { 
    "order_id": "#ord-75812e18d7-e08a47b", 
    "invoice_data": "test invoice",
    "customer_contact": "918008271515"}
response = requests.post(URL_UPDATE_PURCHASE, json=req)
print(response.json())

URL_UPDATE_USER_DATA=urljoin(base=os.environ["WMPBE_WEBHOOK_SERVICE"], url='/update-user-data')
#in customer_contact put the openid
req = { 
    "order_id": "#ord-75812e18d7-e08a47b", 
    "user_data": "test user_data",
    "customer_contact": "918008271515"}
response = requests.post(URL_UPDATE_USER_DATA, json=req)
print(response.json())
