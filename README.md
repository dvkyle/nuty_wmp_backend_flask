# Management utils

This repository contains a set of scripts that can be used by ops teams to create records for:
- New Stores
- New SKUs
- Adding items to the inventory

## Basic Assumptions
People using this script are expected to know these things at the very least:
- Using the Linux command line (either via a pure Linux environment or via WSL/WSL2 or a VM)
- [Dealing with environment variables in Linux](https://www.serverlab.ca/tutorials/linux/administration-linux/how-to-set-environment-variables-in-linux/)
- [Generating an SSH Keypair](https://www.ssh.com/ssh/keygen/#creating-an-ssh-key-pair-for-user-authentication)
- [Connecting to a server via SSH](https://mediatemple.net/community/products/dv/204403684/connecting-via-ssh-to-your-server)
- [Using Git](https://opensource.com/article/18/1/step-step-guide-git)
- [Being able to execute a python script from the command line](https://www.knowledgehut.com/blog/programming/run-python-scripts)


## Operating environment

### OS
We recommend running this script within a Linux distro (like Ubuntu, Debian, etc). This is what we recommend for Linux:
```
Distributor ID: Ubuntu
Description:    Ubuntu 18.04.4 LTS
Release:        18.04
Codename:       bionic
```

### Runtime Environment
We require Python 3.x. This is the version we recommend:
```
14:55 $ python --version
Python 3.6.9
(dev) ✔ ~/workspace/tulitahara-py/management [master|✚ 1]
14:55 $
``` 
In addition, we recommend running this script within the context of a [virtualenv](https://virtualenv.pypa.io/en/stable/)


### Environment variables required
The script expects these variables to be set a-priori with relevant values:
```
AZ_STOR_CNXN_STR
AZ_STOR_ACCT_KEY
AZ_STOR_ACCT_NAME
AZ_IMAGES_CONTAINER
```

If you are not sure of what values are required, contact Prashant Warrier.


## Scripts that are used
These scripts can be used:

- [add_chillers](#management/add_chillers.py)
- [load_skus](#management/load_skus.py)
- [load_inventory](#management/load_inventory.py)


## management/add_chillers.py
This script lets you create a store record in the database. This block describes the script's usage:
```
usage: add_chillers [-h] -i OUTLET_ID -b BUSINESS_NAME -o OUTLET_NAME -n
                    CONTACT -a AREA -s STREET_ADDRESS -c CITY -p POSTAL_CODE
                    -r REGION -g GOOGLE_MAPS_URL
                    [--starting-time STARTING_TIME]
                    [--closing-time CLOSING_TIME]
```

Here are the parameters to the script:
```
  -h, --help            show this help message and exit
  -i OUTLET_ID, --outlet-id OUTLET_ID
                        Chiller's outlet ID
  -b BUSINESS_NAME, --business-name BUSINESS_NAME
                        The name of the business
  -o OUTLET_NAME, --outlet-name OUTLET_NAME
                        The name of the outlet
  -n CONTACT, --contact CONTACT
                        Outlet contact
  -a AREA, --area AREA  The area where this outlet is localted
  -s STREET_ADDRESS, --street-address STREET_ADDRESS
                        The outlet's street address
  -c CITY, --city CITY  The city where this outlet is located
  -p POSTAL_CODE, --postal-code POSTAL_CODE
                        The city's postal code
  -r REGION, --region REGION
                        The state where the outlet is located
  -g GOOGLE_MAPS_URL, --google-maps-url GOOGLE_MAPS_URL
                        The outlet's URL from Google Maps
  --starting-time STARTING_TIME
                        The outlet's opening time. Specify as HH:MM
  --closing-time CLOSING_TIME
                        The outlet's closing time. Specify as HH:MM
```

`--starting-time` and `--closing-time` **are not compulsory**. Everything else **is compuslory** 

An example run would look like this:
```
14:37 $ python add_chillers.py -i 'BLR2C00097' -b 'NÜTY - Platinum City' -o 'Fair N Fair super market' -n '919324948290' -a 'Platinum City' -s 'Platinum City, Industrial Area,Stage 1, 2nd Stage' -c 'Bengaluru' -
p '560022' -r 'Karnataka' -g 'https://www.google.com/maps/place/N%C3%9CTY+-+Platinum+City/@13.036315,77.5295749,17z/data=!3m1!4b1!4m5!3m4!1s0x0:0x10c6b39a2c07d2c8!8m2!3d13.036315!4d77.5317636' --starting-time '1
1:00' --closing-time '19:00'
Summary:

outlet_id       BLR2C00097
business_name   NÜTY - Platinum City
outlet_name     Fair N Fair super market
contact 919324948290
area    Platinum City
street_address  Platinum City, Industrial Area,Stage 1, 2nd Stage
city    Bengaluru
postal_code     560022
region  Karnataka
google_maps_url https://www.google.com/maps/place/N%C3%9CTY+-+Platinum+City/@13.036315,77.5295749,17z/data=!3m1!4b1!4m5!3m4!1s0x0:0x10c6b39a2c07d2c8!8m2!3d13.036315!4d77.5317636
starting_time   11:00
closing_time    19:00
Confirm and create? [yes|no]
```

The script asks for confirmation. Enter either "yes" or "no". If you enter "no", the script will abort and will not create a chiller record.

If you enter "yes", expect this kind of output:
```
Confirm and create? [yes|no]yes
[2020-04-08 14:42:33,866] - INFO - database_connection - Trying to sping up a database connection from a pool
[2020-04-08 14:42:33,866] - INFO - db_connection_pool - Attempting to spin-up connection pool. __name__: add_chillers.py
[2020-04-08 14:42:34,171] - INFO - db_connection_pool - Connection pool created
[2020-04-08 14:42:34,173] - INFO - add_chillers - Chiller timezone: Asia/Kolkata
[2020-04-08 14:42:34,259] - INFO - add_chillers - Will save chiller record: chiller-fairnfairsupermarket-platinumcity
[2020-04-08 14:42:34,263] - INFO - create_franchisee_record - Creating franchisee record. Chiller name: chiller-fairnfairsupermarket-platinumcity
[2020-04-08 14:42:34,438] - INFO - upload_to_azure_storage - Uploading /tmp/chiller-fairnfairsupermarket-platinumcity.png to Azure storage account
[2020-04-08 14:42:34,439] - INFO - try_create_azure_container - Attempting to create container qr-codes if it does not exist already
[2020-04-08 14:42:34,855] - INFO - upload_to_azure_storage - File /tmp/chiller-fairnfairsupermarket-platinumcity.png uploaded to azure
[2020-04-08 14:42:34,855] - INFO - create_franchisee_record - QR Code uploaded to https://tastorestaging.blob.core.windows.net/qr-codes/chiller-fairnfairsupermarket-platinumcity.png
(dev) ✔ ~/workspace/tulitahara-py/management [master|…1]
14:42 $
```

## management/load_skus.py

This script lets you create SKU records in the database. The following block describes the script's usage:
```
usage: load_skus.py [-h] -c CATEGORY -s SKU_CODE -n SKU_NAME -d
                    SKU_DESCRIPTION -q QUANTITY_GRAM -p PRICE -i IMAGE_URL -k
                    ENERGY_KCAL -t PROTEIN_GM -f TOTAL_FAT_GM -x
                    EXPIRY_INTERVAL_DAYS [-r {INR,USD,CNY,RMB}]
```

These are the parameters that you can pass to the script:
```
  -h, --help            show this help message and exit
  -c CATEGORY, --category CATEGORY
                        The SKU category
  -s SKU_CODE, --sku-code SKU_CODE
                        The SKU Code
  -n SKU_NAME, --sku-name SKU_NAME
                        The SKU Name
  -d SKU_DESCRIPTION, --sku-description SKU_DESCRIPTION
                        The SKU's description
  -q QUANTITY_GRAM, --quantity-gram QUANTITY_GRAM
                        The product's quantity in grams
  -p PRICE, --price PRICE
                        The product's price
  -i IMAGE_URL, --image-url IMAGE_URL
                        The product's image URL
  -k ENERGY_KCAL, --energy-kcal ENERGY_KCAL
                        Product's calorie count.
  -t PROTEIN_GM, --protein-gm PROTEIN_GM
                        Amount of protein in the product
  -f TOTAL_FAT_GM, --total-fat-gm TOTAL_FAT_GM
                        Total fat in gram in the product
  -x EXPIRY_INTERVAL_DAYS, --expiry_interval_days EXPIRY_INTERVAL_DAYS
                        The number of days within which an item in this SKU
                        will expire
  -r {INR,USD,CNY,RMB}, --currency {INR,USD,CNY,RMB}
                        The product's price currency
```

**ALL PARAMETERS ARE REQUIRED**

An example run looks like:

```
14:49 $ python load_skus.py -c "Veg Curries" -s "nucomvc001" -n "Palak Paneer" -d "Creamy Palak Paneer Made With Fresh Spinach Leaves, Paneer, Onions, Herbs And Spices. Serve It with Rice, Roti or Naan." -q 280
-p 80 -k 183 -t 7.5 -f 15 -x 45 -r INR -i 'https://drive.google.com/open?id=1GoFBm-H9IbFuYFEP5N0fAeaa6dKXYwnf'
Summary:
{
    "category": "Veg Curries",
    "sku_code": "nucomvc001",
    "sku_name": "Palak Paneer",
    "sku_description": "Creamy Palak Paneer Made With Fresh Spinach Leaves, Paneer, Onions, Herbs And Spices. Serve It with Rice, Roti or Naan.",
    "quantity_gram": "280",
    "price": "80",
    "image_url": "https://drive.google.com/open?id=1GoFBm-H9IbFuYFEP5N0fAeaa6dKXYwnf",
    "energy_kcal": "183",
    "protein_gm": "7.5",
    "total_fat_gm": "15",
    "expiry_interval_days": "45",
    "currency": "INR"
}

Confirm and create SKU record? [yes|no]
```

The script will print the details of the SKU being inserted and will ask for confirmation. If you enter "yes", expect this kind of output:
```
[2020-04-08 14:50:31,342] - INFO - oauth2client.transport - Attempting refresh to obtain initial access_token
[2020-04-08 14:50:31,829] - INFO - download_image_from_gdrive - Will download file to /tmp/nucomvc001.jpg
[2020-04-08 14:50:32,786] - INFO - download_image_from_gdrive - Image https://drive.google.com/open?id=1GoFBm-H9IbFuYFEP5N0fAeaa6dKXYwnf downloaded to file /tmp/nucomvc001.jpg
[2020-04-08 14:50:32,786] - INFO - upload_to_media_server - Uploading /tmp/nucomvc001.jpg to https://media-server-staging.nuty.in
[2020-04-08 14:50:33,827] - INFO - load_skus - Attempting insertion of record: ('nucomvc001', 'Palak Paneer', 'Creamy Palak Paneer Made With Fresh Spinach Leaves, Paneer, Onions, Herbs And Spices. Serve It with
Rice, Roti or Naan.', 'https://media-server-staging.nuty.in/products/nucomvc001.jpg', '45 days', '80', 'INR', 'Veg Curries', '280', '{"energy_kcal": "183", "protein-gm": "7.5", "total-fat-gm": "15"}')
[2020-04-08 14:50:33,827] - INFO - database_connection - Trying to sping up a database connection from a pool
[2020-04-08 14:50:33,827] - INFO - db_connection_pool - Attempting to spin-up connection pool. __name__: load_skus.py
[2020-04-08 14:50:34,124] - INFO - db_connection_pool - Connection pool created
[2020-04-08 14:50:34,125] - INFO - load_skus - Record inserted. result: nucomvc001
``` 

## management/load_inventory.py

This script lets you create/update inventory records against each (SKU, chiller) combination in the database. The following block describes the script's usage:
```
usage: load_inventory.py [-h] -o OUTLET_IDS [OUTLET_IDS ...] -w WORKSHEET -t
                         TITLE
```

**ALL PARAMETERS ARE REQUIRED**

An example run would look like:
```
15:31 $ python management/load_inventory.py -o BLR2C00097 BLR2C00124 -w Inventory-Threshold -t '2020-03-03-13-59-53'
Summary:
{
    "outlet_ids": [
        "BLR2C00097",
        "BLR2C00124"
    ],
    "worksheet": "Inventory-Threshold",
    "title": "2020-03-03-13-59-53"
}

Confirm and update? [yes|no]
```

The script will ask for confirmation. Upon entering "yes", expect this kind of output:
```
[2020-04-08 15:32:57,840] - INFO - database_connection - Trying to sping up a database connection from a pool
[2020-04-08 15:32:57,840] - INFO - db_connection_pool - Attempting to spin-up connection pool. __name__: load_inventory.py
[2020-04-08 15:32:58,224] - INFO - db_connection_pool - Connection pool created
[2020-04-08 15:32:58,224] - INFO - get_sheets - Listing sheets from Inventory-Threshold
Updating inventories for outlets: {'BLR2C00097', 'BLR2C00124'}
[2020-04-08 15:33:00,642] - INFO - root - Updating inventory for outlet id BLR2C00097, chiller chiller-fairnfairsupermarket-platinumcity
[2020-04-08 15:33:00,645] - INFO - root - Adding nucomsc002 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,648] - INFO - root - Adding nucomsc003 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,649] - INFO - root - Adding nucomsc004 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,651] - INFO - root - Adding nucomsc005 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,652] - INFO - root - Adding nucomsc006 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,653] - INFO - root - Adding nucomvc001 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,655] - INFO - root - Adding nucomvc002 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,656] - INFO - root - Adding nucomvc003 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,657] - INFO - root - Adding nucomvc004 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,662] - INFO - root - Adding nucomcc001 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,666] - INFO - root - Adding nucomcc002 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,669] - INFO - root - Adding nucomcc003 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,670] - INFO - root - Adding nucomcc004 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,673] - INFO - root - Adding nucomsc001 to chiller-fairnfairsupermarket-platinumcity's inventory.
[2020-04-08 15:33:00,676] - INFO - root - Updating inventory for outlet id BLR2C00124, chiller chiller-neenterprisefoodmart-sarjapurroad
[2020-04-08 15:33:00,677] - INFO - root - Adding nucomsc002 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,678] - INFO - root - Adding nucomsc003 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,678] - INFO - root - Adding nucomsc004 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,679] - INFO - root - Adding nucomsc005 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,681] - INFO - root - Adding nucomsc006 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,682] - INFO - root - Adding nucomvc001 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,683] - INFO - root - Adding nucomvc002 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,684] - INFO - root - Adding nucomvc003 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,685] - INFO - root - Adding nucomvc004 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,686] - INFO - root - Adding nucomcc001 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,689] - INFO - root - Adding nucomcc002 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,690] - INFO - root - Adding nucomcc003 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,691] - INFO - root - Adding nucomcc004 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
[2020-04-08 15:33:00,692] - INFO - root - Adding nucomsc001 to chiller-neenterprisefoodmart-sarjapurroad's inventory.
```
