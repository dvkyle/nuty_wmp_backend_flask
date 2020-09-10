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
