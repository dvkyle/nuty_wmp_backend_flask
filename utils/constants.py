import os
import re

AZ_STOR_CNXN_STR = os.environ.get("AZ_STOR_CNXN_STR")
AZ_STOR_ACCT_KEY = os.environ.get("AZURE_STORAGE_KEY")
AZ_STOR_ACCT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT")
AZ_IMAGES_CONTAINER = os.environ.get("AZ_IMAGES_CONTAINER")
AZ_RECEIPTS_CONTAINER = os.environ.get("AZ_RECEIPTS_CONTAINER")
GDRIVE_FILE_ID = re.compile(r'id=(.+)')
GDRIVE_FILE_ID_FALLBACK = re.compile(r'/d/(.+)')
GDRIVE_DOWNLOAD_FILE_PATH = "/tmp/{sku_code}.{extension}"
GDRIVE_SCALED_DOWN_IMAGE_PATH = "/tmp/scaled-{}"

EXISTING_BLOB_URL = "https://{storage_account_name}.blob.core.windows.net/{container_name}/{file_name}"
CURRENCY = "INR"
EXPIRY_INTERVAL = "45 days"
IMAGE_FILE_SIZE_THRESHOLD_MB = 4.0
QR_CODE_DIMENSIONS=(512, 512)
QR_CODE_API = "https://api.qrserver.com/v1/create-qr-code/?size={d1}x{d2}&data={chiller_name}"
QR_CODE_DOWNLOAD_PATH = "/tmp/qr-code-{chiller_name}.png"
CURRENCIES = [
    "INR",
    "USD",
    "CNY",
    "RMB"
]

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
CACHE_TTL_SECONDS = 900
API_RESULTS_PER_PAGE = 10


# About wechat information
WECHAT = {
    "WMPAPP_ID": "wx99817fdd3500633e",  # niuty
    "WMPAPP_SERCRET": "51623c5eecef15a81e8de377e32f994e",
    "MCH_ID": 1570430991,
    "WECHAT_PAY_NOTIFY_URL": "https://xxx/thirdparty/v1/wechat_pay",
    #
    "API_KEY": "ku6ZKa8SLiP2wQieBCnm186FhzRn0HlF",
    # 代扣申请扣款地址
    "PAPORDER_URL": "https://api.mch.weixin.qq.com/pay/pappayapply",
    # 统一下单地址
    "UFDORDER": "https://api.mch.weixin.qq.com/pay/unifiedorder",
    # 查询订单url
    "SEARCH_URL": "https://api.mch.weixin.qq.com/pay/orderquery",
    # 关闭订单url
    "CLOSE_URL": "https://api.mch.weixin.qq.com/pay/closeorder",
    # 申请退款url
    "REFUND_URL": "https://api.mch.weixin.qq.com/secapi/pay/refund",
    # 查询申请退款
    "SEARCH_REFUND_URL": "https://api.mch.weixin.qq.com/pay/refundquery",
    # 服务器存放证书路径（微信支付签发的）
    "API_CLIENT_CERT_PATH": "/path/your/cert/apiclient_cert.pem",
    "API_CLIENT_KEY_PATH": "/path/your/cert/apiclient_key.pem",
    # 本地IP，申请微信代扣需要的参数
    # TODO：修改为真实服务器的IP
    "SPBILL_CREATE_IP": '127.0.0.1',

    # access_toke获取地址
    "ACCESSTOKEN_URL": "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}",
    # 微信小程序码生成接口1 maximum 100000个
    "WMPQRCODE_API_LIMITED": "https://api.weixin.qq.com/cgi-bin/wxaapp/createwxaqrcode?access_token={}",
    # 微信小程序码生成接口2 无限个
    "WMPQRCODE_API_UNLIMITED": "https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={}",
    # 签约状态查询接口
    "QUERYCONTRACT_URL": "https://api.mch.weixin.qq.com/papay/querycontract",
    # 签约模版ID
    "CONTRACT_PLAN_ID": 1,
    # 签约结果通知回调
    "AUTOPAYMENT_SIGN_RESULT_NOTIFY_URL": "https://xxx/thirdparty/v1/sign_result",
    # 获取openid的tokenurl
    "WeChatcode": "https://api.weixin.qq.com/sns/jscode2session",
    # 模版消息API
    "TEMPLATE_MSG_URL": "https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={}",
    # 待支付模版消息ID
    "UNPAID_TEMPLATE_ID": "aL_QRd_KdKMmCoHTq2hxQfx7dxT18IGHo_2gz6Wz0r8",
    # 下单成功模版消息ID
    "SUCCESSFUL_PAY_TEMPLATE_ID": "XGoB8H-8mZhua7oy1IEjSjVzue0xCY0VODIojG7eLvM",
    # 模版消息跳转小程序类型
    "MINIPROGRAM_STATE": "trial"
}
TOKEN_PRPCRYPT_KEY = "MrblOV4RsqUN8hE1"

# Smart Chiller backend information
PARTNER_NAME = 'nuty'
TENANT_ID = "nuty"

WMP_BACKEND_SERVICE_URL = "https://dev.mpbe.arfront.cn/"


