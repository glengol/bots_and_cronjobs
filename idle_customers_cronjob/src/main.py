import pymongo
from datetime import datetime, timedelta
import logging
import os
import requests
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


def send_report_to_slack(inactive_accounts_sorted):
    if not inactive_accounts_sorted:
        message = "No idle enterprise accounts found."
    else:
        message = ":low_battery: Idle Customer Report :low_battery:\n"
        message += "```{:<30} {:<15}\n".format("Account Name", "Days Inactive")  # Headers without Account ID
        message += "-"*50 + "\n"  # Separator
        for account in inactive_accounts_sorted:
            message += "{:<30} {:<15}\n".format(account['name'], account['days_inactive'])
        message += "```"  # End of code block for formatting
    
    # Send POST request to Slack
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        if response.status_code != 200:
            logger.error("Failed to send report to Slack", extra={"status_code": response.status_code, "response": response.text})
        else:
            logger.info("Successfully sent idle customer report to Slack")
    except Exception as e:
        logger.error("Error sending report to Slack", extra={"error": str(e)})


# Connect to MongoDB
try:
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error("Error connecting to MongoDB", extra={"error": str(e)})
    raise

# Define the number of days
days_threshold = 14
current_date = datetime.now()
logger.info("Script started", extra={"days_threshold": days_threshold, "current_date": current_date})

ignored_names = [
    "apple.com", "axiom.security", "Skyhawk.security", "moonactive-traveltown", 
    "robert-maury.com", "sportradar-production-engineering", "sportradar-devops", 
    "barefootcoders.com", "nedinthecloud.com", "sportradar-av", "moonactive-zm", 
    "moonactive-melsoft", "dailyhypervisor.com", "blueally.com", "comtech-CPSS", 
    "comtech-ctl-eng-prod", "comtech-smsc", "comtech-scm", "comtech-cybr", 
    "comtech-prod", "sportradar-odds", "sportradar-ads", "tamnoon.io"
]
# Query for enterprise accounts
try:
    enterprise_accounts = collection.find({
        "tier_type": "ENTERPRISE",
        "active": True,
        "name": {"$nin": ignored_names}
    }, {"_id": 1, "name": 1, "latest_activity": 1})
    account_count = collection.count_documents({
        "tier_type": "ENTERPRISE",
        "name": {"$nin": ignored_names},
        "active": True  # Include only active accounts
    })
    logger.info("Enterprise accounts retrieved", extra={"account_count": account_count})
except Exception as e:
    logger.error("Error querying MongoDB", extra={"error": str(e)})
    raise

# Prepare a list of accounts that haven't logged in for more than 14 days
inactive_accounts = []
for account in enterprise_accounts:
    if 'latest_activity' in account:
        latest_activity_date = account['latest_activity']
        days_inactive = (current_date - latest_activity_date).days
        
        if days_inactive >= days_threshold:
            inactive_accounts.append({
                'account_id': account['_id'],
                'name': account.get('name', 'Unknown'),
                'latest_activity': latest_activity_date,
                'days_inactive': days_inactive
            })
            logger.info("Inactive account found", extra={"account_id": account['_id'], "account_name": account.get('name', 'Unknown'), "days_inactive": days_inactive})

# Sort the accounts by days inactive (descending order)
inactive_accounts_sorted = sorted(inactive_accounts, key=lambda x: x['days_inactive'], reverse=True)
logger.info("Accounts sorted by days inactive", extra={"sorted_account_count": len(inactive_accounts_sorted)})

# Output the results
for account in inactive_accounts_sorted:
    logger.info("Account details", extra={
        'account_id': account['account_id'],
        'latest_activity': account['latest_activity'],
        'days_inactive': account['days_inactive']
    })

send_report_to_slack(inactive_accounts_sorted)
