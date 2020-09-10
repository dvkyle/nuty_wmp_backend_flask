import logging
import os
import cachetools
import argparse
import json

from utils import common

Q_ADD_INVENTORY = """
with transaction as 
(insert into chiller_quantity (name, sku_code, quantity, tenant_id)
        values (%(name)s, %(sku_code)s, %(qty)s, %(tenant_id)s)
        on conflict(name, sku_code) do update set quantity=excluded.quantity+chiller_quantity.quantity
        returning name, sku_code, %(qty)s as update_quantity, quantity-%(qty)s as previous_quantity, quantity as revised_quantity, tenant_id)
        insert into inventory_updates (chiller_name, sku_code, update_quantity, previous_quantity, revised_quantity, tenant_id)
        select name, sku_code, update_quantity, previous_quantity, revised_quantity, tenant_id from transaction
"""

Q_UPDATE_INVENTORY = """
update chiller_quantity
set quantity = %s
where name = %s and sku_code = %s
"""

Q_GET_CHILLER_NAME = """
select name from chillers where outlet_id = '%s' and tenant_id = '%s'
"""

Q_EXISTING_QTY = """
select coalesce(max(quantity), -1) as quantity from chiller_quantity where sku_code = %s and name = %s 
"""

@cachetools.cached({})
def get_skus_from_db(database_connection, tenant_id):
    q_get_skus = "select sku_code, UPPER(sku_name) from item_master where tenant_id = '%s';" %(tenant_id)
    cursor = database_connection.cursor()
    cursor.execute(q_get_skus)
    result_set = cursor.fetchall()
    print ("Skus from db for tenant %s loaded. Length: %s" %(tenant_id, len(result_set)))
    return {
        x[0]: x[1] for x in result_set
    }

@cachetools.cached({})
def get_chiller_name(outlet_id, tenant_id, database_connection):
    cursor = database_connection.cursor()
    query = Q_GET_CHILLER_NAME %(outlet_id, tenant_id)
    cursor.execute(query)
    result_set = cursor.fetchone()
    logging.info("Outlet ID: %s, name: %s" %(outlet_id, result_set))
    return result_set


def get_existing_quantity(chiller_name, sku_code, database_connection):
    cursor = database_connection.cursor()
    cursor.execute(Q_EXISTING_QTY, (sku_code, chiller_name))
    return cursor.fetchone()[0] or 0


def update_inventory(inv_item, existing_skus, database_connection, tenant_id, is_dry_run=False):
    if not existing_skus:
        # logging.info("Existing SKUs not obtained for tenant %s. Bringing them now", tenant_id)
        existing_skus = get_skus_from_db(database_connection, tenant_id)
    sku_code = inv_item.get("sku_code")
    if sku_code not in existing_skus:
        logging.warning("Sku code %s not found in existing set of SKUs", sku_code)
        return
    cursor = database_connection.cursor()
    outlet_id = inv_item.get('outlet_id')
    chiller_name = get_chiller_name(outlet_id, tenant_id, database_connection)
    if not chiller_name:
        logging.warning("Skipping inventory update for outlet id %s", outlet_id)
        return
    chiller_name = chiller_name[0]
    logging.info("Updating inventory for outlet id %s, chiller %s", outlet_id, chiller_name)
    quantity = int(inv_item.get("quantity"))
    if quantity == 0:
        logging.warn("Quantity detected 0 for item %s", inv_item)
        return
    if not is_dry_run:
        logging.info("Adding %s to %s's inventory.", inv_item, chiller_name)
        params = {
            'name': chiller_name,
            'sku_code': inv_item.get("sku_code"),
            'qty': quantity,
            'tenant_id': tenant_id
        }
        try:
            cursor.execute(Q_ADD_INVENTORY, params)
        except Exception as exp:
            logging.exception("An exception occured while inserting this record: %s. Reason: %s", exp)
            raise exp
    else:
        logging.info("Not executing update because of dry-run")
        return

    if not database_connection.autocommit:
        if not is_dry_run:
            database_connection.commit()
        else:
            logging.info("Not commiting changes because of dry-run")


def obtain_tenant_db_credentials(tenant_id, database_connection):
    query = """
    select db_user, tenant_key from tenant_info where tenant_id = %s
    """
    cursor = database_connection.cursor()
    cursor.execute(query, (tenant_id,))
    results = cursor.fetchall()[0]
    return {
        "username": results[0],
        "passwd": results[1]
    }



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True, help="Your tenant id")
    parser.add_argument("--csv-file", required=True, help="A CSV file which contains details about the inventory you want to add/update for a store")
    parser.add_argument("--dry-run", required=False, help="Performs a dry run (does not make changes to the database)", action="store_true")
    arguments = parser.parse_args()

    is_dry_run = arguments.dry_run

    print ("Summary: \n%s\n\nConfirm and update? [yes|no]" %json.dumps(arguments.__dict__, indent=4))
    confirmation = input()
    if confirmation != "yes":
        print("Aborting")
        return

    tenant_id = arguments.tenant_id

    database_connection = common.master_database_connection("load_inventory.py")
    tenant_credentials = obtain_tenant_db_credentials(tenant_id, database_connection)
    database_connection.close()

    database_connection = common.open_tenant_database_connection(tenant_credentials["username"], tenant_credentials["passwd"]) 

    existing_skus = { sku_map[0]: sku_map[1] for sku_map in get_skus_from_db(database_connection, tenant_id) }
    records = common.load_records(arguments.csv_file)
    required_skus = set(existing_skus.keys()).intersection(set([x.get("sku_code") for x in records]))
    for inv_record in records:
        update_inventory(inv_record, required_skus, database_connection, tenant_id, is_dry_run=is_dry_run)


if __name__ == "__main__":
    main()
