# main.py uses functions from here
import json
import requests
import logging
from config import Vars
from typing import List, Dict
from datetime import datetime, timedelta, timezone


ENTERPRISE = "ENTERPRISE"
PREMIUM_TRIAL = "PREMIUM_TRIAL"

PATH_TO_LOCAL_PROJECT="."

TEMPLATE_STATE = PATH_TO_LOCAL_PROJECT + "/templates/state.json"
TEMPLATE_ACTIONS = PATH_TO_LOCAL_PROJECT + "/templates/actions.json"
TEMPLATE_BUTTONS = PATH_TO_LOCAL_PROJECT + "/templates/buttons.json"
TEMPLATE_BLOCK = PATH_TO_LOCAL_PROJECT + "/templates/block.json"
TEMPLATE_TEL_BLOCK = PATH_TO_LOCAL_PROJECT + "/templates/tel_block.json"



variables = Vars()
##########################################################################################################
def get_hubspot_owners():
    """Fetch all HubSpot owners to map owner IDs to names."""
    headers = {
        "Authorization": f"Bearer {variables.api_key_deals}",
        "Content-Type": "application/json",
    }
#    print(f"Raw API Key: {repr(variables.api_key_deals)}")
#    print(variables.owners_api_url)

    response = requests.get(variables.owners_api_url, headers=headers)
    if response.status_code != 200:
        print("Error fetching owners:", response.status_code, response.text)
        return {}

    owners = response.json().get("results", [])
    return {owner["id"]: owner["firstName"] + " " + owner["lastName"] for owner in owners if "firstName" in owner and "lastName" in owner}

def get_recent_deals_by_type(deal_type, days=7, owners_map=None):
    """Fetch all deals from HubSpot CRM with a specific deal type and created in the last 'days' days."""
    headers = {
        "Authorization": f"Bearer {variables.api_key_deals}",
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

        response = requests.get(variables.deals_api_url, headers=headers, params=params)
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

# Deal type to filter
DEAL_TYPE = "newbusiness"  # Internal ID for New Business
DAYS = 7  # Last 7 days

# Fetch deals
deals = get_recent_deals_by_type(DEAL_TYPE, DAYS, owners_map)
deals_30 = get_recent_deals_by_type(DEAL_TYPE, 30,owners_map )
##########################################################################################################

# Generate a Management API token
def get_management_token() -> str:
    """
    Get the management token from Auth0.
    """
    url = f'https://{variables.auth0_doamin}/oauth/token'
    payload = {
        'grant_type': 'client_credentials',
        'client_id': variables.client_id,
        'client_secret': variables.client_secret,
        'audience': f'https://{variables.auth0_doamin}/api/v2/'
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()['access_token']

def get_filtered_users(token: str) -> List[Dict]:
    """
    Retrieve all users from Auth0 that have an 'originalAccountId' in their metadata.
    """
    url = f'https://{variables.auth0_doamin}/api/v2/users'
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'q': 'app_metadata.originalAccountId:*',  # Query for users with originalAccountId
        'search_engine': 'v3',  # Use the Lucene search engine
        'page': 0,
        'per_page': 50  # Adjust page size as needed
    }
    users = []
    while True:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        users.extend(data)
        params['page'] += 1
    return users

def filter_last_seven_days(users: List[Dict]) -> List[Dict]:
    """
    Filter users created within the last 7 days.
    """
    last_seven_days = []
    current_date = datetime.now(timezone.utc)
    seven_days_ago = current_date - timedelta(days=7)

    for user in users:
        created_at = datetime.strptime(user['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        if created_at >= seven_days_ago:
            last_seven_days.append(user)
#            print(last_seven_days)######################################
#    print(last_seven_days)
    return last_seven_days


def get_users_created_in_last_seven_days() -> List[Dict]:
    """
    Retrieves users created in the last 7 days by calling the Auth0 API.
    """
    try:
        token = get_management_token()
#        print("Token generated successfully")
        users = get_filtered_users(token)
#        print(f"Retrieved {len(users)} users.")
        last_seven_days = filter_last_seven_days(users)
#        print(f"Users created in the last 7 days: {len(last_seven_days)}")
        return last_seven_days
    except requests.exceptions.RequestException as e:
#        print("Error fetching users:", e)
        return []


def parse_user_info(users: List[Dict]) -> List[Dict]:
    """
    Parses user information to include account_name from metadata.
    """
    parsed_users = []
    for user in users:
        account_name = user.get('app_metadata', {}).get('account_name', 'N/A')
        parsed_users.append({
            'user_id': user['user_id'],
            'account_name': account_name
        })
#    print(parsed_users)####################
    return parsed_users

def get_options_from_auth0(users: List[Dict]) -> List[Dict]:
    """
    Convert user data from Auth0 into Slack options format.
    """
    options = []
    for i, user in enumerate(users):
        options.append({
            'text': {'type': 'plain_text', 'text': user.get('email', 'No Email')},
            'value': f"value-{i}"  # Generic value format like "value-0", "value-1", etc.
        })
    return options

'''def count_unique_account_names(data):
    # Extract "account_name" values
    account_names = [item['account_name'] for item in data if 'account_name' in item]
    
    # Count unique account names
    unique_count = len(set(account_names))
    print(unique_count)
    return unique_count
'''
def count_unique_account_names() -> List[Dict]:
    """
    Retrieves users created in the last 7 days by calling the Auth0 API.
    """
    
    token = get_management_token()
    users = get_filtered_users(token)
    last_seven_days = filter_last_seven_days(users)
    last_seven_days = len(last_seven_days)
#    print(last_seven_days)
    return last_seven_days

##############################################################################################

def fetch_sandbox_last_7_days() -> List[Dict]:
    """
    Fetches sandbox details for the last 7 days.
    Replace this with actual data-fetching logic.
    """
    return [
        {"name": "John Doe", "email": "john.doe@example.com", "app_metadata": {"account_name": "Account A"}, "created_at": "2024-11-21"},
        {"name": "Jane Smith", "email": "jane.smith@example.com", "app_metadata": {"account_name": "Account B"}, "created_at": "2024-11-20"}
    ]

def post_table_to_slack(channel_id: str, table: str):
    """
    Posts a formatted table to a Slack channel.
    """
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {variables.slack_bot_token}"}
    payload = {
        "channel": channel_id,
        "text": table
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()



##############################################################################################
def parse_account_name(text: str, num: int) -> str:
    """
    gets a string and returns the string to be queried in Retool
    :param text: The text of the message that was sent
    :param num: The number that represents which command should take place
    :return: The value to be queried in Retool

    example:
    text = "Hello!world example", num = 0 - will be returned "world"
    """
    temp = ""
    for i in range(text.index("!" if num == 0 else "?") + 1, len(text)):
        # ignore blank lines
        if text[i] == " ":
            break
        temp += text[i]
    return temp

def get_options(arr: []) -> []:
#    print("get_options called with arr:", arr)

    """
    gets all options and puts them in order
    :param arr: All the accounts that were returned from Retool
    :return: returns the "options" results within the desired slack block with the queried account included

    Sapir: options = account results
        example:
        arr = [
        ["acc123", "Google"],
        ["acc456", "Microsoft"],
        ["acc789", "Apple"]
        ]

        it will return:
        [
        {'text': {'type': 'plain_text', 'text': 'Google'}, 'value': 'value-0'},
        {'text': {'type': 'plain_text', 'text': 'Microsoft'}, 'value': 'value-1'},
        {'text': {'type': 'plain_text', 'text': 'Apple'}, 'value': 'value-2'}
        ]

    """
    results = []
    try:
        for i in range(0, len(arr)):
            curr_val = f"value-{i}"
            results.append({'text': {'type': 'plain_text', 'text': arr[i][1]},
                            'value': curr_val})
    except TypeError as e:
        logging.error(f"Failed in get_options() - {e} - Args: {arr}")
        return

    return results


def make_block(arr: [], name: str) -> json:
    """
    creates the Slack text block that will be posted after configuration is complete
    :param arr: All the accounts that were returned from Retool
    :param name: The value that was queried to Retool
    :return: returns a json Slack block that will be sent to Slack
    """
    with open(TEMPLATE_BLOCK, 'r+') as f:
        data = json.load(f)
        options = get_options(arr)
        if len(options) == 0:
            return {}
        data['blocks'][0]['text']['text'] = f"*SELECTED VALUE:* *{name}*"
        data['blocks'][2]['accessory']['options'] = options
        return data

def adjusted_count(arr):
    if not arr or not isinstance(arr[0], (list, str)):  # Check if arr is not empty and arr[0] is list or string
        return 0  # Return 0 if the structure is not as expected
    return 0 if arr[0][0] == '-' else len(arr)

def make_tel_block(
    arr_7_days: [], 
    arr_about_end: [], 
    arr_in_progress: [], 
    arr_sandbox_last_7_days: []
) -> json:
    """
    Creates the Slack text block that will be posted after configuration is complete.
    This includes sections for 'Started in the last 7 days', 'About to end', 
    'In progress', and 'Sandbox last 7 days'.
    :param arr_7_days: All the trials that were returned from Retool (for 7 days).
    :param arr_about_end: Trials that are about to end.
    :param arr_in_progress: Trials that are currently in progress.
    :param arr_sandbox_last_7_days: Users from Auth0 who accessed the sandbox in the last 7 days.
    :return: Returns a JSON Slack block that will be sent to Slack.
    """
#    print("Received in make_tel_block - arr_7_days:", arr_7_days)
#    print("Received in make_tel_block - arr_about_end:", arr_about_end)
#    print("Received in make_tel_block - arr_in_progress:", arr_in_progress)
#    print("Received in make_tel_block - arr_sandbox_last_7_days:", arr_sandbox_last_7_days)
    with open(TEMPLATE_TEL_BLOCK, 'r+') as f:
        data = json.load(f)
#        print(f"Blocks structure: {data['blocks']}")

        # Get options for each section from the arrays passed in
        options_7_days = get_options(arr_7_days) 
        options_about_end = get_options(arr_about_end)
        options_in_progress = get_options(arr_in_progress)
        options_sandbox_last_7_days = get_options_from_auth0(arr_sandbox_last_7_days)
#        print(f"arr_7_days: {options_7_days}")
#        print(f"arr_about_end: {options_about_end}")
#        print(f"arr_in_progress: {arr_in_progress}")
#        print(f"arr_sandbox_last_7_days: {arr_sandbox_last_7_days}")
#        print("Options for sandbox last 7 days:", options_sandbox_last_7_days)
#        print("Options in progress:", options_in_progress)
        if isinstance(arr_sandbox_last_7_days, dict):
            arr_sandbox_last_7_days = list(arr_sandbox_last_7_days.values()) 

        # If any of the options are empty, return an empty response
        if not options_7_days or not options_about_end or not options_in_progress or not options_sandbox_last_7_days:
            return {}

        # Get counts for each section
        count_7_days = adjusted_count(arr_7_days)
        count_about_end = adjusted_count(arr_about_end)
        count_in_progress = adjusted_count(arr_in_progress)
        count_sandbox_last_7_days = count_unique_account_names()
        count_deals = len(deals)
        count_deals_30 = (len(deals_30))
#        print(count_sandbox_last_7_days)
        # Update the 'Started in the last 7 days' section
        data['blocks'][2]['text']['text'] = f"*Started in the last 7 days:* *{count_7_days}*"
        data['blocks'][2]['accessory']['options'] = options_7_days

        # Update the 'About to end' section
        data['blocks'][3]['text']['text'] = f"*About to end:* *{count_about_end}*"
        data['blocks'][3]['accessory']['options'] = options_about_end

        # Update the 'In progress' section
        data['blocks'][4]['text']['text'] = f"*In progress:* *{count_in_progress}*"
        data['blocks'][4]['accessory']['options'] = options_in_progress

        # Update the 'Sandbox last 7 days' section
        data['blocks'][7] = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Sandbox last 7 days:* *{count_sandbox_last_7_days}*"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Details"},
                "action_id": "view_sandbox_details"
            }
        }
        
        data['blocks'][10] = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*New deals last 7 days:* *{count_deals}*"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Details"},
                "action_id": "view_deals_details"
            }
        }
        data['blocks'][12] = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*New deals this month:* *{count_deals_30}*"},
        }

        return data


def update_block(values: {}) -> json:
    """
    Creates the block that shows the details of a selected account
    :param values: The values of the account. Returned from a Retool API request
    :return: returns an updated action message JSON
    """
    with open(TEMPLATE_STATE, 'r+') as f: #opens the file in read+write mode
        data = json.load(f)
        tier = values.get('tier_type')
        active = values.get('active')
        #  show active status
        data["blocks"][0]["text"]["text"] = f"Statistics for account: {values.get('name')}"
        data.get("blocks").append(
            {"type": "context",
            "elements": [
                {"type": "plain_text",
                "text": f"Active: {str(values.get('active'))}{' :white_check_mark:' if values.get('active') else ' :x:'}"}
            ]}
        )
        # shows onboarding status
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": (
                f"Onboarding Status: {str(values.get('onboarding_status'))}"
                f"{' :ballot_box_with_check:' if values.get('onboarding_status') == 'done' else ' :x:'}"
            )}
        )

        # shows asset count
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": f"Assets: {values.get('asset_number')} :chart_with_upwards_trend:"}
        )
        # shows asset count
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": f"License Age: {values.get('license_age')} :handshake:"}
        )

        # Shows last activity
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": f"Last Activity: {values.get('last_activity')} :clock3:"}
        )
        # Shows total savings
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": f"Total Savings: {values.get('total_savings')} :moneybag:"}
        )
        # Shows tier
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": f"Tier: {tier} {':house:' if tier == 'PREMIUM_TRIAL' else ':office:'}"}
        )

        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
            "text": (
                " IaC Status: :o:\n"
                f"Codified: {values.get('codified')}\n"
                f"Drift: {values.get('drift')}\n"
                f"Unmanaged: {values.get('unmanaged')}"
            )
            }
        )


        # data["blocks"][1].get("elements").append(
        #     {"type": "plain_text",
        #      "text": f"\n':o:' IaC Status:\n"})
        # data["blocks"][1].get("elements").append(
        #     {"type": "plain_text",
        #      "text": f"Codified: {values.get('codified')}"})
        # data["blocks"][1].get("elements").append(
        #     {"type": "plain_text",
        #      "text": f"Drift: {values.get('drift')}"})
        # data["blocks"][1].get("elements").append(
        #     {"type": "plain_text",
        #      "text": f"Unmanaged: {values.get('unmanaged')}"})
        with open(TEMPLATE_ACTIONS, 'r+') as f1:
            data["blocks"].append(json.load(f1))
        with open(TEMPLATE_BUTTONS, 'r+') as f2:
            data["blocks"].append(json.load(f2))
    return data

def filter_function(index, name): #Unnecessery function
    if index[1] == name:
        return index[0]
    return ""

def get_id(data: [], name: str) -> str:
    """
    Gets the Id of the selected account from the accounts list
    :param data: The accounts list
    :param name: The name of the account
    :return: returns the id of a specific name
    """
    for i in range(0, len(data['results'])):
        if name == data['results'][i][1]:
            return data['results'][i][0]
    return ""

def get_tier(slack_formatted_tier: str) -> str:
    """
    :param slack_formatted_tier: The tier's name with emojis , to be parsed
    :return: returns parsed tier name (contains only the name)
    """
    dictionary = {":office: ENTERPRISE :office:": ENTERPRISE,
                  ":house: PREMIUM TRIAL :house:": PREMIUM_TRIAL}
    return dictionary.get(slack_formatted_tier)

def add_user_info(user_list: {}, user: str, timestamp: str, request: json, message: json):
    """
    Adds crucial parameters to a user.
    :param user_list: The dictionary of the users.
    :param user: The Id of the user
    :param timestamp: The timestamp of the first message that the user received from the bot
    :param request: A json that was returned from Retool. Contains all accounts that were returned from the query
    :param message: The message that was sent in the Slack channel
    """
    # adds the slack information dictionary to the general information dictionary
    user_list[user] = {"Timestamp": timestamp, "Request": request, "Account": "", "Action": "", "Prev": "", "Message": message}

def update(user_list: {}, user: str, subdir: str, val: str):
    """
    Updates a value in a subdirectory in user_list
    :param user_list: The dictionary of the users.
    :param user: The Id of the user
    :param subdir: The subdirectory to be accessed in user_list. val will be written into it
    :param val: the value to be written into the provided subdirectory
    """
    user_list.get(user, {})[subdir] = val

def get_item(user_list: {}, user: str, subdir: str) -> str:
    """
    :param user_list: The dictionary of the users.
    :param user: The Id of the user
    :param subdir: The subdirectory to be accessed in user_list. val will be written into it
    :return: The item that is inside the 'subdir' directory of the dictionary
    """
    return user_list.get(user, {}).get(subdir)

def remove(user_list: {}, user: str):
    """
    Removes information from the user. Used upon configuration abortion
    :param user_list: The dictionary of the users.
    :param user: The Id of the user
    """
    user_list[user] = ""

def make_admin_list(s: str) -> {}:
    """
    Get a string of users and makes a dictionary out of it
    :param s: The string to be transformed into a dictionary
    :return: A dictionary of the bot's users
    """
    dictionary = dict((user.strip(), value.strip())
                      for user, value in (element.split(':')
                                          for element in s.split(', ')))
    return dictionary