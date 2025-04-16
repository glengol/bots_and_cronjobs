import requests
import json
import time
import os

# ✅ HubSpot API Key (Private App Access Token)
HUBSPOT_API_KEY = os.environ.get("HUBSPOT_API_KEY")  

# ✅ Path to JSON File
JSON_FILE_PATH = "rfes_output.json"  # Change this to your actual file path

# ✅ HubSpot API Endpoints
SEARCH_COMPANY_URL = "https://api.hubapi.com/crm/v3/objects/companies/search"
UPDATE_COMPANY_URL = "https://api.hubapi.com/crm/v3/objects/companies/{company_id}"

# ✅ Headers for API Calls
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
    "Content-Type": "application/json"
}

# ✅ Function to Find Company ID in HubSpot
def get_company_id(company_name):
    search_payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "name",
                        "operator": "EQ",
                        "value": company_name
                    }
                ]
            }
        ]
    }

    response = requests.post(SEARCH_COMPANY_URL, headers=HEADERS, json=search_payload)

    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]["id"]  # ✅ Return first matching Company ID

    # ❌ Log missing companies
    with open("missing_companies.log", "a") as log_file:
        log_file.write(f"Company not found: {company_name}\n")

    print(f"❌ Company not found: {company_name} (Logged in missing_companies.log)")
    return None


# ✅ Function to Get Current RFE Data from HubSpot
def get_current_rfe(company_id):
    fetch_url = UPDATE_COMPANY_URL.format(company_id=company_id)
    response = requests.get(fetch_url, headers=HEADERS, params={"properties": "rfe_customer_feature_requests"})

    if response.status_code == 200:
        current_rfe = response.json().get("properties", {}).get("rfe_customer_feature_requests")
        if current_rfe is not None:
            return current_rfe.strip()
        return ""
    else:
        print(f"❌ Failed to fetch current RFE for Company ID {company_id}. Status: {response.status_code}")
        return ""


# ✅ Function to Overwrite RFE in HubSpot **Only If Data Changes**
def push_rfe_to_hubspot(company_id, rfe_data):
    """Pushes updated RFE data to HubSpot only if it has changed."""
    
    # ✅ Combine all RFEs into a single text block, excluding "Delivered and Communicated"
    filtered_rfes = [
        f"Feature: {rfe['Feature']}\nCustomers: {rfe['Customers']}\nStatus: {rfe['Status']}\nJIRA Link: {rfe['JIRA Link']}\nCreation Log: {rfe['Creation Log']}"
        for rfe in rfe_data if rfe['Status'] != "Delivered and Communicated"
    ]

    # ✅ If no RFEs remain after filtering, do nothing
    if not filtered_rfes:
        print(f"🚫 No valid RFEs to update for Company ID {company_id}")
        return

    rfe_text = "\n\n".join(filtered_rfes).strip()

    # ✅ Fetch existing RFE from HubSpot
    current_rfe = get_current_rfe(company_id)

    # ✅ Compare the new RFE text with the existing one
    if current_rfe == rfe_text:
        print(f"🔄 No changes detected for Company ID {company_id}, skipping update.")
        return  # ✅ Skip update if the text is the same

    update_payload = {
        "properties": {
            "rfe_customer_feature_requests": rfe_text
        }
    }

    update_url = UPDATE_COMPANY_URL.format(company_id=company_id)

    # ✅ Perform the update **only if necessary**
    update_response = requests.patch(update_url, headers=HEADERS, json=update_payload)

    if update_response.status_code == 200:
        print(f"✅ RFE successfully updated for Company ID {company_id}")
    else:
        print(f"❌ Failed to update RFE for Company ID {company_id}. Status: {update_response.status_code}")
        print(update_response.text)



# ✅ Load RFE Data from JSON File
with open(JSON_FILE_PATH, "r") as file:
    rfe_list = json.load(file)

# ✅ Process Each RFE Entry
company_rfe_data = {}  # Store RFEs grouped by company

for rfe in rfe_list:
    # ✅ Skip RFEs with "Delivered and Communicated" status
    if rfe["Status"] == "Delivered and Communicated":
        continue

    company_name = rfe["Customers"]
    
    if company_name not in company_rfe_data:
        company_rfe_data[company_name] = []
    
    company_rfe_data[company_name].append(rfe)

# ✅ Loop through each company and update RFE
for company_name, rfe_data in company_rfe_data.items():
    company_id = get_company_id(company_name)

    if company_id:
        push_rfe_to_hubspot(company_id, rfe_data)
    
    # ✅ Rate limiting (optional)
    time.sleep(1)  # Prevents API throttling

print("🚀 Test Completed!")
