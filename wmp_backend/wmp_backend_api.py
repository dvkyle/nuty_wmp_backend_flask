# -*- coding: utf-8 -*-
from OpenSSL import crypto
from flask import Flask, request, jsonify, Response
import urllib
import json
import ssl
from urllib.parse import urljoin
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
import requests
import threading
from utils import token_utils, wx_utils
from wmp_backend.wsct import WebsocketClient
from utils import constants
from utils.token_utils import token_decorator
from utils import common
from utils.enum_collection import ErrorCode

APPLICATION_NAME = "WMP_BACKEND"

app = Flask(APPLICATION_NAME)
PREFIX = "/api"
ca_cert = ""
device_ca_cert = ""
WEBSOCKET_USER_DICT = dict()
websocket_thread = None

topics = [
    "scbe_session_done_payment",
    "user_door_timed_out",
    "user_door_left_open",
    "user_session_not_started",
    "expired_tags_in_order",
    "stock_alert_notification",
    "door_closed_notification",
    "timeout_partner"]

log = common.getLogger("wmp_backend_api")

def send_to_wmp(sid, event, more_payload=None):
    base_url=os.environ["WMP_CHAT_SERVICE_POD"]+"/notify"
#    base_url="https://wmp-chat:4101/notify"
    params = {"session": sid,
        "message": event
    }
    if more_payload:
        params["more"] = more_payload
    response = requests.get(base_url, params=params)
    print(response, file=sys.stderr)

def done_payment_handler(event, payload):
    print("Settle Payment", file=sys.stderr)
#   send a message using websocket
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "scbe-session-done-payment", more_payload=json.dumps(payload))
    session = smartchiller_backend_call("/finalauth", payload)
    rval = smartchiller_backend_call("/end", session)
    websocket_thread.chat_client.ws.write_message(json.dumps(rval))
    return rval

def user_door_timed_out_handler(sid, payload):
    print("Door timed out", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "user-door-timed-out", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

def user_door_left_open_handler(sid, payload):
    print("User left door open", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "user-left-door-open", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

def user_session_not_started_handler(sid, payload):
    print("User session did not start", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "user-session-not-started", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

def expired_tags_in_order_handler(sid, payload):
    print("Expired tags in order", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "expired-tags-in-order", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

def stock_alert_notification_handler(sid, payload):
    print("Stock alert notification", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "stock-alert-notification", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

def door_closed_notification_handler(sid, payload):
    print("Door closed by user", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "door-closed-notification", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

def timeout_partner_handler(sid, payload):
    print("Timeout by server", file=sys.stderr)
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "timeout-partner", more_payload=json.dumps(payload))
    websocket_thread.chat_client.ws.write_message(json.dumps(payload))

topic_handlers = {
    "scbe_session_done_payment": done_payment_handler,
    "user_door_timed_out": user_door_timed_out_handler,
    "user_door_left_open": user_door_left_open_handler,
    "user_session_not_started": user_session_not_started_handler,
    "expired_tags_in_order": expired_tags_in_order_handler,
    "stock_alert_notification": stock_alert_notification_handler,
    "door_closed_notification": door_closed_notification_handler,
    "timeout_partner": timeout_partner_handler}

def flask_incoming_payload():
    payload = request.json
    if not payload:
        payload = request.args
        payload = payload.to_dict()
    return payload

def smartchiller_backend_call(link, payload):
    scbend_url = urljoin(base=os.environ["SCBACKEND_URL"], url=link)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.check_hostname = False
    context.load_cert_chain(certfile='partner-cert.pem', keyfile='partner-cert.key')
    context.load_verify_locations(cadata=device_ca_cert)

    data_json = json.dumps(payload)
    req = urllib.request.Request(scbend_url, data=data_json.encode(encoding='UTF8'), headers={"Content-Type": "application/json"})
    response = urllib.request.urlopen(req, context=context)

    string_response = response.read().decode('utf-8')
    json_obj = json.loads(string_response)
    return json_obj

@app.route("/", methods = ['GET'])
def index():
    return "Nuty wmp_backend flask is running "

@app.route(PREFIX + "/start-smart-chiller-transaction", methods=['POST'], endpoint="start")
@token_decorator
def start_smart_session(**kwargs):
    print("Starting new session", file=sys.stderr)
    payload = flask_incoming_payload()
    openid = kwargs["data"]["openid"]
    if not openid or not payload['chiller_name']:
        return common.error_response(code=ErrorCode.MISSED_PARAS.value, message="missed openid or chiller_name")

    # 1. Build data
    req = dict()
    req['allowed_time'] = "1"
    req['chiller_name'] = payload['chiller_name']
    req['openid'] = openid
    req['platform'] = 'wechat'
    req['tenant_id'] = constants.TENANT_ID

    log.info("start req:{}".format(str(req)))
    # 2. request start api
    try:
        rep = smartchiller_backend_call("/start", req)
    except:
        log.info("error req:".format(req))
        return common.error_response(code=ErrorCode.CONNECTION_ERROR.value, message="can not connect to nuty cloud")

    # 3. verify data
    if not rep['session_id']:
        return common.error_response(code=ErrorCode.CHILLER_ERROR.value, message="unknow error")

    try:
        if not rep["last_order"]:
            rep = smartchiller_backend_call("/preauth", rep)
        else:
            log.info("upaid order {} :".format(rep["last_order"]))
            unpaid_data = dict()
            unpaid_data['data'] = ""
            unpaid_data["code"] = ErrorCode.USER_UNPAID.value
            unpaid_data["msg"] = "user has unpaid order"
            last_order_dict = json.loads(rep["last_order"])
            unpaid_data["data"] = dict()
            unpaid_data["data"]["order_id"] = last_order_dict['order_id']
            unpaid_data["data"]["openid"] = rep["user_id"]
            unpaid_data["data"]["amount"] = last_order_dict['amount']
            return jsonify(data=unpaid_data)

    except:
        return common.error_response(code=ErrorCode.CONNECTION_ERROR.value, message=_("can't connect to nuty cloud"))

    # 4.tell frontend the door has opened
    log.info("User [{}] opened [{}] ".format(openid, payload['chiller_name']))

    data = dict()
    data["msg"] = "User [{}] opened [{}] ".format(openid, payload['chiller_name'])
    data["code"] = 0
    data["sid"] = rep['session_id']

    return jsonify(data=data)


@app.route(PREFIX + "/pre-auth", methods = ['POST'])
def do_pre_auth():
    print("Pre Authorization", file=sys.stderr)
    payload = flask_incoming_payload()
    return smartchiller_backend_call("/preauth", payload)

@app.route(PREFIX + "/update-purchase", methods = ['POST'])
def do_update_purchase():
    print("Update purchase", file=sys.stderr)
    payload = flask_incoming_payload()
    print("purchase_data:"+str(payload))
    return smartchiller_backend_call("/updatepurchase", payload)

@app.route(PREFIX + "/update-user-data", methods = ['POST'])
def do_update_user_data():
    print("Update user data", file=sys.stderr)
    payload = flask_incoming_payload()
    return smartchiller_backend_call("/updateuserdata", payload)

@app.route(PREFIX + "/user-login", methods = ['POST'])
def do_user_login_and_info():
    print("Login and last order", file=sys.stderr)
    payload = flask_incoming_payload()
    return jsonify(smartchiller_backend_call("/userloginplusinfo", payload))

@app.route(PREFIX + "/userorderlist", methods = ['POST'], endpoint="orderlist")
def do_user_info():
    print("User order list", file=sys.stderr)
    payload = flask_incoming_payload()
    return jsonify(smartchiller_backend_call("/userloginplusinfo", payload))


@app.route(PREFIX + "/order-detail", methods = ['GET'])
def order_detail():
    print("Order detail", file=sys.stderr)
    payload = flask_incoming_payload()
    # payload = {"order_id" : order_id}
    return smartchiller_backend_call("/orderdetail", payload)

@app.route(PREFIX + "/register-user", methods = ['POST'], endpoint="register")
@token_decorator
def do_register_user(*args, **kwargs):
    print("Register use", file=sys.stderr)
    openid = kwargs["data"]["openid"]
    payload = flask_incoming_payload()
    user_data = {
        "openid": openid,
        "platform": "wechat",
        "nickname": payload["nickName"],
        "gender": "male" if payload["gender"] == 1 else "female",
        "avatar": payload["avatarUrl"]
    }
    return smartchiller_backend_call("/registeruser", user_data)

@app.route(PREFIX + "/scbe-session-done-payment", methods = ['POST'])
def done_payment():
    payload = flask_incoming_payload()
    print("Settle Payment", file=sys.stderr)
#   send a message using websocket
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "scbe-session-done-payment", more_payload=json.dumps(payload))
    session = smartchiller_backend_call("/finalauth", payload)
    return smartchiller_backend_call("/end", session)

@app.route(PREFIX + "/user-door-timed-out", methods = ['POST'])
def door_timed_out():    
    print("Door timed out", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "user-door-timed-out")
    return payload

@app.route(PREFIX + "/user-door-left-open", methods = ['POST'])
def door_left_open():
    print("User door left open", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "user-door-left-open")
    return payload

@app.route(PREFIX + "/user-session-not-started", methods = ['POST'])
def session_not_started():
    print("User did not start session", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "user-session-not-started")
    return smartchiller_backend_call("/end", payload)

@app.route(PREFIX + "/expired-tags-in-order", methods = ['POST'])
def expired_tags_in_order():
    print("There are expired tags in order", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "expired-tags-in-order", more_payload=json.dumps(payload["expired_tags_records"]))
    return payload

@app.route(PREFIX + "/stock-alert-notification", methods = ['POST'])
def stock_alert_notification():
    print("Stock out alert", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the store owner
    return payload

@app.route(PREFIX + "/door-closed-notification", methods = ['POST'])
def door_closed_notification():
    print("Door closed notification", file=sys.stderr)
    payload = flask_incoming_payload()
    #update wmp ui here
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "door-closed-notification")
    return payload

@app.route(PREFIX + "/timeout-partner", methods = ['POST'])
def timeout_partner():
    print("Timeout partner", file=sys.stderr)
    payload = flask_incoming_payload()
    #update wmp ui here
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp_frontend(sid, "timeout-partner")
    return payload


@app.route(PREFIX + "/test", methods=['GET'])
def test():
    return jsonify(token_utils.get_token_for_wechat("918008271515", 3600 * 360))


@app.route(PREFIX + "/test1", methods=['GET'])
def test1():
    payload = flask_incoming_payload()
    if not request:
        return "simple str"
    print(payload)
    print(os.environ['CA_URL'])
    return jsonify(data={'data':"haha"})


@app.route(PREFIX + "/get_user_token", methods=['GET'])
def get_wxuser_token():
    code = request.args.get('code')
    openid = wx_utils.get_openid(code)

    return jsonify(data=token_utils.get_token_for_wechat(openid, 3600 * 8))


@app.route(PREFIX + "/get_qrcode", methods=['GET'])
def make_qrcode():
    chiller_name = request.args.get('chiller_name')
    if not chiller_name:
        return common.error_response(code=ErrorCode.MISSED_PARAS.value, message="missed chillid or chiller name")

    # TODO: limit api request times per day
    # redis = get_redis_connection()
    # redis.hincrby('qrcode_create_time',get_request_ip(request),1)
    # if redis.ttl('qrcode_create_time') < 0:
    #     redis.expire('qrcode_create_time',seconds_to_next_day)

    access_token = wx_utils.get_access_token()
    if not access_token:
        return common.error_response(code=ErrorCode.UNKNOWN.value, message="access token error")
    else:
        url = constants.WECHAT['WMPQRCODE_API_LIMITED'].format(access_token)
        data = {"path": "pages/openDoor/openDoor?chiller_name={}".format(chiller_name),
                "width": 600,
                }

        ret = requests.post(url, json=data)
        log.info("qrcode created ,chiller_name:%s", str(chiller_name))
        return Response(ret, content_type='image/png')


@app.route('/wechat-pay-request', methods=['GET'])
@token_decorator
def WXPayRequest(request, *args, **kwargs):
    """从智能柜端获取微信支付参数并向微信申请扣款"""
    openid = kwargs["data"]["openid"]
    orderid = request.POST.get('orderid')
    if '' or None in [openid, orderid]:
        return common.error_response(code=ErrorCode.MISSED_PARAS.value, message="missed openid or orderid")
    return wx_utils.wx_pay_params(openid, orderid)


@app.route('/thirdparty/wechatpaynotify', methods=['POST'])
def post(self, request, *args, **kwargs):
    data_dict = wx_utils.trans_xml_to_dict(request.body)  # 回调数据转字典
    log.info("response POST body: [%s]", data_dict)
    sign = data_dict.pop('sign')  # 取出签名
    back_sign = wx_utils.get_sign(data_dict, constants.WECHAT['API_KEY'])  # 计算签名
    # 验证签名是否与回调签名相同
    if sign == back_sign and data_dict['result_code'] == 'SUCCESS':
        # 调用支付成功后处理函数
        wx_utils.wx_pay_success(data_dict)
        # print('支付完成')
        return Response(wx_utils.trans_dict_to_xml({'return_code': 'SUCCESS', 'return_msg': 'OK'}))
    return Response(wx_utils.trans_dict_to_xml({'return_code': 'FAIL', 'return_msg': 'SIGNERROR'}))


@app.route('/wmp_websocket')
def connect_websocket():
    user_count = 0
    sid = ""
    try:
        # 1. http request not include wsgi.websocket
        ws = request.environ.get('wsgi.websocket')
        if not ws:
            return 'pls use websocket'
        # websocket request
        sid = request.args.get("sid")
        if WEBSOCKET_USER_DICT.get(sid) is None:
            user_count = user_count + 1
            WEBSOCKET_USER_DICT[sid] = ws
        while True:
            message = ws.receive()
            ws.send('websocket conneted:' + str(user_count)+" msg :"+message)
    except:
        pass
    finally:
        if sid in WEBSOCKET_USER_DICT:
            WEBSOCKET_USER_DICT.pop(sid)
            log.info("sid deleted:" + sid)
            user_count = user_count - 1
        return {"msg":"websocket break"}


def send_to_wmp_frontend(sid,  event, more_data=None):
    if sid in WEBSOCKET_USER_DICT:
        print("openid exist")
        data = {"event": event}
        if more_data:
            data['data'] = more_data
        WEBSOCKET_USER_DICT[sid].send(json.dumps(data).encode('utf-8'))
        log.info("user event {} has sent to sid{}".format(event,sid))
        print("msg sent")
        return True
    else:
        log.info("user has broken the websocket:{}".format(sid))
        print("openid not exist，msg not send")
        return False


def enroll():
    enroll_url = os.environ["CA_URL_ENROLL_PARTNER_APP"]

    partner_cert_path = 'partner-cert.pem'
    partner_cert = None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.check_hostname = False
    context.load_verify_locations(cadata=ca_cert)
    context.verify_mode = ssl.CERT_NONE

    with open(partner_cert_path, "r") as file:
        partner_cert = file.read()
    data = {
        "partner_certificate": partner_cert
    }

    data_json = json.dumps(data)

    req = urllib.request.Request(enroll_url, data=data_json.encode(encoding='UTF8'), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, context=context)


def prepare_hooks():
    hooks = dict()

    base_path = os.environ.get("WMPBE_WEBHOOK_SERVICE", "")

    for topic in topics:
        hook_api = urljoin(base=base_path, url=topic.replace('_', '-'))
        hooks[topic] = hook_api
    return hooks

def get_partnername():
    cert_path = 'partner-cert.pem'
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_path).read())
    subject = cert.get_subject()
    issued_to = subject.CN
    return issued_to

def get_trust_chain():
    ca_url = os.environ["CA_URL"]

    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(ca_url, headers={"Content-Type": "application/json"})
    response = urllib.request.urlopen(req, context=context) 

    string_response = response.read().decode('utf-8')
    json_obj = json.loads(string_response)

    global ca_cert
    global device_ca_cert

    ca_cert = json_obj['ca_cert']
    device_ca_cert = json_obj['device_cert']

def setup_hooks(hooks):
    scbend_url = os.environ["SCBACKEND_URL"]+"/webhooks"

    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.check_hostname = False
    context.load_cert_chain(certfile='partner-cert.pem', keyfile='partner-cert.key')
    context.load_verify_locations(cadata=device_ca_cert)

    if hooks:
        data_json = json.dumps(hooks)
    else:
        data_json = json.dumps({"web_socket": "using_websocket"})

    req = urllib.request.Request(scbend_url, data=data_json.encode(encoding='UTF8'), headers={"Content-Type": "application/json"})
    response = urllib.request.urlopen(req, context=context)
    string_response = response.read().decode('utf-8')
    json_obj = json.loads(string_response)

    print(json_obj, file=sys.stderr)


def send_to_wmp_client(in_msg):
    msg = json.loads(in_msg)
    import time
    print(time.strftime('%H:%M:%S',time.localtime(time.time())) + str(msg))
    event = msg.get("event")
    if event:
        print("Incoming event", event, file=sys.stderr)
        session_string = msg.get("session_details")
        if session_string:
            session_information = json.loads(session_string)
            handler = topic_handlers.get(event)
            if handler:
                # handler(event, session_information)
                url = "http://127.0.0.1:8000/{}".format(event.replace('_', '-'))
                ret = requests.post(url, data=msg.get('session_details'))
                print(ret)
            else:
                print("No handler for topic", file=sys.stderr)
        else:
            print("Bad incoming message. Session information not found", file=sys.stderr)
    else:
        print("Bad incoming message. Event not found", file=sys.stderr)


class WebsocketThread (threading.Thread):
   def __init__(self, name, callback):
        threading.Thread.__init__(self)
        self.name = name
        self.chat_client = WebsocketClient(os.environ["WMPBE_WEBHOOK_SERVICE_CHAT"]+"/wmphook"+ "?" + "partner" + "=" + self.name, callback, 30)

   def run(self):
      print ("Starting " + self.name)
      self.chat_client.start_chat()
      print ("Exiting " + self.name)


def set_environ():
    os.environ['CA_URL'] = "https://tulitahara-ca.southeastasia.cloudapp.azure.com:4443"
    os.environ['WMPBE_WEBHOOK_SERVICE'] = "https://dev.mpbe.arfront.cn"
    os.environ['WMPBE_API_SERVICE'] = "https://partner-staging.nuty.in"
    os.environ['SCBACKEND_URL'] = "https://tulitahara-scbend.southeastasia.cloudapp.azure.com:8449"
    os.environ[
        'CA_URL_ENROLL_PARTNER_APP'] = "https://tulitahara-ca.southeastasia.cloudapp.azure.com:4443/enroll-partner-app"
    os.environ['WMPBE_WEBHOOK_SERVICE_CHAT'] = "wss://partner-staging.nuty.in"


if __name__ == '__main__':
    set_environ()
    get_trust_chain()
    enroll()
    partner_name = get_partnername()

    if len(sys.argv) > 1:
        if sys.argv[1] == "websocket":
            setup_hooks(None)
            websocket_thread = WebsocketThread(partner_name, send_to_wmp_client)
            websocket_thread.run()
        else:
            print("Bad command line")
    else:
        hooks = prepare_hooks()
        print (hooks)
        setup_hooks(hooks)

    app.run(host="0.0.0.0", port=4100, debug=True)

    # support websocket for client
    # from geventwebsocket.handler import WebSocketHandler
    # from gevent.pywsgi import WSGIServer
    # http_server = WSGIServer(('127.0.0.1', 4100), app, handler_class=WebSocketHandler)
    # http_server.serve_forever()
