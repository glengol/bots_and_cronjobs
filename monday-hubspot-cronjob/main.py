import requests
import json
import os

# ✅ Your monday.com API Key
MONDAY_API_KEY = os.environ.get("MONDAY_API_KEY")

# ✅ Board ID
BOARD_ID = os.environ.get("BOARD_ID")  

# ✅ GraphQL Query (Fetch Board Items with Pagination)
QUERY = {
    "query": f"""
    {{
      boards(ids: {BOARD_ID}) {{
        name
        items_page(limit: 500) {{  # Fetch first 500 rows
          items {{
            id
            name
            column_values {{
              id
              text
            }}
          }}
        }}
      }}
    }}
    """
}

# ✅ Headers for API Request
HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json"
}

# ✅ Send Request
response = requests.post("https://api.monday.com/v2", json=QUERY, headers=HEADERS)

# ✅ Parse and Save Response
if response.status_code == 200:
    data = response.json()

    # ✅ Extract Board Items
    board_info = data.get("data", {}).get("boards", [])[0]  # Get first board
    board_name = board_info.get("name", "N/A")
    items = board_info.get("items_page", {}).get("items", [])

    # ✅ List to store formatted RFE data
    rfe_list = []

    for item in items:
        feature_name = item["name"]
        creation_log = "N/A"
        customers = "N/A"
        status = "N/A"
        jira_link = "N/A"

        for column in item["column_values"]:
            if column["id"] == "creation_log__1" and column["text"]:
                creation_log = column["text"]
            elif column["id"] == "text5" and column["text"]:
                customers = column["text"]
            elif column["id"] == "status" and column["text"]:
                status = column["text"]
            elif column["id"] == "text4" and column["text"]:  # JIRA Link column
                jira_link = column["text"]

        # ✅ Split Customers field if multiple companies exist
        customer_list = [c.strip() for c in customers.split(",")]

        for customer in customer_list:
            rfe_entry = {
                "Feature": feature_name,
                "Customers": customer,  # ✅ Assign each company separately
                "Status": status,
                "JIRA Link": jira_link,
                "Creation Log": creation_log,
            }

            # ✅ Append to list
            rfe_list.append(rfe_entry)

    # ✅ Save to JSON file
    json_filename = "rfes_output.json"
    with open(json_filename, "w") as f:
        json.dump(rfe_list, f, indent=4)

    print(f"✅ Data successfully saved to {json_filename}")

else:
    print(f"❌ Error fetching data: {response.status_code}\n{response.text}")
