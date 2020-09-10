import argparse, os, base64

from collections import namedtuple
from utils.common import master_database_connection, getLogger
from kubernetes import client, config
from uuid import uuid4

OptParam = namedtuple("OptParam", ["flag_short", "flag_long", "description", "type", "required", "choices", "default"])

OPTIONS = {
    "name": OptParam('-t', '--tenant-name', "The tenant's Full Name", str, True, None, None),
    "email": OptParam("-e", "--email-address", "The tenant's email address", str, True, None, None),
    "phone": OptParam("-p", "--phone-number", "The tenant's contact number", str, True, None, None),
    "address": OptParam("-a", "--registered-address", "The tenant's registered address", str, True, None, None),
    "tax": OptParam("-g", "--gst-number", "The Tenant's GST number", str, True, None, None),
    "base_logo": OptParam("-b", "--base-logo", "The Tenant's logo", str, False, None, None),
    "receipt_logo": OptParam("-r", "--receipt-logo", "The tenant's receipt logo", str, False, None, None),
    "tenant_id": OptParam("-i", "--tenant-id", "A tenant id", str, True, None, None),
    "exec_env": OptParam("-v", "--exec-env", "The execution environment", str, False, ["staging", "production-ecommerce"], "staging"),
    "cloud": OptParam("-c", "--cloud", "The cloud within which this script is being executed", str, False, ["azure", "aws"], "azure"),
    "dry_run": OptParam("-x", "--dry-run", "Do not commit any changes", bool, False, None, False)
}


APPLICATION_NAME = "tenant.py"
def __list_tables_with_rls():
    logger = getLogger("__list_tables_with_rls")
    logger.info("Listing tables which require RLS")
    result_set = None
    try:
        connection = master_database_connection(application_name=APPLICATION_NAME)
        query = "select table_name from information_schema.columns where column_name = 'tenant_id' and table_name != 'tenant_info' order by table_name asc;"
        logger.info("Executing query: %s", query)
        cursor = connection.cursor()
        cursor.execute(query)
        result_set = cursor.fetchall()
        result_set = [x[0] for x in result_set]
        logger.info("Tables which need RLS: %s", result_set)
        cursor.close()
        connection.close()
    except Exception as exp:
        logger.exception("An exception occured while trying to list tables from the database: %s", exp)
    finally:
        cursor.close()
        connection.close()
        return result_set


def __list_sequences():
    logger = getLogger("_list_sequences")
    logger.info("Listing sequences which require access grant")
    query = "select sequence_name from information_schema.sequences where sequence_schema = 'public' and sequence_catalog = 'tulitahara';"
    logger.info("Executing query: %s", query)
    result_set = None
    try:
        connection = master_database_connection(application_name=APPLICATION_NAME)
        cursor = connection.cursor()
        cursor.execute(query)
        result_set = cursor.fetchall()
        result_set = [x[0] for x in result_set]
        logger.info("Sequences which need grants: %s", result_set)
    except Exception as exp:
        logger.exception("An exception occured while listing sequences: %s", exp)
    finally:
        cursor.close()
        connection.close()
        return result_set


def __update_pgbouncer_userlist(k8s_environment, user, passwd):
    home = os.environ.get("HOME")
    k8s_config_file = "{home}/.kube/config-{k8s_environment}".format(home=home, k8s_environment=k8s_environment)
    logger = getLogger("__update_pgbouncer_userlist")
    logger.info("Updating pgbouncer userlist within k8s. Looking at k8s config at %s", k8s_config_file)
    config.load_kube_config(config_file=k8s_config_file)
    core_v1_api = client.CoreV1Api()
    pgbouncer_config_secret = "pgbouncer-configuration"
    namespace = "default"
    logger.info("Looking up secret %s in namespace %s", pgbouncer_config_secret, namespace)
    secret = core_v1_api.read_namespaced_secret(name=pgbouncer_config_secret, namespace=namespace)
    secret_data = secret.data
    userlist_txt = base64.b64decode(secret_data["userlist.txt"]).decode("utf-8")
    line = "\"{user}\" \"{passwd}\"\n".format(user=user, passwd=passwd)
    userlist_txt = userlist_txt + line
    updated_userlist = base64.b64encode(bytes(userlist_txt, "utf-8")).decode("utf-8")
    logger.info("Updated userlist: %s", updated_userlist)
    patch_to_apply = {
        "pgbouncer.ini": secret_data["pgbouncer.ini"],
        "userlist.txt": updated_userlist
    }

    logger.info("Produced patch to apply")
    updated_secret = client.V1Secret(data=patch_to_apply)
    core_v1_api.patch_namespaced_secret(name=pgbouncer_config_secret, namespace=namespace, body=updated_secret)
    logger.info("DB login %s added to userlist.txt", user)


def _create_tenant_record(tenant_info, dry_run=False):
    logger = getLogger("_create_tenant_record")
    tenant_key = str(uuid4())
    query = """
    INSERT INTO tenant_info (
        tenant_id,
        name,
        address,
        contact,
        email,
        tenant_key,
        tenant_passwd_crypt,
        db_user,
        gstin,
        base_logo,
        receipt_logo
    )
    VALUES (
        %s,
        %s,
        %s,
        %s,
        %s,
        %s,
        crypt(%s, 'bf'),
        %s,
        %s,
        %s,
        %s
    )
    """
    result = {}
    try:
        connection = master_database_connection(application_name=APPLICATION_NAME)
        cursor = connection.cursor()

        db_user = None
        cloud = tenant_info.get("cloud")
        tenant_id = tenant_info.get("tenant_id")

        if cloud == "aws":
            db_user = tenant_id
        elif cloud == "azure":
            db_server = os.environ.get("DB_SERVER")
            db_user = "%s@%s" %(tenant_id, db_server)

        params = (
            tenant_id,
            tenant_info.get("name"),
            tenant_info.get("address"),
            tenant_info.get("contact"),
            tenant_info.get("email"),
            tenant_key,
            tenant_key,
            db_user,
            tenant_info.get("gst_number"),
            tenant_info.get("base_logo"),
            tenant_info.get("receipt_logo")
        )
        cursor.execute(query, params)
        if not dry_run:
            connection.commit()
        logger.info("Tenant record created")
        result = {
            "db_role": tenant_id,
            "db_passwd": tenant_key,
            "db_user_login": db_user
        }
    except Exception as exp:
        logger.exception("Error while creating tenant. Reason: %s", exp)
        raise exp
    finally:
        cursor.close()
        connection.rollback()
        connection.close()
        return result


def _create_database_role(role_details, dry_run=False):
    user = role_details.get("db_role")
    passwd = role_details.get("db_passwd")
    logger = getLogger("_create_database_role")
    query = "CREATE USER %s WITH ENCRYPTED PASSWORD '%s';" %(user, passwd)
    try:
        connection = master_database_connection(application_name=APPLICATION_NAME)
        cursor = connection.cursor()
        cursor.execute(query)
        if not dry_run:
            connection.commit()
        logger.info("Role %s created", user)
    except Exception as exp:
        logger.exception("Unable to create database role. Reason: %s. Rolling back this txn", exp)
        connection.rollback()
        cursor.close()
        raise exp
    finally:
        connection.close()


def create_tenant(args):
    logger = getLogger("create_tenant")
    dry_run = args.dry_run
    logger.info("Creating tenant. Arguments: %s", args)
    tenant_id = args.tenant_name.lower().replace(' ', '')
    tenant_info = {
        "tenant_id": tenant_id,
        "name": args.tenant_name,
        "address": args.registered_address,
        "contact": args.phone_number,
        "email": args.email_address.lower(),
        "gst_number": args.gst_number.lower(),
        "base_logo": args.base_logo,
        "receipt_logo": args.receipt_logo,
        "cloud": args.cloud
    }
    logger.info("Creating tenant record. Details follow:")
    for k, v in tenant_info.items():
        print ("%s: %s" %(k, v))
    confirmation = input("Confirm and create tenant? [yes|no]")
    if confirmation != "yes":
        logger.info("Aborting tenant creation")
        return
    try:
        tenant_login_details = _create_tenant_record(tenant_info, dry_run)
        if not tenant_login_details:
            raise ValueError("Unable to obtain tenant login details")

        _create_database_role(tenant_login_details, dry_run)

        tables = __list_tables_with_rls()
        sequences = __list_sequences()

        template_query_grant_table_access = "GRANT INSERT, SELECT, UPDATE, DELETE on table %s to %s"
        template_query_create_policy_on_table = "CREATE POLICY %s_policy on %s FOR ALL TO %s using (tenant_id='%s') with check (tenant_id='%s')"
        template_query_grant_sequence_access = "GRANT SELECT, USAGE ON SEQUENCE %s to %s"

        connection = master_database_connection(application_name=APPLICATION_NAME)
        cursor = connection.cursor()
        for tbl in tables:
            query_grant_table_access = template_query_grant_table_access %(tbl, tenant_id)
            cursor.execute(query_grant_table_access)
            logger.info("Granted access to table %s", tbl)

            query_create_policy_on_table = template_query_create_policy_on_table %(tenant_id, tbl, tenant_id, tenant_id, tenant_id)
            cursor.execute(query_create_policy_on_table)
            logger.info("Created RLS policy %s_policy for table %s", tenant_id, tbl)

        for seq in sequences:
            query_grant_sequence_access = template_query_grant_sequence_access % (seq, tenant_id)
            cursor.execute(query_grant_sequence_access)
            logger.info("Granted access to sequence %s to user", seq)

        if not dry_run:
            connection.commit()
        cursor.close()
        __update_pgbouncer_userlist(args.exec_env, tenant_login_details.get("db_user_login"), tenant_login_details.get("db_passwd"))

    except Exception as exp:
        logger.exception("Error while creating tenant. Reason: %s", exp)
        connection.rollback()
        raise exp

    finally:
        connection.close()


def disable_tenant(args):
    return


def enable_tenant(args):
    return


ACTIONS = {
    "create": create_tenant,
    "disable": disable_tenant,
    "enable": enable_tenant
}

def obtain_argparser_for_verb(verb, options, sub_parser):
    if verb not in ACTIONS:
        return ValueError("%s is not a valid action" %verb)
    parser = sub_parser.add_parser(name=verb)
    parser.set_defaults(func=ACTIONS[verb])
    
    for opt in options:
        if opt not in options:
            raise ValueError("%s is not a valid option for action %s" %(opt, verb))
        param = OPTIONS[opt]
        choices = param.choices
        default = param.default
        if param.type != bool:
            parser.add_argument(param.flag_short, param.flag_long, help=param.description, required=param.required, choices=choices, default=default)
        else:
            parser.add_argument(param.flag_short, param.flag_long, help=param.description, required=param.required, default=default, action='store_true')
    return parser


def main():
    parser = argparse.ArgumentParser(prog="tenant.py")

    sub_parser = parser.add_subparsers()
    create = obtain_argparser_for_verb("create", ["name", "email", "phone", "address", "tax", "base_logo", "receipt_logo", "exec_env", "cloud", "dry_run"], sub_parser)
    disable = obtain_argparser_for_verb("disable", ["tenant_id"], sub_parser)
    enable = obtain_argparser_for_verb("enable", ["tenant_id"], sub_parser)

    arguments = parser.parse_args()
    arguments.func(arguments)


if __name__ == "__main__":
    main()
