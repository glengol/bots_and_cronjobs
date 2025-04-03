import requests
import json
import time
import os

# ✅ HubSpot API Key (Private App Access Token)
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY")

# ✅ Path to JSON File
JSON_FILE_PATH = "simplified_support_tickets.json"  # Your saved support file

# ✅ HubSpot API Endpoints
SEARCH_COMPANY_URL = "https://api.hubapi.com/crm/v3/objects/companies/search"
UPDATE_COMPANY_URL = "https://api.hubapi.com/crm/v3/objects/companies/{company_id}"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
    "Content-Type": "application/json"
}

def get_company_id(company_name):
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "name",
                "operator": "EQ",
                "value": company_name
            }]
        }]
    }

    res = requests.post(SEARCH_COMPANY_URL, headers=HEADERS, json=payload)
    if res.status_code == 200:
        results = res.json().get("results", [])
        if results:
            return results[0]["id"]

    with open("missing_companies.log", "a") as log_file:
        log_file.write(f"Company not found: {company_name}\n")
    print(f"❌ Company not found: {company_name}")
    return None

def get_current_support(company_id):
    """Fetches the current Jira support data from HubSpot for a given company."""
    url = UPDATE_COMPANY_URL.format(company_id=company_id)
    res = requests.get(url, headers=HEADERS, params={"properties": "jira_support_tickets"})

    if res.status_code == 200:
        current_value = res.json().get("properties", {}).get("jira_support_tickets")
        if current_value is None:
            return ""
        return current_value.strip()

    print(f"❌ Failed to fetch current support for Company ID {company_id}. Status: {res.status_code}")
    return None


def push_support_to_hubspot(company_id, support_data):
    formatted = [
        f"Key: {t['key']}\nSummary: {t['summary']}\nStatus: {t['status']}\nPriority: {t['priority']}\nEscalation Type: {t['escalation_type']}\nCreated: {t['created']}"
        for t in support_data
    ]


    if not formatted:
        print(f"🚫 No tickets to update for Company ID {company_id}")
        return

    combined_text = "\n\n".join(formatted).strip()
    current = get_current_support(company_id)

    if current == combined_text:
        print(f"🔄 No changes for Company ID {company_id}, skipping update.")
        return

    payload = {
        "properties": {
            "jira_support_tickets": combined_text
        }
    }

    update_url = UPDATE_COMPANY_URL.format(company_id=company_id)
    res = requests.patch(update_url, headers=HEADERS, json=payload)

    if res.status_code == 200:
        print(f"✅ Jira support tickets updated for Company ID {company_id}")
    else:
        print(f"❌ Failed to update Company ID {company_id}")
        print(res.text)


# ✅ Load support data and group by customer
with open(JSON_FILE_PATH, "r") as f:
    support_list = json.load(f)

grouped_data = {}
for ticket in support_list:
    customer = ticket["customer"]
    if not customer:
        continue
    grouped_data.setdefault(customer, []).append(ticket)

for company_name, tickets in grouped_data.items():
    company_id = get_company_id(company_name)
    if company_id:
        push_support_to_hubspot(company_id, tickets)
    time.sleep(1)  # Respect HubSpot API rate limits

print("✅ Jira Support sync complete!")
