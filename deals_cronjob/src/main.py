import requests
from datetime import datetime, timedelta, timezone
import calendar
import os

# HubSpot API Key
# API Endpoints
API_KEY_DEALS = os.environ.get("API_KEY_DEALS")
DEALS_API_URL = os.environ.get("DEALS_API_URL")
OWNERS_API_URL = os.environ.get("OWNERS_API_URL")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


# Deal type to filter
DEAL_TYPE = "newbusiness"  # Internal ID for New Business
DAYS = 7  # Last 7 days


def get_hubspot_owners():
    """Fetch all HubSpot owners to map owner IDs to names."""
    headers = {
        "Authorization": f"Bearer {API_KEY_DEALS}",
        "Content-Type": "application/json",
    }
    response = requests.get(OWNERS_API_URL, headers=headers)
    if response.status_code != 200:
        print("Error fetching owners:", response.status_code, response.text)
        return {}
    
    owners = response.json().get("results", [])
    # Create a mapping of owner_id to owner_name
    return {owner["id"]: owner["firstName"] + " " + owner["lastName"] for owner in owners if "firstName" in owner and "lastName" in owner}

def get_recent_deals_by_type(deal_type, days=7, owners_map=None):
    """Fetch all deals from HubSpot CRM with a specific deal type and created in the last 'days' days."""
    headers = {
        "Authorization": f"Bearer {API_KEY_DEALS}",
        "Content-Type": "application/json",
    }
    params = {
        "limit": 100,  # Number of records per page
        "properties": "dealtype,dealname,amount,createdate,hubspot_owner_id,deal_source_1,deal_source_2",  # Include required properties
        "archived": "false",
    }

    # Calculate the cutoff datetime
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    deals = []
    has_more = True
    after = None

    while has_more:
        if after:
            params["after"] = after  # Pagination token

        response = requests.get(DEALS_API_URL, headers=headers, params=params)
        if response.status_code != 200:
            print("Error fetching deals:", response.status_code, response.text)
            break

        data = response.json()
        for deal in data.get("results", []):
            # Get the deal's created date
            created_date = deal.get("properties", {}).get("createdate")
            if created_date:
                # Convert the ISO 8601 string to a datetime object
                created_datetime = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                # Check if the deal matches the type and is within the last 'days' days
                if deal.get("properties", {}).get("dealtype") == deal_type and created_datetime >= cutoff_date:
                    deals.append(deal)

        # Pagination handling
        after = data.get("paging", {}).get("next", {}).get("after")
        has_more = bool(after)

    return deals
owners_map = get_hubspot_owners()
##################################################################################################
DEAL_TYPE = "newbusiness"  # Internal ID for New Business
def get_deals_by_month(deal_type, start_date, end_date, owners_map=None):
    """
    Fetch all deals from HubSpot CRM with a specific deal type within a given date range.
    
    Args:
        deal_type (str): The type of deal to filter (e.g., "newbusiness").
        start_date (datetime): Start date of the range (inclusive).
        end_date (datetime): End date of the range (exclusive).
        owners_map (dict): Optional mapping of HubSpot owner IDs to owner names.

    Returns:
        list: A list of deals matching the criteria.
    """
    headers = {
        "Authorization": f"Bearer {API_KEY_DEALS}",
        "Content-Type": "application/json",
    }

    # Initialize variables for pagination
    deals = []
    has_more = True
    after = None

    while has_more:
        params = {
            "limit": 100,  # Number of records per page
            "properties": "dealtype,dealname,amount,createdate,hubspot_owner_id,deal_source_1,deal_source_2",
            "archived": "false",
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "createdate",
                            "operator": "GTE",
                            "value": f"{int(start_date.timestamp() * 1000)}"
                        },
                        {
                            "propertyName": "createdate",
                            "operator": "LTE",
                            "value": f"{int(end_date.timestamp() * 1000)}"
                        }
                    ]
                }
            ]
        }

        if after:
            params["after"] = after  # Add pagination token if available

        response = requests.get(DEALS_API_URL, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error fetching deals: {response.status_code} - {response.text}")
            break

        data = response.json()
        for deal in data.get("results", []):
            created_date = deal.get("properties", {}).get("createdate")
            deal_type_property = deal.get("properties", {}).get("dealtype")

            if created_date:
                try:
                    created_datetime = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                except ValueError:
                    continue

                # Normalize and compare deal type
                if (
                    deal_type_property and deal_type_property.strip().lower() == deal_type.strip().lower()
                    and start_date <= created_datetime < end_date
                ):
                    deals.append(deal)

        after = data.get("paging", {}).get("next", {}).get("after")
        has_more = bool(after)

    return deals


def get_month_date_range(year, month):
    """Get the start and end datetime of a given month."""
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    _, last_day = calendar.monthrange(year, month)
    end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start_date, end_date


# Current date details
now = datetime.now(timezone.utc)
current_year = now.year
current_month = now.month

# Current month range
start_current_month, end_current_month = get_month_date_range(current_year, current_month)
current_month_deals = get_deals_by_month(DEAL_TYPE, start_current_month, end_current_month, owners_map)

# Last month range
last_month = current_month - 1 if current_month > 1 else 12
last_month_year = current_year if current_month > 1 else current_year - 1
start_last_month, end_last_month = get_month_date_range(last_month_year, last_month)
last_month_deals = get_deals_by_month(DEAL_TYPE, start_last_month, end_last_month, owners_map)

# Two months back range
two_months_back = last_month - 1 if last_month > 1 else 12
two_months_back_year = last_month_year if last_month > 1 else last_month_year - 1
start_two_months_back, end_two_months_back = get_month_date_range(two_months_back_year, two_months_back)
two_months_back_deals = get_deals_by_month(DEAL_TYPE, start_two_months_back, end_two_months_back, owners_map)

##################################################################################################

# Fetch deals
deals = get_recent_deals_by_type(DEAL_TYPE, DAYS, owners_map)

def send_to_slack(blocks):
    """Send formatted blocks to a Slack channel."""
    payload = {
        "blocks": blocks
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload, headers=headers)
    if response.status_code != 200:
        print(f"Error sending message to Slack: {response.status_code} - {response.text}")

sorted_deals = sorted(deals, key=lambda deal: deal['properties'].get('createdate', 'N/A'), reverse=True)

def format_deals_for_slack(sorted_deals, owners_map, now, current_month_deals, last_month_deals, two_months_back_deals):
    """Format deals in a Slack-friendly text blob (code block)."""
    # Report date
    report_date = now.strftime("%d-%m-%Y")
    report_header = f"New deals report {report_date}\n-------------"
    summary = (
        f"Deals created last 7 days: {len(get_recent_deals_by_type(DEAL_TYPE, DAYS, owners_map))}\n"
        f"Deals created current month ({now.strftime('%B')}): {len(current_month_deals)}\n"
        f"Deals created last month ({calendar.month_name[last_month]}): {len(last_month_deals)}\n"
        f"Deals created two months back ({calendar.month_name[two_months_back]}): {len(two_months_back_deals)}\n"
    )

    # Initialize the text content with the header and summary
    text_content = report_header + "\n" + summary + "\n---\n"

    # Process deals into a single text blob
    for i, deal in enumerate(sorted_deals):
        deal_name = deal['properties'].get('dealname', 'N/A') or 'N/A'
        amount = deal['properties'].get('amount', 'N/A')
        owner_id = deal['properties'].get('hubspot_owner_id', 'N/A') or 'N/A'
        deal_owner = owners_map.get(owner_id, "Unknown Owner")
        deal_source_1 = deal['properties'].get('deal_source_1', 'N/A') or 'N/A'
        deal_source_2 = deal['properties'].get('deal_source_2', 'N/A') or 'N/A'
        created_date = deal['properties'].get('createdate', 'N/A') or 'N/A'

        # Format amount as a plain number
        if amount is None or amount == 'N/A':
            amount = 'N/A'
        else:
            try:
                amount = f"{float(amount):,.0f}"
            except (ValueError, TypeError):
                amount = 'N/A'

        # Format the created date
        created_date = created_date.split("T")[0] if "T" in created_date else created_date

        # Format the deal details
        deal_details = (
            f"Name: {deal_name}\n"
            f"Amount: {amount}\n"
            f"Deal Owner: {deal_owner}\n"
            f"Deal Source 1: {deal_source_1}\n"
            f"Deal Source 2: {deal_source_2}\n"
            f"Created Date: {created_date}\n"
        )

        # Add the deal details to the text content
        text_content += deal_details

        # Add a divider unless it's the last deal
        if i < len(sorted_deals) - 1:
            text_content += "---\n"

    # Wrap the entire content in triple backticks for a code block
    text_blob = f"```{text_content.strip()}```"

    # Return the Slack block with the entire blob
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text_blob
            }
        }
    ]

slack_blocks = format_deals_for_slack(sorted_deals, owners_map, now, current_month_deals, last_month_deals, two_months_back_deals)
send_to_slack(slack_blocks)
