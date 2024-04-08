import pymongo
import requests
import logging
import time
import os
from datetime import datetime, timedelta
from pythonjsonlogger import jsonlogger

# Configure logger
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

# Calculate the date one month ago
year = current_date.year
month = current_date.month - 1
day = current_date.day

# Adjust for cases where the previous month was the previous year
if month == 0:
    year -= 1
    month = 12

# Determine the number of days in the previous month
if month in [1, 3, 5, 7, 8, 10, 12]:
    num_days_in_previous_month = 31
elif month == 2:
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        num_days_in_previous_month = 29  # Leap year
    else:
        num_days_in_previous_month = 28
else:
    num_days_in_previous_month = 30

# If the current day is greater than the last day of the previous month,
# set it to the last day of the previous month
if day > num_days_in_previous_month:
    day = num_days_in_previous_month

# Construct the datetime object for one month ago
last_month_date = datetime(year, month, day)


query = {"tier_type": "PREMIUM_TRIAL", 
         "active": True, 
         "onbording_status": "done", 
         "license_start": {"$gte": last_month_date}}
accounts = collection.find(query, {"_id": 1, "license_start": 1, "name": 1, "latest_activity": 1}).sort("license_start", 1)

for account in accounts:
    license_start: datetime = account.get("license_start")
    latest_activity: datetime = account.get("latest_activity")
    license_start = datetime(license_start.year,license_start.month, license_start.day)
    account_id = account.get("_id")
    account_name = account.get("name", "")

    if license_start is None:
        logger.warning(f"Skipping account {account_id}: 'license_start' attribute is missing or None.")
        continue

    days_passed = (current_date.date() - license_start.date()).days
    days_left = 15 - days_passed
    

    if days_left > 0 and days_left < 3:
        last_login = (current_date.date() - latest_activity.date()).days
        message = f":rotating_light: {account_name} *trial will end in {days_left} days* :rotating_light:\n*Days since last login*: {last_login}\n*Account ID*: {account_id}"
        payload = {"text": message}

        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            logger.info(f"Message sent to Slack successfully for account {account_id}.")
        else:
            logger.error(f"Failed to send message to Slack for account {account_id}. Status code: {response.status_code}")
    else:
        logger.info(f"Skipping account {account_id}: premium trial expiration is not imminent.")

