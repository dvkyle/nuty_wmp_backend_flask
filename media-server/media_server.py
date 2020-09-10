import flask
import os
import argparse
from cachetools import LRUCache

from utils import common
from utils import constants
APP_NAME = 'media_server'
MEDIA_DIRS = {
    "root": "/media",
    "products": "/media/products/",
    "purchase_receipts": "/media/purchaseReceipts/"
}
EXEC_ENV = os.environ.get("FLASK_ENV")
MEDIA_DIR_PREFIX = "/tmp" if EXEC_ENV != "live" else ""
MEDIA_SERVER_HOSTNAME = os.environ.get("MEDIA_SERVER_HOSTNAME") or "http://localhost:2560"

app = flask.Flask(APP_NAME)
app.config["DEBUG"] = False

media_cache = LRUCache(1000)

def item_from_cache(tenant_name, item_id):
    cached_image = media_cache.get((tenant_name, item_id))
    raw_bytes = cached_image.get("content")
    content_type = cached_image.get("content_type")
    content_disposition = cached_image.get("content_disposition")
    response = flask.make_response(raw_bytes)
    response.headers["Content-Disposition"] = "inline; filename={}".format(content_disposition)
    response.headers["Content-Type"] = content_type
    return response


@app.route("/products/<tenant_name>/<product_sku_code>", methods=["GET"])
def download_product_image(tenant_name, product_sku_code):
    log = common.getLogger("get_product_image")
    if not product_sku_code in media_cache:
        log.info("Product image not found in cache")
        download_path = MEDIA_DIR_PREFIX + MEDIA_DIRS["products"] + product_sku_code
        try:
            download_path, content_type, actual_filename = common.download_from_azure_storage(tenant_name, product_sku_code, constants.AZ_IMAGES_CONTAINER, download_path)
            if not os.path.exists(download_path):
                log.error("Product image for sku code %s not downloaded", product_sku_code)
                return 404
            if os.stat(download_path).st_size <= 0:
                log.error("Image file not proper")
                return 502
            with open(download_path, "rb") as saved_file:
                media_cache[(tenant_name, product_sku_code)] = {
                    "content": saved_file.read(),
                    "content_type": content_type,
                    "content_disposition": actual_filename
                }
            os.remove(download_path)
        except Exception as exp:
            log.exception("Unable to fetch image. Reason: %s", exp)
            return 502
    return item_from_cache(tenant_name, product_sku_code)


@app.route("/<tenant_name>/receipts/<receipt_id>", methods=["GET"])
def download_receipt(tenant_name, receipt_id):
    log = common.getLogger("get_receipt")
    if not receipt_id in media_cache:
        log.info("Product image not found in cache")
        download_path = MEDIA_DIR_PREFIX + MEDIA_DIRS["purchase_receipts"] + receipt_id
        try:
            common.download_from_azure_storage(tenant_name, receipt_id, constants.AZ_RECEIPTS_CONTAINER, download_path)
            if not os.path.exists(download_path):
                log.error("Receipt %s not downloaded", receipt_id)
                return 404
            if os.stat(download_path).st_size <= 0:
                log.error("Downloaded file not proper")
                return 502
            with open(download_path, "rb") as saved_file:
                media_cache[receipt_id] = {
                    "content": saved_file.read()
                }
            os.remove(download_path)
        except Exception as exp:
            log.exception("Unable to fetch receipt. Reason: %s", exp)
            return 502
    return item_from_cache(tenant_name, receipt_id)


@app.route("/products/<tenant_name>", methods=["POST"])
def upload_product_image(tenant_name):
    log = common.getLogger("upload_product_image")
    incoming_image_request = flask.request.files["image"]
    filename = incoming_image_request.filename
    log.info("Uploading image %s", filename)
    save_file_path = MEDIA_DIR_PREFIX + MEDIA_DIRS["products"] + filename
    with open(save_file_path, "wb") as saved:
        image_bytes = incoming_image_request.stream.read()
        saved.write(image_bytes)
    try:
        common.upload_to_azure_storage(tenant_name, save_file_path, constants.AZ_IMAGES_CONTAINER, "image")
        endpoint = MEDIA_SERVER_HOSTNAME + "/products/{tenant_name}/{filename}".format(tenant_name=tenant_name, filename=filename)
        return {
            "endpoint": endpoint
        }
    except Exception as exp:
        log.exception(exp)
        return 500


def preflight_tasks(preflight_opts=None):
    log = common.getLogger("preflight_tasks")
    log.info("Performing pre-flight tasks")
    for m_dir_path in MEDIA_DIRS.values():
        dir_path = MEDIA_DIR_PREFIX + m_dir_path
        if not os.path.exists(dir_path):
            log.info("Creating directory %s", dir_path)
            os.mkdir(dir_path)


if __name__ == "__main__":
    preflight_tasks()
    app.run(host="0.0.0.0", port=2560)
