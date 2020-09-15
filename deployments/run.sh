#!/bin/sh

/etc/init.d/nginx start
service redis-server restart

cd /home/src/wmp_backend/
./wmp_backend_api.sh

