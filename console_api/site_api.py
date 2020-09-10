from flask import Flask, request, jsonify
from flask_api import status
from flask_cors import CORS, cross_origin
import simplejson as json
from utils import common
import requests
import os
from management import load_skus
from management import load_inventory
import cachetools
from psycopg2 import OperationalError
from utils import constants

MEDIA_SERVER_HOSTNAME = os.environ.get("MEDIA_SERVER_HOSTNAME") or "http://localhost:2560"
log = common.getLogger('site_api')
app = Flask(__name__)
cors = CORS(app)
APPLICATION_NAME="mmc_api"


def get_tenant_db_conn(tenant_id):
    log.info("Opening db connection for tenant %s", tenant_id)
    connection = None
    try:
        details = common.get_tenant_db_login_details(tenant_id)
        if not details:
            return None
        connection = common.open_tenant_database_connection(details[0], details[1])
    except Exception as exp:
        log.exception("An error occured while trying to open a connection to the database in context of tenant %s: %s", tenant_id, exp)
        raise exp
    finally:
        return connection


@app.route('/login', methods = ['POST'])
def login():
    login_data = request.json
    otp = login_data.get("otp")
    if not otp:
        return jsonify({
            "status": False,
            "reason": "OTP not provided for logging in."
        })
    log.info("Login request received. Feilds: %s", login_data.keys())

    try:
        tenant_details = common.get_tenant_details(otp)
        tenant_id = tenant_details.get("tenant_id", "blah")
        phone_number = tenant_details.get("phone_number", "bleh")

        token_plain = tenant_id + "|" + phone_number
        token_scrambled = common.generate_token(token_plain)

        tenant_db_connection = get_tenant_db_conn(tenant_id)
        admin_details = common.get_admin_details(tenant_db_connection=tenant_db_connection, phone_number=phone_number)
        stores_under_tenant = common.list_stores(tenant_db_connection=tenant_db_connection)
        response = {
            "status": True,
            "Token": token_scrambled.decode("utf-8"),
            "phone_number": phone_number,
            "admin_name": admin_details.get("name"),
            "store_name": admin_details.get("store_name"),
            "meta": {
                "stores_under_tenant": stores_under_tenant
            }
        }
        log.info("Response: %s", response)
        return jsonify(response)

    except Exception as exp:
        return jsonify({
            "status": False,
            "reason": str(exp)
        })
 
@app.route('/upload_skus', methods = ['POST'])
def upload_skus():
    skus = [ x for x in request.json if x.get('checked') ]
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not(tenant_id and skus):
        return {'status' : False}
    db_connection = get_tenant_db_conn(tenant_id)
    try:
        for record in skus:
            load_skus.add_to_item_master(tenant_id, record, db_connection)
    except Exception as exp:
        log.exception("An error occured while trying to save records. Error: %s", exp)
        db_connection.close()
        return {
            "status": False,
            "reason": exp
        }
    return {'status':True}


@app.route('/add_skus', methods =['POST'])# form section
def add_skus():
    token = common.decrypt_token(request.headers['Token'])
    if not token:
        return {'status' : False}
    tenant_id = token.split('|')[0]
    skus = request.form
    uploaded_file = request.files.get('image_path')
    save_file_as = "/tmp/{tenant_id}_{filename}".format(tenant_id=tenant_id, filename=uploaded_file.filename)
    log.info("Got a file to uplaod. Name: %s, will save to filesystem as: %s", uploaded_file.filename, save_file_as)
    with open(save_file_as, 'wb') as handle:
        handle.write(uploaded_file.stream.read())
    log.info("File saved to %s", save_file_as)
    record = { x[0]: x[1] for x in skus.items() }
    log.info("Adding SKU with SKU code %s and name: %s" %(record['sku_code'],record['sku_name']))
    record["image_path"] = save_file_as
    try:
        db_connection = get_tenant_db_conn(tenant_id)
        load_skus.add_to_item_master(tenant_id, record, database_connection=db_connection)
        return jsonify({'status':True})
    except Exception as exp:
        log.exception("An error occured while trying to insert an SKU. Details: %s", exp)
        db_connection.close()
        return jsonify({"status": False, "reason": str(exp)})


@app.route('/update_skus',methods = ['POST'])
def update_skus():
    query = """update post_production_master set expired = true where sku_code = '%s' """
    update_request = request.json
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not tenant_id:
        return {'status' : False}
    log.info("Received update request for SKU: %s, Tenant ID: %s", update_request, tenant_id)
    try:
        db_connection = get_tenant_db_conn(tenant_id)
        load_skus.add_to_item_master(tenant_id, update_request, database_connection=db_connection)
        cursor = db_connection.cursor()
        set_expire_true_query = query %(update_request['sku_code'])
        log.info(set_expire_true_query)
        if not update_request['active']:
            cursor.execute(set_expire_true_query)
        else:
            cursor.execute("update post_production_master set expired = false where sku_code = %s ", (update_request['sku_code'],))
        db_connection.commit()
        return {'status': True}
    except Exception as e:
        log.exception("An exception occured while updating an SKU. Error: %s", e)
        db_connection.close()
        return {'status' : False,'reason' : str(e)}
          

@app.route('/admin_add', methods = ['POST'])
def admin_add():
    query = """insert into admins (name, chiller_name, tenant_id, phone_number) values ('%s' , '%s', '%s', '%s') """
    add_admin = request.json
    log.info("Add admin data received: %s", add_admin)
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not (tenant_id and add_admin):
        return {'status' : False}
    try:
        db_connection = get_tenant_db_conn(tenant_id)
        query_to_execute = query %(add_admin['name'], add_admin['chiller_name'],tenant_id ,add_admin['phone_number'],)
        cursor = db_connection.cursor()
        log.info("Query to execute: %s", query_to_execute)
        cursor.execute(query_to_execute)
        db_connection.commit()
        return {'status': True}
    except Exception as e:
        log.exception("An error occured while trying to add admin. Details: %s", e)
        db_connection.close()
        return {'status': False, 'reason': str(e)}        
        

@app.route('/update_admins', methods = ['POST'])
def update_admins():
    query = """update admins set chiller_name = '%s' , active= %s where phone_number = '%s'
     and chiller_name = '%s'"""
    update_req = request.json
    log.info(update_req)
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not tenant_id :
        return {'status' : False}
    try:
        db_connection = get_tenant_db_conn(tenant_id)
        cursor = db_connection.cursor()
        query_to_execute = query %(update_req['new_chiller_name'], update_req['status'], update_req['mobile_no'], update_req['old_chiller_name'],)
        log.info(query_to_execute)
        cursor.execute(query_to_execute)
        db_connection.commit()
        return {'status': True }
    except Exception as e:
        log.exception("An error occured while trying to update admins. Details: %s", e)
        db_connection.close()
        return{'status': False , 'reason': str(e)}
        

@app.route('/show_admins')
def show_admins():
    result = []
    query = """ select ad.name, ad.chiller_name, ch.store_name,
     ad.phone_number,ad.active from admins ad join chillers ch
     on ad.chiller_name = ch.name where ad.tenant_id = %s """
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not tenant_id :
        return {'status' : False}
    db_connection = get_tenant_db_conn(tenant_id)
    cursor = db_connection.cursor()
    cursor.execute(query,(tenant_id,))
    admins = cursor.fetchall()
    for i in admins:
        row={
            'name': i[0],
            'chiller_name' : i[1],
            'store_name' : i[2],
            'phone_number' : i[3],
            'status' : i[4]
        }
        result.append(row)
    return {'status': True, 'admins': json.dumps(result)}


@app.route('/show_skus')
def show_skus():
    skus_json = []

    # skipping tenant_id in this query because a db connection in context of that tenant's user will be opened anyway
    query = """
    SELECT sku_code, sku_name, item_descr, active, expiry, price, item_pic, nutrition_info, weight, category, COUNT(*) OVER() AS total_records
    FROM item_master
    ORDER BY sku_code
    LIMIT %s
    OFFSET %s
    """
    id = common.decrypt_token(request.headers['Token'])
    if not id:
        return {'status' : False}
    per_page = int(request.args.get("per_page", constants.API_RESULTS_PER_PAGE))
    offset = int(request.args.get("page", 1))
    offset = offset - 1
    log.info(id)
    tenant_id = id.split('|')[0]
    # connecting using tenant credentials
    cursor = get_tenant_db_conn(tenant_id).cursor()
    params = None
    if offset == 0:
        params = (per_page, offset)
    else:
        params = (per_page, offset * per_page)
    query_to_execute = query %params
    log.info("Query to execute: %s", query_to_execute)
    cursor.execute(query_to_execute)
    skus_data = cursor.fetchall()
    records_found = set()
    if skus_data:
        for skus in skus_data:
            records_found.add(int(skus[-1]))
            row = {
                'sku_code': skus[0],
                'sku_name' :  skus[1],
                'item_descr' : skus[2],
                'active' : skus[3],
                'expiry' : str(skus[4]),
                'price' : str(skus[5]),
                'item_pic': skus[6],
                'nutritional_info': skus[7],
                'weight' : skus[8],
                'category' : skus[9]
            }
            log.info(row)
            skus_json.append(row)
    records_found = list(records_found)[0]
    log.info("Total records found: %s", records_found)
    response = app.make_response({
        "skus": skus_json,
        'records_found' : records_found
    })
    response.headers['records_found'] = records_found
    return response


@app.route('/transaction')
def transaction():
    query = """
    SELECT order_id, amount, platform, chiller_name, trantz::date, customer_contact, status, amount_paid, invoice_data, COUNT(*) OVER() as total_records
    FROM chiller_purchase_transactions
    ORDER BY trantz desc
    LIMIT %s
    OFFSET %s
    """
    output = []
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not tenant_id:
        return {'status' : False}
    per_page = int(request.args.get("per_page", constants.API_RESULTS_PER_PAGE))
    offset = int(request.args.get("page", 1))
    offset = offset - 1

    cursor = get_tenant_db_conn(tenant_id).cursor()
    params = None
    if offset == 0:
        params = (per_page, offset)
    else:
        params = (per_page, offset * per_page)
    query_to_execute = query %params
    log.info("Query to execute: %s", query_to_execute)
    cursor.execute(query, params)
    records_found = set()
    if cursor:
        order_data = cursor.fetchall()
        for orders  in order_data:
            records_found.add(orders[-1])
            invoice_data = orders[8]
            parsed_invoice_data = None
            try:
                parsed_invoice_data = json.loads(invoice_data)
            except Exception as exp:
                log.warn("Unable to load invoice data for order id %s. Reason: %s", orders[0], exp)
                parsed_invoice_data = json.dumps("not-found")
            row = {
                'order_id' : orders[0],
                'amount' : json.dumps(orders[1], use_decimal=True),
                'platform' : orders[2],
                'chiller_name' : orders[3],
                'booking_date' :str(orders[4]),
                'customer_contact': str(orders[5]),
                'order_status': str(orders[6]),
                'amount_received' :  json.dumps(orders[7], use_decimal=True),
                'invoice_data': parsed_invoice_data
            }
            output.append(row)
    records_found = list(records_found)[0]
    response = app.make_response({
        "transactions": output,
        "records_found" : records_found
    })
    response.headers['records_found'] = records_found
    return response


@app.route('/add_inventory', methods = ['POST'])
def add_inventory():
    inventory = request.json
    # log.info(inventory)
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not(tenant_id and inventory):
        return {'status' : False}
    log.info("Inventory update request for tenant %s ", tenant_id)
    try:
        db_connection = get_tenant_db_conn(tenant_id)
        existing_skus = load_inventory.get_skus_from_db(db_connection, tenant_id)
        inventory_items_to_upload = [ x for x in inventory if x.get("checked") ]
        for record in inventory_items_to_upload:
            load_inventory.update_inventory(record, existing_skus=existing_skus, database_connection=db_connection, tenant_id=tenant_id)
    except Exception as exp:
        log.exception("An error occured while updating inventory. Details: %s", exp)
        db_connection.close()
        return {
            "status": False,
            "reason": exp
        }
    return {'status':True}


@app.route('/get_single_sku/<skucode>')
def get_single_sku(skucode):
    single_sku = []
    query = """ select sku_code, sku_name, item_descr,  active, expiry, price, 
    item_pic from item_master where tenant_id = %s and sku_code = %s """
    log.info(skucode)
    tenant_id = common.decrypt_token(request.headers['Token']).split('|')[0]
    if not tenant_id:
        return {'status' : False}
    connection = get_tenant_db_conn(tenant_id)
    cursor = connection.cursor()

    cursor.execute(query,(tenant_id,skucode))
    sku = cursor.fetchall()
    if sku:
        for s_value in sku:
            row = {
                'sku_code': s_value[0] ,
                'sku_name' : s_value[1] , 
                'item_descr' : s_value[2],
                'active' : s_value[3],
                'expiry' : str(s_value[4]) ,
                'price' : str(s_value[5]),
                'item_pic': s_value[6]
            }
            single_sku.append(row)
    log.info(single_sku)
    return json.dumps(single_sku)



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=2900)

