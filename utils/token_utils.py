import sys
import json
from Crypto.Cipher import AES
from binascii import b2a_hex, a2b_hex
import time
import json
from flask import Flask, request, jsonify, Response

from utils.common import error_response
from utils.enum_collection import ErrorCode
from utils import constants

class prpcrypt():
    def __init__(self, key):
        self.key = key
        self.mode = AES.MODE_CBC

    def encrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        length = 16
        count = len(text)
        add = length - (count % length)
        text = text + ('\0' * add)
        self.ciphertext = cryptor.encrypt(text)
        token = b2a_hex(self.ciphertext)
        return token.decode()

    def decrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        plain_text = cryptor.decrypt(a2b_hex(text))
        plain_text = plain_text.decode()
        plain_text = json.loads(plain_text.strip('\0'), strict=False)
        
        return plain_text


def get_token_for_wechat(openid, expire):
    pc = prpcrypt(constants.TOKEN_PRPCRYPT_KEY)
    expire_time = int(time.time()) + expire
    print("exprire_time:"+str(expire_time))
    data = {
        "openid": openid,
        "expire": expire_time
    }
    token_data = {
        "token": pc.encrypt(json.dumps(data)),
        "code": 0
    }
    return token_data


def check_tokendata_for_wechat(token_str):
    pc = prpcrypt(constants.TOKEN_PRPCRYPT_KEY)
    data = pc.decrypt(token_str)
    if int(data['expire']) > int(time.time()):
        return data
    else:
        return error_response(code=ErrorCode.TOKEN_EXPIRED.value, message="token expired")


def token_decorator(func):
    
    def inner():
        token_str = ""
        if request.args.get('token') != None:  #websocket
            token_str = request.args.get('token')
        else:
            # token_str = request.META.get('HTTP_TOKEN') # django
            token_str = request.environ.get('HTTP_TOKEN')  # flask
        # print("token_str", token_str)
        pc = prpcrypt(constants.TOKEN_PRPCRYPT_KEY)
        data = pc.decrypt(token_str)
        if int(data['expire']) > int(time.time()):

            return func(data=data)
        else:
            return error_response(code=ErrorCode.TOKEN_EXPIRED.value, message="token expired")
    
    return inner


