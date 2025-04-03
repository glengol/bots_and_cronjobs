import requests
from requests.auth import HTTPBasicAuth
import json
import os

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL")
PROJECT_KEY = "SUPPORT"
USERNAME = os.environ.get("USERNAME")
API_TOKEN = os.environ.get("API_TOKEN")

# Only keep essential fields
def simplify_issue(issue):
    fields = issue["fields"]
    return {
        "key": issue["key"],
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "customer": fields.get("customfield_10029"),
        "escalation_type": fields.get("customfield_10088", {}).get("value"),
        "created": fields.get("created"),
        "priority": fields.get("priority", {}).get("name")
    }

def fetch_issues():
    url = f"{JIRA_BASE_URL}/rest/api/3/search"
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)

    query = {
        "jql": f"project={PROJECT_KEY}",
        "fields": "summary,status,customfield_10029,customfield_10088,created,priority",
        "maxResults": 100,
        "startAt": 0
    }

    all_issues = []

    while True:
        res = requests.get(url, headers=headers, params=query, auth=auth)
        if res.status_code != 200:
            print("Error:", res.status_code, res.text)
            return

        data = res.json()
        issues = data.get("issues", [])

        for issue in issues:
            simplified = simplify_issue(issue)
            # 🚫 Skip "✓ & Communicated" or internal dogfood tickets
            if simplified["status"] == "\u2705 & Communicated":
                continue
            if simplified["customer"] == "Firefly (dog-food)":
                continue
            all_issues.append(simplified)

        if len(issues) < query["maxResults"]:
            break
        query["startAt"] += query["maxResults"]

    with open("simplified_support_tickets.json", "w") as f:
        json.dump(all_issues, f, indent=2)

    print(f"✅ Saved {len(all_issues)} filtered issues to simplified_support_tickets.json")

fetch_issues()
