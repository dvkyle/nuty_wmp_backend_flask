import os
import logging
from flask import Flask, escape, request

logging.basicConfig(
    format="[%(asctime)s] - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

MANAGEMENT_APPLICATION = os.environ.get("MANAGEMENT_APPLICATION")

app = Flask(MANAGEMENT_APPLICATION)

@app.route("/management/chillers/add")
def chillerAdd():
    pass


@app.route("/management/inventory/add")
def inventoryAdd():
    pass


@app.route("/management/store/add")
def storeAdd():
    pass
