import argparse
import smtplib
import json
from datetime import datetime, timedelta
from os import environ, makedirs, path, chdir
from collections import defaultdict
from zipfile import ZipFile
from tabulate import tabulate
from utils import common, constants
 
 
REPORT_TEMPLATE_ALL_LOCATIONS = """
REPORT TYPE: {rtype}

NO. OF ORDERS MADE:     {n_orders}
TOTAL ORDER VALUE:      {order_value}
NO. UNIQUE CUSTOMERS:   {n_unique_customers}

ORDERS PRODUCT WISE
-------------------
{orders_product_wise}
"""

REPORT_TEMPLATE_LOCATION_WISE_SKU_ORDERS = """
REPORT TYPE: {rtype}

STORE NAME: {store_name}

ORDERS PRODUCT WISE
-------------------
{orders_product_wise}
"""

EMAIL_BDOY = """
Please find a zip file attached which contains reports for {date}. The file is called {fname}. There are {k} files.
They are:
{file_list}
"""


class Reporter(object):
    def __init__(self, tenant_id, platform="whatsapp"):
        self.logger = common.getLogger("Reporter")
        db = common.database_connection("reports.py", autocommit=True)
        db_credential_query = "select db_user, tenant_key from tenant_info where tenant_id = '%s'" %(tenant_id)
        cursor = db.cursor()
        cursor.execute(db_credential_query)
        credentials = cursor.fetchall()[0]
        self.logger.info("Credentials: %s", credentials)

        db = common.open_tenant_database_connection(credentials[0], credentials[1])

        self.tenant_id = tenant_id

        self.modes = ["all_time", "yesterday"]
        self.cursor = db.cursor()
        self.platform = platform

        self.sku_map = self._initialize_sku_map()
        self.outlet_map = self._initialize_outlet_map()
        self.current_stock_position = self._initialize_stock_positions()
        self.transactions_per_outlet_all_time = self._initialize_transactions_per_outlet(mode="all_time")
        self.transactions_per_outlet_yesterday = self._initialize_transactions_per_outlet(mode="yesterday")
        self.skus_sold_yesterday = self._per_sku_breakdown(mode="yesterday")
        self.skus_sold_all_time = self._per_sku_breakdown(mode="all_time")
        self.logger.info("Reporter initialized")

    def _initialize_sku_map(self):
        query = """
        select sku_code, sku_name
        from item_master
        where active;
        """
        self.cursor.execute(query)
        results = self.cursor.fetchall()
        results = {
            sku[0]: sku[1] for sku in results
        }
        self.logger.info("SKU map initialized")
        return results


    def _initialize_outlet_map(self):
        query = """
        select name, store_name, city
        from chillers where active;
        """
        self.cursor.execute(query)
        results = self.cursor.fetchall()
        outlets = {}
        for record in results:
            city = record[2]
            if city not in outlets:
                outlets[city] = defaultdict()
            outlets[city][record[0]] = record[1]
        self.logger.info("Initialized outlets map")
        return outlets


    def _initialize_stock_positions(self):
        query = """
        select sku_code, quantity
        from chiller_quantity
        where name = %s
        """
        stocks_now = {}
        for city, nuty_stores in self.outlet_map.items():
            if city not in stocks_now:
                stocks_now[city] = defaultdict()
            for store in nuty_stores:
                # store_name = store.get("name")
                params = (store, )
                self.cursor.execute(query, params)
                stock_position = self.cursor.fetchall()
                stock_position = {
                    stk_pos[0]: stk_pos[1] for stk_pos in stock_position
                }
                stocks_now[city][store] = stock_position
        self.logger.info("Stock positions initialized")
        return stocks_now


    def _initialize_transactions_per_outlet(self, mode):
        query = """
        select CAST(amount as FLOAT), fulfilled_items
        from chiller_purchase_transactions
        where
        platform = %s and
        chiller_name = %s
        """
        params = [self.platform]
        transactions_per_outlet = {}
        if mode == "yesterday":
            query = query + """
            and trantz::date = now()::date - '1 day'::interval;
            """
        for city, nuty_stores in self.outlet_map.items():
            if city not in transactions_per_outlet:
                transactions_per_outlet[city] = defaultdict()
            for outlet in nuty_stores:
                if outlet not in transactions_per_outlet[city]:
                     transactions_per_outlet[city][outlet] = {
                         "total_sales_done": 0.0,
                         "txn_items": list()
                     }
                params = (self.platform, outlet)
                self.cursor.execute(query, params)
                results = self.cursor.fetchall()
                if not results:
                    transactions_per_outlet[city][outlet]["txn_items"].append({
                        "amount": 0,
                        "fulfilled_items": [
                            {
                                "sku_code": x,
                                "purchased": 0,
                                "fulfilled": 0
                            } for x in self.current_stock_position[city][outlet]
                        ]
                    })
                else:
                    for txn in results:
                        transactions_per_outlet[city][outlet]["txn_items"].append({
                                "amount": txn[0],
                                "fulfilled_items": txn[1]
                            }
                        )
                amounts_per_txn = [x.get("amount") for x in transactions_per_outlet[city][outlet]["txn_items"]]
                total_sales_done = sum(amounts_per_txn)
                transactions_per_outlet[city][outlet]["total_sales_done"] = total_sales_done
        self.logger.info("Initialized transactions per outlet for mode = '%s'", mode)
        if not transactions_per_outlet:
            self.logger.warn("No transactions found for tenant %s", self.tenant_id)
            return None
        return transactions_per_outlet


    def _per_sku_breakdown(self, mode):
        required_dataset = None
        if mode == "yesterday":
            required_dataset = self.transactions_per_outlet_yesterday
        elif mode == "all_time":
            required_dataset = self.transactions_per_outlet_all_time
        if not required_dataset:
            self.logger.warning("Cannot get required dataset for mode = %s", mode)
            return

        breakdown = {}
        for city, nuty_store in required_dataset.items():
            if city not in breakdown:
                breakdown[city] = defaultdict()
            for store in nuty_store:
                if store not in breakdown[city]:
                    breakdown[city][store] = dict()
                breakdown[city][store]["items_in_store"] = { sku_code: { "purchased": 0, "fulfilled": 0, "name": self.sku_map.get(sku_code) } for sku_code in self.current_stock_position[city][store] }
                breakdown[city][store]["total_sales_done"] = required_dataset[city][store].get("total_sales_done")

                for txn in required_dataset[city][store]["txn_items"]:
                    fulfilled_items = txn.get("fulfilled_items")
                    if not fulfilled_items:
                        continue
                    items_sold = [(x.get("sku_code"), x.get("quantity") or 0, x.get("fulfilled") or 0) for x in fulfilled_items]
                    for i_sold in items_sold:
                        sku_code = i_sold[0]
                        if sku_code not in breakdown[city][store]["items_in_store"]:
                            breakdown[city][store]["items_in_store"][sku_code] = {
                                "purchased": 0,
                                "fulfilled": 0,
                                "name": self.sku_map.get(sku_code)
                            }
                        breakdown[city][store]["items_in_store"][sku_code]["purchased"] += i_sold[1] or 0
                        breakdown[city][store]["items_in_store"][sku_code]["fulfilled"] += i_sold[2] or 0

        self.logger.info("Broke down sales per sku")
        return breakdown


    def count_orders(self):
        results = []
        queries = [
            """
            select count(*) from chiller_purchase_transactions
            where trantz::date = now()::date - '1 day'::interval;
            """,
            """
            select count(*) from chiller_purchase_transactions;
            """
        ]
        for qry in queries:
            self.cursor.execute(qry)
            results.append(self.cursor.fetchone()[-1])
        return {
            "yesterday": results[0],
            "all_time": results[1]
        }


    def order_value(self):
        results = []
        queries = [
            """
            select sum(amount) from chiller_purchase_transactions
            where trantz::date = now()::date - '1 day'::interval;
            """,
            """
            select sum(amount) from chiller_purchase_transactions;
            """
        ]
        for qry in queries:
            self.cursor.execute(qry)
            results.append(self.cursor.fetchone()[-1])
        return {
            "yesterday": results[0],
            "all_time": results[1]
        }


    def unique_customers(self):
        results = []
        queries = [
            """
            select count(distinct(phone_number)) from customers
            where create_time::date = now()::date - '1 day'::interval;
            """,
            """
            select count(distinct(phone_number)) from customers;
            """
        ]
        for qry in queries:
            self.cursor.execute(qry)
            results.append(self.cursor.fetchone()[-1])
        return {
            "yesterday": results[0],
            "all_time": results[1]
        }


    def orders_per_sku(self):
        q_skus = """
        select sku_code from item_master
        where active
        """
        self.cursor.execute(q_skus)
        sku_codes = [ x[0] for x in self.cursor.fetchall() ]
        results = []
        breakdowns = {
            "yesterday": defaultdict(),
            "all_time": defaultdict()
        }
        for sku in sku_codes:
            breakdowns["yesterday"][sku] = {
                "fulfilled": 0,
                "name": self.sku_map.get(sku)
            }
            breakdowns["all_time"][sku] = {
                "fulfilled": 0,
                "name": self.sku_map.get(sku)
            }

        queries = [
            """
            select fulfilled_items
            from chiller_purchase_transactions
            where
                trantz::date = now()::date - '1 day'::interval
                and
                fulfilled_items is not null;
            """,
            """
            select fulfilled_items
            from chiller_purchase_transactions
            where fulfilled_items is not null;
            """
        ]
        for qry in queries:
            self.cursor.execute(qry)
            items_fulfilled = [x[0] for x in self.cursor.fetchall()]
            rset = []
            for i_fulfilled in items_fulfilled:
                for item in i_fulfilled:
                    sku = item.get("sku_code")
                    rset.append((sku, self.sku_map.get(sku), item.get("fulfilled")))
            results.append(rset)

        for item in results[0]:
            breakdowns["yesterday"][item[0]]["fulfilled"] += item[2] if item[2] else 0
        for item in results[1]:
            if not item[0]:
                continue
            breakdowns["all_time"][item[0]]["fulfilled"] += item[2] if item[2] else 0

        return breakdowns


    def get_mail_details(self):
        query = "select name, email from tenant_info where tenant_id = '%s'" %(self.tenant_id)
        self.cursor.execute(query)
        details = self.cursor.fetchall()[0]
        return {
            "name": details[0],
            "email": details[1]
        }


def enumerate_tenants():
    t_id = []
    db = common.database_connection("reports.py", autocommit=True)
    cursor = db.cursor()
    qry = 'select tenant_id, email from tenant_info'
    cursor.execute(qry)
    tenant_id = cursor.fetchall()
    if tenant_id:
        for tenant in tenant_id:
            t_id.append({tenant[0]:tenant[1]})
        return t_id


def _tabulate_info(skus_sold):
    table_headers = ["sku code", "sku name", "fulfilled"]
    sold = [ [x, y["name"], y["fulfilled"]] for x, y in skus_sold.items() ]
    sorted(sold, reverse=True, key=lambda record: record[2])
    return tabulate(sold, headers=table_headers)


def create_dir(dir_name):
    logger = common.getLogger("create_dir")
    try:
        makedirs(dir_name, exist_ok=True)
        logger.info("Directory %s created", dir_name)
        return dir_name
    except FileExistsError as exp:
        logger.warning("Directory %s creation failed. Reason: %s", dir_name, exp)
        return dir_name


def list_tenants():
    db = common.database_connection("tulitahara")
    cursor = db.cursor()
    query = "select tenant_id from tenant_info where tenant_id not like 'not-set' and active"
    cursor.execute(query)
    tenants = [ x[0] for x in cursor.fetchall() ]
    logger = common.getLogger("reports.py/list_tenants")
    logger.info("Tenants found: %s", tenants)
    return tenants


def execute_report(tenant_id, yesterday, today_str, reporting_ctx):
    logger = common.getLogger("reports.py/{}".format(tenant_id))
    report_root = "/tmp/reports/{}".format(tenant_id)
    if not path.exists(report_root):
        makedirs(report_root, exist_ok=True)

    reports_base = "{root}/{execution_date}".format(root=report_root, execution_date=today_str) 
    directories = [
        reports_base,
        reports_base + "/{city}",
    ]

    reporter = Reporter(tenant_id=tenant_id)
    if not create_dir(directories[0]):
        return
    for city in reporter.outlet_map.keys():
        dir_name = directories[1].format(city=city)
        if not create_dir(dir_name):
            return

    summary = {
        "orders_per_sku": reporter.orders_per_sku(),
        "total_orders_made": reporter.count_orders(),
        "order_value": reporter.order_value(),
        "unique_customers": reporter.unique_customers()
    }

    files_written = []

    # all locations, all time
    report = REPORT_TEMPLATE_ALL_LOCATIONS.format(
        rtype="Consolidated till {}".format(yesterday),
        n_orders=summary["total_orders_made"]["all_time"],
        order_value=summary["order_value"]["all_time"],
        n_unique_customers=summary["unique_customers"]["all_time"],
        orders_product_wise=_tabulate_info(summary["orders_per_sku"]["all_time"])
    )
    dest_file = reports_base + "/consolidated.txt"
    files_written.append(dest_file)
    with open(dest_file, "w") as handle:
        handle.write(report)
        logger.info("Consolidated report written to %s", dest_file)

    # all locations, yesterday
    report = REPORT_TEMPLATE_ALL_LOCATIONS.format(
        rtype="For {}".format(yesterday),
        n_orders=summary["total_orders_made"]["yesterday"],
        order_value=summary["order_value"]["yesterday"] or 0,
        n_unique_customers=summary["unique_customers"]["yesterday"],
        orders_product_wise=_tabulate_info(summary["orders_per_sku"]["yesterday"])
    )
    dest_file = reports_base + "/yesterday.txt"
    files_written.append(dest_file)
    with open(dest_file, "w") as handle:
        handle.write(report)
        logger.info("Yesterday's report written to %s", dest_file)
    headers = ["sku code", "sku name", "purchased", "fulfilled"]

    # per location, all time
    for city, locations_in_city in reporter.skus_sold_all_time.items():
        for outlet, outlet_sales in locations_in_city.items():
            data = []
            dest_file = reports_base + "/{city}/{outlet}-consolidated-till-{date}.txt".format(city=city, outlet=outlet, date=yesterday)
            logger.info("Breaking down for outlet %s, city: %s", outlet, city)
            for sku_code, sale_details in outlet_sales["items_in_store"].items():
                data.append((sku_code, sale_details.get("name"), sale_details.get("purchased"), sale_details.get("fulfilled")))
            data = sorted(data, key=lambda x: x[-1], reverse=True)
            sales = tabulate(data, headers=headers)
            report_text = REPORT_TEMPLATE_LOCATION_WISE_SKU_ORDERS.format(
                rtype="Consolidated till {yday}".format(yday=yesterday),
                store_name=reporter.outlet_map[city].get(outlet),
                orders_product_wise=sales
            )
            files_written.append(dest_file)
            with open(dest_file, "w") as handle:
                handle.write(report_text)
                logger.info("Wrote consolidated sku breakdown for outlet %s to %s", outlet, dest_file)

    # per location, yesterday
    for city, locations_in_city in reporter.skus_sold_yesterday.items():
        for outlet, outlet_sales in locations_in_city.items():
            data = []
            dest_file = reports_base + "/{city}/{outlet}-yesterday-{date}.txt".format(city=city, outlet=outlet, date=yesterday)
            logger.info("Breaking down for outlet %s, city: %s", outlet, city)
            for sku_code, sale_details in outlet_sales["items_in_store"].items():
                data.append((sku_code, sale_details.get("name"), sale_details.get("purchased"), sale_details.get("fulfilled")))
            data = sorted(data, key=lambda x: x[-1], reverse=True)
            sales = tabulate(data, headers=headers)
            report_text = REPORT_TEMPLATE_LOCATION_WISE_SKU_ORDERS.format(
                rtype="For {yday}".format(yday=yesterday),
                store_name=reporter.outlet_map[city].get(outlet),
                orders_product_wise=sales
            )
            files_written.append(dest_file)
            with open(dest_file, "w") as handle:
                handle.write(report_text)
                logger.info("Wrote yesterday's sku breakdown for outlet %s to %s", outlet, dest_file)

    destination_zip_file = "/tmp/report-{date}-{tenant_id}.zip".format(date=yesterday, tenant_id=tenant_id)
    chdir(reports_base)
    with ZipFile(destination_zip_file, "w") as zip:
        for f in files_written:
            archive_filename_dirs = f.split('/')[2:]
            archive_filename = '/'.join(archive_filename_dirs)
            zip.write(f, arcname=archive_filename)

    logger.info("Zip filed written to %s", destination_zip_file)
    email_text = EMAIL_BDOY.format(
        date=yesterday,
        fname=destination_zip_file.split('/')[-1],
        k=len(files_written),
        file_list="\n".join([x.replace("/tmp/", '') for x in files_written])
    )

    if reporting_ctx != "staging":
        mailing_details = reporter.get_mail_details()

        email_text = email_text + "\nThis is a system-generated email. Please do not respond to this email."

        mail_info = {
            'body': email_text,
            'subject': "Sales reports for %s via NUTY Technologies" %(mailing_details["name"]),
            'attachments': [destination_zip_file],
            'to': mailing_details["email"]
        }
        common.send_mail(mail_info)



def main():
    today = datetime.now()

    today_str = today.strftime("%Y-%m-%d")
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    tenants = list_tenants()
    report_execution_env = environ.get("REPORT_EXECUTION_CTX")
    for tnt in tenants:
        try:
            execute_report(tnt, yesterday, today_str, report_execution_env)
        except Exception as exp:
            common.logging.exception("Unable to process reports for tenant %s. Reason: %s" %(tnt, exp))


if __name__ == "__main__":
    main()