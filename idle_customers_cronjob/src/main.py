import pymongo
from datetime import datetime, timedelta
import logging
import os
import requests
from pythonjsonlogger import jsonlogger
import re

# Configure logger
formatter = jsonlogger.JsonFormatter("%(asctime)s - %(message)s")
json_handler = logging.StreamHandler()
json_handler.setFormatter(formatter)
logger = logging.getLogger('my_json')
logger.setLevel(logging.INFO)
logger.addHandler(json_handler)

# Environment variables
MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = os.environ.get("DATABASE_NAME")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME")
SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

# Function to fetch the last Slack message
def fetch_last_slack_message():
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    url = f"https://slack.com/api/conversations.history?channel={CHANNEL_ID}&limit=200"
    
    while url:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            messages = data.get("messages", [])
            
            for message in messages:
                if "Idle Customer Report" in message.get("text", ""):
                    return message["text"]  # Return the last relevant message's text
            
            # Paginate to the next batch of messages if available
            url = f"https://slack.com/api/conversations.history?channel={CHANNEL_ID}&cursor={data.get('response_metadata', {}).get('next_cursor')}"
        else:
            break  # Exit if API call fails
    
    return None


# Function to extract inactive accounts from the last message
def extract_inactive_accounts(last_message):
    if not last_message:
        return set()

    lines = last_message.split("\n")
    inactive_accounts = set()
#   print("Raw message lines:", lines)  # Debug: Log raw lines of the message
    for line in lines:
        # Remove Slack link formatting (<http...|...>)
        line = re.sub(r"<http.*\|([\w\.-]+)>", r"\1", line)
#        print("Processed line:", line)  # Debug: Log the processed line

        # Match lines containing account names and days inactive
        match = re.match(r"^\s*([\w\.-]+)\s+\d+\s*$", line)
        if match:
            account_name = match.group(1)
#            print("Extracted account:", account_name)  # Debug: Log the extracted account
            inactive_accounts.add(account_name)

#    print("Extracted accounts:", inactive_accounts)  # Debug: Log all extracted accounts
    return inactive_accounts

# Global variable to track previously reported inactive accounts
last_message = fetch_last_slack_message()
#print("The last message:", last_message)
last_message_accounts = extract_inactive_accounts(last_message)
#print("The last message accounts:", last_message_accounts)

# Function to send a report to Slack
def send_report_to_slack(inactive_accounts_sorted):
    global last_message_accounts
    current_date = datetime.now().strftime("%m/%d/%Y")
    current_accounts = set([account['name'] for account in inactive_accounts_sorted])

    # Calculate new reactivated accounts (only accounts removed from the last run)
    reactivated_accounts = last_message_accounts - current_accounts
    last_message_accounts = current_accounts  # Update for the next run

    if not inactive_accounts_sorted and not reactivated_accounts:
        message = "No idle enterprise accounts found."
    else:
        message = f":low_battery: Idle Customer Report {current_date} :low_battery:\n"

        # Separate accounts into categories
        rest_of_world = [
            "appsflyer.com", "helvetia.ch", "similarweb.com", "artlist.io",
            "aquasec.com", "moonactive.com", "tamnoon.io", "axissecurity.com",
            "ridewithvia.com", "axiom.security", "zoominfo.com", "final.co.il",
            "economist.com", "cyesec.com", "strauss-group.com", "moonactive-data-platform",
            "moonactive-infra-group", "moonactive-melsoft", "moonactive-traveltown",
            "moonactive-zm", "checkpoint.com", "checkpoint.com-perimeter81", "solitics.com"
        ]

        american_accounts = []
        rest_of_world_accounts = []

        for account in inactive_accounts_sorted:
            if account['name'] in rest_of_world:
                rest_of_world_accounts.append(account)
            else:
                american_accounts.append(account)

        # Format American accounts section
        if american_accounts:
            message += "American Accounts:\n"
            message += "```{:<30} {:<15}\n".format("Account Name", "Days Inactive")
            message += "-" * 50 + "\n"
            for account in american_accounts:
                message += "{:<30} {:<15}\n".format(account['name'], account['days_inactive'])
            message += "```\n"

        # Format Rest of the World section
        if rest_of_world_accounts:
            message += "Rest of the World:\n"
            message += "```{:<30} {:<15}\n".format("Account Name", "Days Inactive")
            message += "-" * 50 + "\n"
            for account in rest_of_world_accounts:
                message += "{:<30} {:<15}\n".format(account['name'], account['days_inactive'])
            message += "```\n"

        # Include only new reactivated accounts
        if reactivated_accounts:
            logger.info("Reactivated accounts found", extra={"reactivated_accounts": list(reactivated_accounts)})
            message += "\n:battery: Back to being active :battery:\n"
            message += "```\n"
            for account in sorted(reactivated_accounts):
                logger.debug(f"Adding reactivated account to message: {account}")
                message += f"{account}\n"
            message += "```"

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
    print("Successfully connected to MongoDB.")
except Exception as e:
    print("Failed to connect to MongoDB:", e)
    logger.error("Error connecting to MongoDB", extra={"error": str(e)})
    raise

# Define the number of days
days_threshold = 14
current_date = datetime.now()
logger.info("Script started", extra={"days_threshold": days_threshold, "current_date": current_date})

ignored_names = [
    "apple.com", "acme", "axiom.security", "Skyhawk.security",
    "robert-maury.com", "tamnoon.io", "blueally.com",
    "barefootcoders.com", "nedinthecloud.com", "dailyhypervisor.com",
    "moonactive-melsoft",  "moonactive-zm", "moonactive-traveltown", 
    "comtech-CPSS", "comtech-ctl-eng-prod", "comtech-smsc", "comtech-scm", "comtech-cybr", "comtech-prod", 
    "sportradar-production-engineering", "sportradar-devops", "sportradar-odds", "sportradar-av", "sportradar.com",
    "sportradar-comp-solutions", "sportradar-ads", "spinbyoxxo.com.mx", "moonactive-data-platform",
    "moonactive-infra-group", "moonactive-melsoft", "moonactive-traveltown", "moonactive-zm"
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

send_report_to_slack(inactive_accounts_sorted)