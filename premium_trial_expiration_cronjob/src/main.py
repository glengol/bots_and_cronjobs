import pymongo
import requests
from pythonjsonlogger import jsonlogger
import logging
import time
import os
from datetime import datetime, timedelta

formatter = jsonlogger.JsonFormatter("%(asctime)s - %(message)s")
json_handler = logging.StreamHandler()
json_handler.setFormatter(formatter)
logger = logging.getLogger('my_json')
logger.setLevel(logging.INFO)
logger.addHandler(json_handler)

MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = os.environ.get("DATABASE_NAME")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

client = pymongo.MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

current_date = datetime.now()
current_date = datetime(current_date.year,current_date.month, current_date.day)
last_month_date = current_date.replace(month=current_date.month - 1)

query = {"tier_type": "PREMIUM_TRIAL", 
         "active": True, 
         "onbording_status": "done", 
         "license_start": {"$gte": last_month_date}}
accounts = collection.find(query, {"_id": 1, "license_start": 1, "name": 1})

for account in accounts:
    license_start: datetime = account.get("license_start")
    license_start = datetime(license_start.year,license_start.month, license_start.day)
    account_id = account.get("_id")
    account_name = account.get("name", "")

    if license_start is None:
        logger.warning(f"Skipping account {account_id}: 'license_start' attribute is missing or None.")
        continue

    days_passed = (current_date.date() - license_start.date()).days
    days_left = 15 - days_passed

    if days_left > 0 and days_left < 4:
        message = f"This account {account_id} ({account_name}) is about to expire! :hourglass_flowing_sand: There are {days_left} more days for the premium trial to finish."
        payload = {"text": message}

        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            logging.info(f"Message sent to Slack successfully for account {account_id}.")
        else:
            logging.error(f"Failed to send message to Slack for account {account_id}. Status code: {response.status_code}")
    else:
        logging.info(f"Skipping account {account_id}: premium trial expiration is not imminent.")

