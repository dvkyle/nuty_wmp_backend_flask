import csv
import psycopg2
import os
import cachetools
import json
import requests
import argparse
import traceback
import re
from utils import common
from utils import constants
from datetime import datetime
from datetime import time
import pytz
import qrcode
from timezonefinder import TimezoneFinder
import arrow
log = common.getLogger("add_chillers")

CHILLER_NAME_TEMPLATE = "{name}-{area}-{tenant_id}"
CHILLER_RECORD_QUERY = """
insert into chillers(
    name,
    country,
    region,
    city,
    postalcode,
    latitude,
    longitude,
    address,
    registered,
    cert,
    smart,
    store_name,
    outlet_id,
    google_maps_uri,
    opening_time,
    closing_time,
    active,
    delivery_available,
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
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
);
"""
FRANCHISEE_RECORD_QUERY = """
insert into franchisee (
    phone_number,
    chiller_name,
    name,
    active,
    tenant_id
) values (
    %s,
    %s,
    %s,
    %s,
    %s
)
"""


@cachetools.cached({})
def get_timezone_finder():
    return TimezoneFinder()

def lat_long(google_map_uri):
    raw_latlong = google_map_uri.split("!3d")[-1].replace("?hl=en", "").split("!4d")
    clean_lat = ''.join(c for c in raw_latlong[0] if c.isdigit() or c == ".")
    clean_long = ''.join(c for c in raw_latlong[1] if c.isdigit() or c == ".")
    return float(clean_lat), float(clean_long)


def generate_chiller_qr_code(chiller_name):
    uri = constants.QR_CODE_API.format(
        d1=constants.QR_CODE_DIMENSIONS[0],
        d2=constants.QR_CODE_DIMENSIONS[1],
        chiller_name=chiller_name
    )
    log = common.getLogger("generate_chiller_qr_code")
    log.info("Generating QR code for chiller %s. URI: %s", chiller_name, uri)
    qr_code_response = requests.get(url=uri)
    try:
        qr_code_response.raise_for_status()
        qr_code_filename = constants.QR_CODE_DOWNLOAD_PATH.format(chiller_name=chiller_name)
        log.info("Saving QR code for %s to %s", chiller_name, qr_code_filename)
        with open(qr_code_filename, "wb") as download_handle:
            download_handle.write(qr_code_response.content)
            return download_handle.name
    except requests.exceptions.HTTPError as http_error:
        log.exception("Cannot generate QR code for %s. %s", chiller_name, http_error)
        return None


def generate_franchisee_qr(chiller_name):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=30,
        border=10
    )
    qr.add_data(chiller_name)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    qr_code_filepath = "/tmp/{}.png".format(chiller_name)
    with open(qr_code_filepath, "wb") as destination:
        image.save(destination)
    return qr_code_filepath


def create_franchisee_record(tenant_id, chiller_name, phone_number, retailer_name, master_database_connection):
    log = common.getLogger("create_franchisee_record")
    log.info("Creating franchisee record. Chiller name: %s", chiller_name)
    try:
        cursor = master_database_connection.cursor()
        generate_franchisee_qr(chiller_name)
        qr_code_file = generate_franchisee_qr(chiller_name)
        qr_code_uri = common.upload_to_azure_storage(tenant_id, qr_code_file, "qr-codes", "images")
        log.info("QR Code uploaded to %s", qr_code_uri)
        params = (
            phone_number,
            chiller_name,
            retailer_name,
            'true',
            tenant_id
        )
        cursor.execute(FRANCHISEE_RECORD_QUERY, params)
        if not master_database_connection.autocommit:
            master_database_connection.commit()
    except Exception as exp:
        log.exception("Failed to create franchisee record. %s", exp)    


def get_timezone(chiller_co_ordinates):
    return get_timezone_finder().timezone_at(lat=chiller_co_ordinates[0], lng=chiller_co_ordinates[1])


def get_tz_aware_time(t_string, tz):
    z = arrow.Arrow.strptime(t_string, "%H:%M:%S")
    z = z.to(tz)
    return z.format('HH:MM:SSZZ')


def prepare_chiller_name(outlet_id, name, area, tenant_id):
    name_cated = "%s.%s-%s-%s" %(tenant_id, outlet_id, name, area)
    expression = re.compile(r'[\'\s\_\\\/\,]')
    return expression.sub('', name_cated)


def create_chiller_record(tenant_id, record):
    master_database_connection = common.master_database_connection(tenant_id, "add_chillers.py")
    cursor = master_database_connection.cursor()
    gmap_uri = record.get("google_maps_url")
    chiller_co_ordinates = (lat_long(gmap_uri))
    chiller_timezone = get_timezone(chiller_co_ordinates)
    log.info("Chiller timezone: %s", chiller_timezone)
    timezone = record.get("timezone", 'Asia/Kolkata')
    region = record.get("region")
    city = record.get("city")
    pincode = record.get("postal_code")
    area = record.get("area")
    name = record.get("outlet_name").title()
    business_name = record.get("business_name")
    street_address = record.get("street_address")
    country = record.get("country")
    delivery_available = record.get("delivery_available", False)
    complete_address = "{oname}, {street_address}, {city}, {region}, {pincode}, {country}".format(
        oname=name,
        street_address=street_address,
        city=city,
        region=region,
        pincode=pincode,
        country=country
    )
    store_opening_time = get_tz_aware_time(record.get("starting_time"), timezone)
    store_closing_time = get_tz_aware_time(record.get("closing_time"), timezone)
    outlet_id = record.get("outlet_id")
    chiller_name = prepare_chiller_name(record.get("outlet_id"), name, area, tenant_id) #CHILLER_NAME_TEMPLATE.format(name=name.strip().lower().replace(' ', ''), area=area.strip().lower().replace(' ',''), tenant_id=tenant_id)
    phone_number = record.get("contact")
    chiller_record = (
        chiller_name,
        country,
        region,
        city,
        pincode,
        chiller_co_ordinates[0],
        chiller_co_ordinates[1],
        complete_address,
        'true',
        ' ',
        'false',
        business_name,
        outlet_id,
        gmap_uri,
        store_opening_time,
        store_closing_time,
        'true',
        delivery_available,
        tenant_id
    )
    log.info("Will save chiller record: %s. Delivery available for chiller? %s", chiller_record[0], delivery_available)
    try:
        cursor.execute(CHILLER_RECORD_QUERY, chiller_record)
        create_franchisee_record(record.get("tenant_id"), chiller_name, phone_number, name, master_database_connection)
        if not master_database_connection.autocommit:
            master_database_connection.commit()
    except Exception as exp:
        traceback.print_exc()
        log.exception("Chiller record insertion failed. Reason: %s", exp)
        master_database_connection.rollback()


def main():
    parser = argparse.ArgumentParser(prog="add_chillers")
    parser.add_argument("--tenant-id", required=True, help="Your tenant ID", type=str)
    parser.add_argument("-i", "--outlet-id", required=True, help="Chiller's outlet ID", type=str)
    parser.add_argument("-b", "--business-name", required=True, help="The name of the business", type=str)
    parser.add_argument("-o", "--outlet-name", required=True, help="The name of the outlet", type=str)
    parser.add_argument("-n", "--contact", required=True, help="Outlet contact", type=str)
    parser.add_argument("-a", "--area", required=True, help="The area where this outlet is localted", type=str)
    parser.add_argument("-s", "--street-address", required=True, help="The outlet's street address", type=str),
    parser.add_argument("-c", "--city", required=True, help="The city where this outlet is located", type=str)
    parser.add_argument("-p", "--postal-code", required=True, help="The city's postal code", type=str),
    parser.add_argument("-r", "--region", required=True, help="The state where the outlet is located", type=str)
    parser.add_argument("-y", "--country", required=True, help="Country", type=str)
    parser.add_argument("-g", "--google-maps-url", required=True, help="The outlet's URL from Google Maps", type=str)
    parser.add_argument("-d", "--delivery-available", required=False, default=False, action="store_true")

    parser.add_argument("--starting-time", required=False, default="11:00", help="The outlet's opening time. Specify as HH:MM")
    parser.add_argument("--closing-time", required=False, default="22:00", help="The outlet's closing time. Specify as HH:MM")
    parser.add_argument("--timezone", required=False, default="Asia/Kolkata", help="The outlet's timezone locale.")

    arguments = parser.parse_args()
    arguments_raw = arguments.__dict__
    chiller_record = {
        key: value for key, value in arguments_raw.items()
    }

    print("Summary: \n")
    for key, value in chiller_record.items():
        print("%s\t%s" %(key, value))

    confirmation = input("Confirm and create? [yes|no]")

    if confirmation not in set(["yes", "no"]):
        print ("Please respond with either 'yes' or 'no'")
        return

    if confirmation == "yes":
        create_chiller_record(chiller_record.get("tenant_id"), chiller_record)
    else:
        print ("Aborting...!")

    return


if __name__ == "__main__":
    main()
