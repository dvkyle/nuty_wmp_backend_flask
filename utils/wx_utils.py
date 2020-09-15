import hashlib
import json
import threading
import time
import requests
from collections import OrderedDict
from random import Random
from bs4 import BeautifulSoup
from random import Random
from utils import constants
import logging
from utils.common import error_response
from utils.enum_collection import ErrorCode
from flask import Flask, request, jsonify, Response
from wmp_backend import wmp_backend_api


logger_wx = logging.getLogger("wechat")

# 微信公众号、商户平台基础配置
APP_ID = constants.WECHAT["WMPAPP_ID"]
API_KEY = constants.WECHAT["API_KEY"]
APP_SECRECT = constants.WECHAT["WMPAPP_SERCRET"]
spbill_create_ip = constants.WECHAT["SPBILL_CREATE_IP"]
MCH_ID = constants.WECHAT["MCH_ID"]


def get_openid(code):
    """
    获取微信的openid
    :param code:
    :return:
    """
    if code:

        WeChatcode = constants.WECHAT["WeChatcode"]
        urlinfo = OrderedDict()
        urlinfo['appid'] = APP_ID
        urlinfo['secret'] = APP_SECRECT
        urlinfo['js_code'] = code
        urlinfo['grant_type'] = 'authorization_code'
        info = requests.get(url=WeChatcode, params=urlinfo)
        info_dict = eval(info.content.decode('utf-8'))
        print(info_dict)
        return info_dict['openid']
    return error_response(code=ErrorCode.MISSED_PARAS.value, message="missed code")


def random_str(randomlength=8):
    """
    生成随机字符串
    :param randomlength: 字符串长度
    :return:
    """
    str = ''
    chars = 'AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz0123456789'
    length = len(chars) - 1
    random = Random()
    for i in range(randomlength):
        str += chars[random.randint(0, length)]
    return str


def create_out_trade_no():
    """
    create order number
    :return:
    """
    local_time = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    result = 'wx{}'.format(local_time[2:])
    return result


def get_sign(data_dict, key):
    # 签名函数，参数为签名的数据和密钥
    params_list = sorted(data_dict.items(), key=lambda e: e[0], reverse=False)  # 参数字典倒排序为列表
    params_str = "&".join(u"{}={}".format(k, v) for k, v in params_list) + '&key=' + key
    # 组织参数字符串并在末尾添加商户交易密钥
    md5 = hashlib.md5()  # 使用MD5加密模式
    md5.update(params_str.encode('utf-8'))  # 将参数字符串传入
    sign = md5.hexdigest().upper()  # 完成加密并转为大写
    return sign


def trans_dict_to_xml(data_dict):  # 定义字典转XML的函数
    data_xml = []
    for k in sorted(data_dict.keys()):  # 遍历字典排序后的key
        v = data_dict.get(k)  # 取出字典中key对应的value
        if k == 'detail' and not v.startswith('<![CDATA['):  # 添加XML标记
            v = '<![CDATA[{}]]>'.format(v)
        data_xml.append('<{key}>{value}</{key}>'.format(key=k, value=v))
    return '<xml>{}</xml>'.format(''.join(data_xml)).encode('utf-8')  # 返回XML，并转成utf-8，解决中文的问题


def trans_xml_to_dict(data_xml):
    soup = BeautifulSoup(data_xml, features='xml')
    xml = soup.find('xml')  # 解析XML
    if not xml:
        return {}
    data_dict = dict([(item.name, item.text) for item in xml.find_all()])
    return data_dict


def wx_pay_unifiedorder(data):
    """
    访问微信支付统一下单接口
    :param detail:
    :return:
    """
    data['sign'] = get_sign(data, API_KEY)
    xml = trans_dict_to_xml(data)
    rsp = requests.request('post', constants.WECHAT["UFDORDER"], data=xml)

    return rsp.content


def wx_pay_params(openid, order_id):
    """
    补全微信支付需要参数
    :param openid:微信小程序用户的openid
    :param total_fee:支付金额
    :return:
    """
    
    params = {
        'appid': APP_ID,
        'mch_id': MCH_ID,
        'device_info': "WEB",
        'nonce_str': random_str(16),
        'out_trade_no': order_id,
        'total_fee': int(round(float(0.01), 2) * 100),
        'spbill_create_ip': spbill_create_ip,
        'openid': openid,
        'sign_type': "MD5",
        'notify_url': '{0}/thirdparty/wechatpaynotify'.format(constants.WMP_BACKEND_SERVICE_URL),  # 微信支付结果回调url
        'body': '{0}'.format('nuty自助购物'),  # 商品描述
        'trade_type': 'JSAPI',  # 代扣支付类型
        'attach': '支付测试'
        }

    # 调用微信统一下单支付接口url
    notify_result = wx_pay_unifiedorder(params)
    tmp_str = notify_result.decode()
    notify_result = trans_xml_to_dict(tmp_str)
    if 'result_code' in notify_result and notify_result['result_code'] == 'FAIL':
        return error_response(message=notify_result['err_code_des'])

    # print('获取到的参数', params)
    wmp_params = dict()
    wmp_params["appId"] = APP_ID
    wmp_params["timeStamp"] = str(int(time.time()))
    wmp_params["nonceStr"] = random_str(16)
    wmp_params["package"] = "prepay_id=" + notify_result["prepay_id"]
    wmp_params["signType"] = "MD5"
    wmp_params['paySign'] = get_sign(wmp_params, API_KEY)
    return jsonify(data={'code': 0, 'msg': 'success', 'data': wmp_params})


def wx_pay_success(data):

    logger_wx.info("wechat pay response:", str(data))

    try:
        # 1.tell SCBE order is done
        req = {
            "order_id": data["out_trade_no"],
            "amount_paid": data["total_fee"],
            "customer_contact": data["openid"]
        }
        rep = wmp_backend_api.smartchiller_backend_call("/updatepurchase", req)

    except:
        logger_wx.info("wx call back exception,req:{}".format(req))


#  get access_token
def get_access_token():
    url = constants.WECHAT["ACCESSTOKEN_URL"].format(constants.WECHAT["WMPAPP_ID"],
            constants.WECHAT["WMPAPP_SERCRET"])

    rsp = requests.get(url)
    rsp.raise_for_status()
    logger_wx.info("wechat response elapsed[%s] url[%s], data[%s]",
                   rsp.elapsed, url, rsp.content)

    json_rsp = rsp.json()
    if "errcode" in json_rsp:
        logger_wx.error("get access_token error code:{},msg:{}".format(json_rsp["errcode"], json_rsp['errmsg']))

    return json_rsp.get("access_token")


