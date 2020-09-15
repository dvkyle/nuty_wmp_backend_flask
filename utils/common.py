import logging
import cachetools
import os
import gspread
import traceback
import csv
import json,time,datetime,status

from PIL import Image
from . import constants
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import connect
from azure.storage.blob import BlobServiceClient, ContainerClient
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from redis import Redis
from flask import Flask, request, jsonify, Response
import status



from cryptography.fernet import Fernet
key = 'Ei6nPc5f-XUbN7Wev2DOWhL0BBT2SfLb3saw06uohwQ='
 

logging.basicConfig(
    format="[%(asctime)s] - %(levelname)s - %(name)s - %(message)s",
    # format="{\"level\": \"%(levelname)s\", \"name\": \"%(name)s\" \"msg\": \"%(message)s\", \"time\": \"%(asctime)s\"}",
    level=logging.INFO
)

SUPPRESSED_LOGGERS = [
    "azure.storage.common.storageclient",
    "azure.core.pipeline.policies.http_logging_policy",
    "googleapiclient.discovery",
    "oauth2client.client"
]

BLOB_TTL_CACHE = cachetools.TTLCache(maxsize=999, ttl=constants.CACHE_TTL_SECONDS)
STORE_TTL_CACHE = cachetools.TTLCache(999, constants.CACHE_TTL_SECONDS)
ADMIN_DETAILS_TTL_CACHE = cachetools.TTLCache(999, constants.CACHE_TTL_SECONDS)
TENANT_CREDENTIALS_TTL_CACHE = cachetools.TTLCache(999, constants.CACHE_TTL_SECONDS)

for logger in SUPPRESSED_LOGGERS:
    logging.getLogger(logger).setLevel(logging.ERROR)


@cachetools.cached({})
def getLogger(name):
    return logging.getLogger(name)


def master_database_connection(application_name=None, autocommit=True):
    log = getLogger('master_database_connection')
    try:
        log.info("Trying to spin up a master database connection")
        db_dsn = "host={host} port={port} dbname={dbname} user={user} password={password}".format(
            host=os.environ.get("DB_HOST"),
            dbname=os.environ.get("DB_NAME"),
            port=os.environ.get("DB_PORT"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        if not os.environ.get("DEV"):
            db_dsn += " sslmode=require"
        connection = connect(db_dsn)
        if not connection:
            log.warning("DB Connection not created!")
            return None
        connection.autocommit = autocommit
        return connection
    except Exception as exp:
        log.exception(exp)
        return None


@cachetools.cached({})
def try_create_azure_container(container_name):
    log = getLogger('try_create_azure_container')
    log.info("Attempting to create container %s if it does not exist already", container_name)
    try:
        blob_service_client = BlobServiceClient.from_connection_string(constants.AZ_STOR_CNXN_STR)
        return blob_service_client.get_container_client(container_name)
    except Exception as exp:
        log.exception("Unable to spin up Azure container client for container %s. Reason: %s.\n%s", container_name, exp, traceback.print_exc())
        raise exp


def image_size_within_threshold(image_file):
    log = getLogger('image_size_within_threshold')
    try:
        log.info("Checking if %s is less than %s MB", image_file, constants.IMAGE_FILE_SIZE_THRESHOLD_MB)
        size_mb = round(
            os.stat(image_file).st_size / (1024 * 1024),
            ndigits=1
        )
        log.info("Image size: %s MB", size_mb)
        return size_mb <= constants.IMAGE_FILE_SIZE_THRESHOLD_MB
    except Exception as exp:
        log.exception(exp)
        return False


def scale_down_image(image_file):
    log = getLogger('scale_down_image')
    if image_size_within_threshold(image_file):
        return image_file
    log.warning("Image %s too large for whatsapp. Scaling down", image_file)
    img = Image.open(image_file)
    width, height = img.size
    scale_factor = (int(width/2), int(height/2))
    scaled_down = img.resize(scale_factor)
    image_name = image_file.split('/')[-1]
    scaled_down_destination = constants.GDRIVE_SCALED_DOWN_IMAGE_PATH.format(image_name)
    with open(scaled_down_destination, "wb") as destination:
        scaled_down.save(destination)
    return destination.name


def upload_to_azure_storage(tenant_name, filename, container_name, filetype):
    log = getLogger('upload_to_azure_storage')
    log.info("Uploading %s to Azure storage account", filename)
    name = "%s/%s" %(tenant_name, filename.split('/')[-1].replace(' ', ''))
    client = try_create_azure_container(container_name)
    to_upload = None
    if not client:
        log.warning("Container client not created. Will not upload %s to Azure container", filename)
        return

    # determine what is to be uploaded
    if filetype == "image":
        # scale down image if needed
        corrected_image = scale_down_image(filename)
        to_upload = corrected_image
    else:
        to_upload = filename

    with open(to_upload, 'rb') as upload_source: 
        upload_result = client.upload_blob(data=upload_source, name=name, overwrite=True)
        log.info("File %s uploaded to azure", filename)
        return upload_result.url


@cachetools.cached(BLOB_TTL_CACHE)
def list_blobs_in_azure_container(container):
    log = getLogger("list_blobs_in_azure_container")
    log.info("Listing blobs in container %s", container)
    try:
        container_client = try_create_azure_container(container)
        lazy_blob_list = container_client.list_blobs()
        return set([x.name for x in lazy_blob_list])
    except Exception as exp:
        log.exception(exp)
        return None


@cachetools.cached({})
def azure_blob_to_download(container, blob_name):
    available_blobs = list_blobs_in_azure_container(container)
    if not available_blobs:
        return None
    log = getLogger("azure_blob_to_download")
    log.info("Looking for the correct blob to download")
    for blob in available_blobs:
        if blob_name in blob:
            log.info("Relevant blob for filename %s found: %s", blob, blob_name)
            return blob


def download_from_azure_storage(tenant_name, filename, container, dest_path):
    log = getLogger('download_from_azure_storage')
    blob_name = "%s/%s" %(tenant_name, filename)
    blob_name = blob_name.replace(' ', '')
    log.info("Downloading blob %s from container %s to file %s", filename, container, dest_path)
    container_client = try_create_azure_container(container)
    if not container_client:
        log.warn("Unable to create container client")
        return None
    corrected_filename = azure_blob_to_download(container, blob_name)
    with open(dest_path, "wb") as download_path:
        try:
            storage_stream_downloader = container_client.download_blob(corrected_filename)
            storage_stream_downloader.readinto(download_path)
            log.info("Downloaded file to %s", download_path.name)
            return download_path.name, storage_stream_downloader.properties["content_settings"]["content_type"], corrected_filename
        except Exception as exp:
            log.exception("An attempt to download file %s to destination %s failed. Reason: %s", filename, dest_path, exp)
            log.exception(traceback.print_exc())
            download_path.close()
            os.remove(dest_path)
            raise exp


def load_records(source_csv_file):
    try:
        with open(source_csv_file) as source:
            reader = csv.DictReader(source)
            return [ line for line in reader ]
    except Exception as exp:
        logging.error("Unable to load inventory records!. Reason: %s" %(exp))
        return None


@cachetools.cached({})
def get_expiry_interval(sku_code):
    query = """
    select expiry from item_master where sku_code = %s
    """
    params = (sku_code, )

    # obtaining db connection to tulitahara db since it is not clear if this needs to be multi-tenant
    try:
        cnxn = master_database_connection("tulitahara")
        cursor = cnxn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        return result[0]
    except Exception as exp:
        logging.exception("Unable to get expiry interval for %s. Reason: %s", sku_code, exp)
        return None


def send_mail(mail_info):
    log = getLogger("send_mail")
    # keys of mail_info receiving_email,cc,body,attachments,subject id and password need to be set in environment variable REPORT_SENDER_EMAIL,REPORT_SENDER_PASSWORD
    sender = os.environ['REPORT_SENDER_EMAIL'] # sender mail id
    data = MIMEMultipart()
    data['From'] = sender
    data['To'] = mail_info.get('to')
    data['cc'] = mail_info.get('cc')
    data['Subject'] = mail_info.get('subject')
    for i in mail_info.get('attachments', []):
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(i, "rb").read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment' ,filename=i)
        data.attach(part)
    data.attach(MIMEText(mail_info.get('body'), 'plain'))
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    try:
        s.login(sender, os.environ.get('REPORT_SENDER_PASSWORD'))  #mail password
        text = data.as_string()
        s.sendmail(sender, mail_info.get('to'), text)
        s.quit()
        log.info("Mail sent to %s !!" %(mail_info['to']))
    except Exception as exp:
        log.excption("Unable to send email to %s. Reason: %s", mail_info.get("to"), exp)


def open_tenant_database_connection(tenant_id, tenant_password):
    log = getLogger('open_tenant_database_connection')

    db_dsn = "host={host} port={port} dbname={dbname} user={user} password={password}".format(
        host=os.environ.get("DB_HOST"),
        dbname=os.environ.get("DB_NAME"),
        port=os.environ.get("DB_PORT"),
        user=tenant_id,
        password=tenant_password
    )
    if not os.environ.get("DEV"):
        db_dsn += " sslmode=require"
    log.info("Attempting to spin-up connection")
    return connect(db_dsn)


def upload_img(files,fileobj):
    path ="/home/deepak/workspace/tulitahara-py/console_api/" + files
    fileobj.save(path)

def generate_token(message):
    message = str(message)
    encoded_message = message.encode()
    f = Fernet(key)
    encrypted_message = f.encrypt(encoded_message)
    return encrypted_message

def decrypt_token(encrypted_message):
    f = Fernet(key)
    decrypted_message = f.decrypt(bytes(encrypted_message, encoding="utf-8"))
    print(decrypted_message.decode())
    return(decrypted_message.decode())


def get_tenant_details(otp):
    log = getLogger("get_tenant_details")
    try:
        redis_connection = Redis(host=constants.REDIS_HOST, port=int(constants.REDIS_PORT), db=1)
        details = redis_connection.get(otp)
        if not details:
            log.warning("Key not found: %s", otp)
            return None
        redis_connection.close()
        return json.loads(details)
    except Exception as exp:
        log.exception("Unable to connect to redis! Reason: %s", exp)
        raise exp


@cachetools.cached(ADMIN_DETAILS_TTL_CACHE)
def get_admin_details(tenant_db_connection, phone_number):
    log = getLogger("get_admin_details")
    query = "select ad.name, ch.store_name from admins ad join chillers ch on ad.chiller_name = ch.name where ad.phone_number = %s"
    params = (phone_number,)
    log.info("Obtaining details for admin with phone number: %s", phone_number)
    try:
        cursor = tenant_db_connection.cursor()
        cursor.execute(query, params)
        result_set = cursor.fetchall()[0]
        log.info("Query result: %s", result_set)
        return {
            "name": result_set[0],
            "store_name": result_set[1]
        }
    except Exception as exp:
        log.exception("Unable to fetch admin details. Reason: %s", exp)
        raise exp

@cachetools.cached(STORE_TTL_CACHE)
def list_stores(tenant_db_connection):
    query = "select name, store_name from chillers where active"
    log = getLogger("list_stores")
    try:
        cursor = tenant_db_connection.cursor()
        cursor.execute(query)
        result_set = cursor.fetchall()
        stores = {
            x[0]: x[1] for x in result_set
        }
        log.info("Stores found: %s", stores)
        return stores
    except Exception as exp:
        log.exception("Unable to list stores. Reason: %s", exp)
        raise exp


@cachetools.cached(TENANT_CREDENTIALS_TTL_CACHE)
def get_tenant_db_login_details(tenant_id):
    query = "SELECT db_user, tenant_key FROM tenant_info WHERE tenant_id = %s"
    logger = getLogger("get_tenant_db_login_details")
    logger.info("Obtaining tenant credentials for tenant id %s", tenant_id)
    credential = None
    try:
        connection = master_database_connection()
        cursor = connection.cursor()
        cursor.execute(query, (tenant_id,))
        results = cursor.fetchall()
        if not results:
            logger.warning("Credentials not found for tenant %s", tenant_id)
            return None
        credential = results[0]
    except Exception as exp:
        logger.exception("An error occured while fetching credentials: %s", exp)
        raise exp
    finally:
        cursor.close()
        connection.close()
        return credential


log = getLogger("wmp_backend_api")

def get_request_ip(request):
    if request.META.get('HTTP_X_FORWARDED_FOR') is not None:
        return request.META['HTTP_X_FORWARDED_FOR']
    elif request.META.get('REMOTE_ADDR') is not None:
        return request.META['REMOTE_ADDR']
    else:
        return "localhost"


def seconds_to_next_day():
    next_day = datetime.date.today() + datetime.timedelta(days=1)
    seconds_to_next_day = int(time.mktime(next_day.timetuple()) - time.time()) + 1
    return seconds_to_next_day


def error_response(code=status.HTTP_400_BAD_REQUEST,
                   reason=None, message=None):
    error = {"code": code}
    if reason:
        error["reason"] = reason
    if message:
        error["message"] = message

    log.error("response error: %s", error)
    return jsonify({"error": error})


def simple_response(code=status.HTTP_200_OK,
                    reason=None, message=None):
    data_json = {"code": code}
    if reason:
        data_json["reason"] = reason
    if message:
        data_json["message"] = message

    log.info("response data: %s", data_json)
    return jsonify(data_json)


def dict_decode(trans_dict: dict):
    new_dict = {}
    for key in trans_dict:
        value = trans_dict[key].decode()
        key = key.decode()
        new_dict[key] = value
    return new_dict
