import os
import json
import cachetools
from PIL import Image
import urllib3
import requests
import argparse

from utils import common
from utils import constants
from tabulate import tabulate

log = common.getLogger('load_skus')

Q_INSERT_ITEM_MASTER = """
insert into item_master(
    sku_code,
    sku_name,
    item_descr,
    item_pic,
    active,
    expiry,
    price,
    category,
    weight,
    nutrition_info,
    tenant_id
)
values(
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
) ON CONFLICT ON CONSTRAINT item_master_pkey DO 
UPDATE
set sku_name = EXCLUDED.sku_name,
item_descr = EXCLUDED.item_descr,
item_pic = EXCLUDED.item_pic,
active = EXCLUDED.active,
expiry = EXCLUDED.expiry,
price = EXCLUDED.price,
category = EXCLUDED.category,
weight = EXCLUDED.weight,
nutrition_info = EXCLUDED.nutrition_info
"""
MEDIA_SERVER_HOSTNAME = os.environ.get("MEDIA_SERVER_HOSTNAME") or "http://localhost:2560"

def download_image_if_url(path, sku_code, tenant_name):
    try:
        res = requests.get(path)
        res.raise_for_status()
        file_ext = res.headers["Content-Type"].split("/")[-1] or "jpeg"
        dest = "/tmp/%s_%s.%s" %(tenant_name, sku_code, file_ext)
        with open(dest, 'wb') as handle:
            handle.write(res.content)
        return dest
    except Exception:
        log.exception("Unable to handle request for %s" %path)
        return None
    

def upload_to_media_server(tenant_name, filename, sku_code):
    log = common.getLogger("upload_to_media_server")
    try:
        if filename.startswith('http://') or filename.startswith('https://'):
            tmp_filename = download_image_if_url(filename, sku_code, tenant_name)
            if tmp_filename:
                filename = tmp_filename
        log.info("Uploading %s to %s", filename, MEDIA_SERVER_HOSTNAME)
        url = "%s/%s/%s" %(MEDIA_SERVER_HOSTNAME, "products", tenant_name)
        try:
            response = requests.post(url, files={"image": open(filename, "rb")})
            response.raise_for_status()
            return response.json()
        except FileNotFoundError:
            log.warning("File %s not found", filename)
            return None
    except requests.HTTPError as http_error:
       log.exception("Upload failed. Reason: %s", http_error)
       return None


def add_to_item_master(tenant_name, record, database_connection=None):
    sku_code = record.get("sku_code")
    sku_name = {"en": record.get("sku_name")}
    sku_image_path = record.get("image_path")
    sku_description = {"en":record.get("item_descr")}
    sku_price = float(record.get("price"))
    sku_category = record.get("category").title()
    sku_quantity = float(record.get("quantity_gram"))
    sku_active = record.get("active", True)
    sku_expiry = record.get("expiry_interval_days") + " days"

    sku_nutrition_info = {
        'energy_kcal': float(record.get("energy_kcal")),
        'protein-gm': float(record.get("protein_gm")),
        'total-fat-gm': float(record.get("total_fat_gm"))
    }

    if not sku_image_path:
        image_path = {
            "endpoint": ""
        }
    else:
        image_path = upload_to_media_server(tenant_name, sku_image_path, sku_code)

    try:
        params = (
            sku_code,
            json.dumps(sku_name),
            json.dumps(sku_description),
            image_path.get("endpoint") if image_path else " ",
            sku_active,
            sku_expiry,
            sku_price,
            sku_category,
            sku_quantity,
            json.dumps(sku_nutrition_info),
            tenant_name
        )
        log.info("Attempting insertion of record: %s", params)
        if not database_connection:
            database_connection = common.master_database_connection()
        else:
            log.info("Using existing database connection")
        cursor = database_connection.cursor()
        cursor.execute(Q_INSERT_ITEM_MASTER, params)
        log.info("Record inserted. result: %s", sku_code)
        if not database_connection.autocommit:
            database_connection.commit()
    except Exception as exp:
        log.exception("Record insertion failed. %s", exp)
        cursor.close()
        raise exp


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tenant-id",
        required=True,
        type=str,
        help="Your tenant id"
    )
    parser.add_argument(
        "--category",
        required=True,
        type=str,
        help="The SKU category"
    )
    parser.add_argument(
        "--sku-code",
        required=True,
        type=str,
        help="The SKU Code"
    )
    parser.add_argument(
        "--sku-name",
        required=True,
        type=str,
        help="The SKU Name"
    )
    parser.add_argument(
        "--sku-description",
        required=True,
        type=str,
        help="The SKU's description"
    )
    parser.add_argument(
        "--quantity-gram",
        required=True,
        type=str,
        help="The product's quantity in grams"
    )
    parser.add_argument(
        "--price",
        required=True,
        type=float,
        help="The product's price"
    )
    parser.add_argument(
        "--image-path",
        required=False,
        type=str,
        help="The product's image file"
    )
    parser.add_argument(
        "--energy-kcal",
        required=True,
        type=str,
        help="Product's calorie count."
    )
    parser.add_argument(
        "--protein-gm",
        required=True,
        type=str,
        help="Amount of protein in the product"
    )
    parser.add_argument(
        "--total-fat-gm",
        required=True,
        type=str,
        help="Total fat in gram in the product"
    )
    parser.add_argument(
        "--expiry-interval-days",
        required=True,
        help="The number of days within which an item in this SKU will expire"
    )
    parser.add_argument(
        "--currency",
        required=False,
        type=str,
        choices=constants.CURRENCIES,
        default="INR",
        help="The product's price currency"
    )


    arguments_raw = parser.parse_args().__dict__
    print("Summary: \n%s\n" %json.dumps(arguments_raw, indent=4))
    confirmation = input("Confirm and create SKU record? [yes|no]")
    if confirmation != "yes":
        print ("Aborting operation")
        return
    add_to_item_master(arguments_raw.get("tenant_id"), arguments_raw)


if __name__ == "__main__":
    main()
