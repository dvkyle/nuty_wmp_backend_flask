import argparse

from utils import common


def add_tag(tag_details, db_cursor):
    sku_code = tag_details.get("SKUCode")
    radio_tag = tag_details.get("RadioTag")
    common.logging.info("Inserting Radio tag %s for SKU code %s", radio_tag, sku_code)
    expiry = common.get_expiry_interval(sku_code)
    query = """
    insert into post_production_master (sku_code, radio_tag, expiry)
    values (%s, %s, %s)
    """
    try:
        params = (sku_code, radio_tag, expiry)
        db_cursor.execute(query, params)
    except Exception as exp:
        common.logging.exception("Unable to add radio tag %s for sku code %s. Reason: %s", radio_tag, sku_code, exp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-file", required=True, help="A CSV file which contains details about the inventory you want to add/update for a store")
    parser.add_argument("--dry-run", required=False, help="Performs a dry run (does not make changes to the database)", action="store_true")
    arguments = parser.parse_args()

    is_dry_run = arguments.dry_run
    csv_records = common.load_records(arguments.csv_file)
    if not is_dry_run:
        # obtaining db connection to tulitahara db since it is not clear if this needs to be multi-tenant
        DB = common.database_connection("tulitahara")
        CURSOR = DB.cursor()

        for rec in csv_records:
            add_tag(rec, CURSOR)
        if not DB.autocommit:
            DB.commit()
        return
    common.logging.info("Skipping insert because dry run!")
    return


if __name__ == "__main__":
    main()
