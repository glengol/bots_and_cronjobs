import json
import logging

FREE_TIER = "FREE_TIER"
PREMIUM_TRIAL = "PREMIUM_TRIAL"
ENTERPRISE = "ENTERPRISE"
TEMPLATE_STATE = "./templates/state.json"
TEMPLATE_ACTIONS = "./templates/actions.json"
TEMPLATE_BUTTONS = "./templates/buttons.json"
TEMPLATE_BLOCK = "./templates/block.json"


def parse_account_name(text: str, num: int) -> str:
    """
    gets a string and returns the string to be queried in Retool
    :param text: The text of the message that was sent
    :param num: The number that represents which command should take place
    :return: The value to be queried in Retool
    """
    temp = ""
    for i in range(text.index("!" if num == 0 else "?") + 1, len(text)):
        # ignore blank lines
        if text[i] == " ":
            break
        temp += text[i]
    return temp


def get_options(arr: []) -> []:
    """
    gets all options and puts them in order
    :param arr: All the accounts that were returned from Retool
    :return: returns the "options" results within the desired slack block with the queried account included
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


def update_block(values: {}) -> json:
    """
    Creates the block that shows the details of a selected account
    :param values: The values of the account. Returned from a Retool API request
    :return: returns an updated action message JSON
    """
    with open(TEMPLATE_STATE, 'r+') as f:
        data = json.load(f)
        tier = values.get('tier_type')
        active = values.get('active')
        #  show active status
        data["blocks"][0]["text"]["text"] = f"Statistics for account: {values.get('name')}"
        data.get("blocks").append({"type": "context",
                                   "elements": [
                                       {"type": "plain_text",
                                        "text": f"Active: {':white_check_mark:' if values.get('active') else ':x:'}{str(values.get('active'))}"}]})
        # shows onboarding status
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
             "text": f"Onboarding Status: {':ballot_box_with_check:' if values.get('onboarding_status') == 'done' else ':x:'}{str(values.get('onboarding_status'))}"})
        # shows asset count
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
             "text": f"Assets: :chart_with_upwards_trend:{values.get('asset_number')}"})
        # shows asset count
        data["blocks"][1].get("elements").append({"type": "plain_text",
                                                  "text": f"License Age: :handshake:{values.get('license_age')}"})
        # shows last activity
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
             "text": f"Last Activity: :clock3:{values.get('last_activity')}"})
        # shows tier
        data["blocks"][1].get("elements").append(
            {"type": "plain_text",
             "text": f"Tier: {':hut:' if tier == FREE_TIER else ':house:' if tier == PREMIUM_TRIAL else ':office:'}{tier}{','}"})

        with open(TEMPLATE_ACTIONS, 'r+') as f1:
            data["blocks"].append(json.load(f1))
        with open(TEMPLATE_BUTTONS, 'r+') as f2:
            data["blocks"].append(json.load(f2))
    return data


def filter_function(index, name):
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
    dictionary = {":hut: FREE TIER :hut:": FREE_TIER, ":office: ENTERPRISE :office:": ENTERPRISE,
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

