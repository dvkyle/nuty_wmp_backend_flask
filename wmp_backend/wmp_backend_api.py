# -*- coding: utf-8 -*-
from OpenSSL import crypto
from flask import Flask, request, jsonify, Response
import urllib
import json
import ssl
import os
from urllib.parse import urlunsplit, urlencode, urljoin
import sys
import requests
import threading
from wsct import WebsocketClient

APPLICATION_NAME = "WMP_BACKEND"
app = Flask(APPLICATION_NAME)
ca_cert = ""
device_ca_cert = ""

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

# log = common.getLogger("wmp_backend_api")

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

@app.route("/start-smart-chiller-transaction", methods = ['POST'])
def start_smart_session():
    print("Starting new session", file=sys.stderr)
    payload = flask_incoming_payload()
    payload = {
        "allowed_time": "1",
        "platform": "wechat",
        "openid": "9112345678",
        "chiller_name": "nuty.multilingual-test-3",
        "nickname": "sw",
        "gender": "male",
        "avatar": "http://xxx.com/xxx.jpg",
        "tenant_id": "nuty"}
    return smartchiller_backend_call("/start", payload)

@app.route("/pre-auth", methods = ['POST'])
def do_pre_auth():
    print("Pre Authorization", file=sys.stderr)
    payload = flask_incoming_payload()
    return smartchiller_backend_call("/preauth", payload)

@app.route("/update-purchase", methods = ['POST'])
def do_update_purchase():
    print("Update purchase", file=sys.stderr)
    payload = flask_incoming_payload()
    print("purchase_data:"+str(payload))
    return smartchiller_backend_call("/updatepurchase", payload)

@app.route("/update-user-data", methods = ['POST'])
def do_update_user_data():
    print("Update user data", file=sys.stderr)
    payload = flask_incoming_payload()
    return smartchiller_backend_call("/updateuserdata", payload)

@app.route("/user-login", methods = ['POST'])
def do_user_login_and_info():
    print("Login and last order", file=sys.stderr)
    payload = flask_incoming_payload()
    return jsonify(smartchiller_backend_call("/userloginplusinfo", payload))

@app.route("/user-info", methods = ['POST'])
def do_user_info():
    print("Login and info", file=sys.stderr)
    payload = flask_incoming_payload()
    return jsonify(smartchiller_backend_call("/userloginplusinfo", payload))

@app.route("/register-user", methods = ['POST'])
def do_register_user():
    print("Register use", file=sys.stderr)
    payload = flask_incoming_payload()
    return jsonify(smartchiller_backend_call("/registeruser", payload))

@app.route("/scbe-session-done-payment", methods = ['POST'])
def done_payment():
    payload = flask_incoming_payload()
    print("Settle Payment", file=sys.stderr)
#   send a message using websocket
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "scbe-session-done-payment", more_payload=json.dumps(payload))
    session = smartchiller_backend_call("/finalauth", payload)
    return smartchiller_backend_call("/end", session)

@app.route("/user-door-timed-out", methods = ['POST'])
def door_timed_out():    
    print("Door timed out", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "user-door-timed-out")
    return payload

@app.route("/user-door-left-open", methods = ['POST'])
def door_left_open():
    print("User door left open", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "user-door-left-open")
    return payload

@app.route("/user-session-not-started", methods = ['POST'])
def session_not_started():
    print("User did not start session", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "user-session-not-started")
    return smartchiller_backend_call("/end", payload)

@app.route("/expired-tags-in-order", methods = ['POST'])
def expired_tags_in_order():
    print("There are expired tags in order", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the wmp
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "expired-tags-in-order", more_payload=json.dumps(payload["expired_tags_records"]))
    return payload

@app.route("/stock-alert-notification", methods = ['POST'])
def stock_alert_notification():
    print("Stock out alert", file=sys.stderr)
    payload = flask_incoming_payload()
    #inform the store owner
    return payload

@app.route("/door-closed-notification", methods = ['POST'])
def door_closed_notification():
    print("Door closed notification", file=sys.stderr)
    payload = flask_incoming_payload()
    #update wmp ui here
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "door-closed-notification")
    return payload

@app.route("/timeout-partner", methods = ['POST'])
def timeout_partner():
    print("Timeout partner", file=sys.stderr)
    payload = flask_incoming_payload()
    #update wmp ui here
    sid = payload.get("session_id") or payload.get("otp_sesssion_id")
    send_to_wmp(sid, "timeout-partner")
    return payload

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
    print("msg" + str(msg))
    event = msg.get("event")
    if event:
        print("Incoming event", event, file=sys.stderr)
        session_string = msg.get("session_details")
        if session_string:
            session_information = json.loads(session_string)
            handler = topic_handlers.get(event)
            if handler:
                handler(event, session_information)
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

if __name__ == '__main__':
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

    app.run(host="0.0.0.0", port=4100)

