import argparse
from utils import common
from utils import constants
import telegram
import qrcode
import re

TEMPLATE = "https://{messages_api_host}/telegram-message-event/{user_type}?tenant_key={tenant_key}&bot_token={token}"

def load_tenant_key(tenant_id):
    db = common.database_connection(tenant_id)
    cursor = db.cursor()
    query = "select tenant_key from tenant_info where tenant_id = %s"
    params = (tenant_id, )
    cursor.execute(query, params)
    return cursor.fetchone()[0]


def generate_qr_code(qr_string):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=30,
        border=10
    )
    rex = re.compile(r'[\.\:\/\s\,]+')
    qr.add_data(qr_string)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    normalized = rex.sub('', qr_string)
    qr_code_filepath = "/tmp/{}.png".format(normalized)
    with open(qr_code_filepath, "wb") as destination:
        image.save(destination)
    return qr_code_filepath


def setup_bot_webhook(token, tenant_id, webhook_type, environment):
    tenant_key = load_tenant_key(tenant_id)

    if environment == "staging":
        uri = TEMPLATE.format(
            messages_api_host="ta-messages-staging.nuty.in",
            user_type=webhook_type,
            token=token,
            tenant_key=tenant_key
        )
    elif environment == "production":
        uri = TEMPLATE.format(
            messages_api_host="ta-messages.nuty.in",
            user_type=webhook_type,
            token=token,
            tenant_key=tenant_key
        )
    elif environment == "staging-cn":
        uri = TEMPLATE.format(
            messages_api_host="tulitahara-messages.chinanorth2.cloudapp.chinacloudapi.cn",
            user_type=webhook_type,
            tenant_key=tenant_key,
            token=token
        )
    bot = telegram.Bot(token)
    try:
        webhook_set = bot.setWebhook(url=uri)
        if not webhook_set:
            print ("Unable to set webhook ", uri)
            return

        print ("Webhook set for ", uri)
        webhook_info = bot.getWebhookInfo()
        print ("Webhook info: ", webhook_info)
        t_me_qr_file = generate_qr_code(bot.link)
        print ("Bot link: %s, QR code written to: %s" %(bot.link, t_me_qr_file))
    except telegram.TelegramError as terr:
        print (terr)


def main():
    parser = argparse.ArgumentParser(prog="set_up_telegram_webhook.py")
    parser.add_argument("-w", "--webhook-type", choices=["admin", "customer", "loader", "franchisee"], required=True, dest="webhook_type")
    parser.add_argument("-t", "--tenant-id", required=True, dest="tenant_id")
    parser.add_argument("-k", "--token", required=True, dest="token")
    parser.add_argument("-e", "--environment", required=False, choices=["staging", "production", "staging-cn"], default="staging")

    arguments = parser.parse_args()

    tenant_id = arguments.tenant_id
    token = arguments.token
    webhook_type = arguments.webhook_type
    environment = arguments.environment

    setup_bot_webhook(token, tenant_id, webhook_type, environment)


if __name__ == "__main__":
    main()
