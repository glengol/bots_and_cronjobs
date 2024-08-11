import os
import signal
from pydantic import Field
from slack_sdk import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from time import time
from slack_sdk.errors import SlackApiError
import utility
import requests
import config
import logging
from pythonjsonlogger import jsonlogger


formatter = jsonlogger.JsonFormatter("%(asctime)s - %(message)s")
json_handler = logging.StreamHandler()
json_handler.setFormatter(formatter)
logger = logging.getLogger('my_json')
logger.setLevel(logging.INFO)
logger.addHandler(json_handler)

variables = config.Vars()
key = variables.key
app_token = variables.app_token
# creates an app client
app = App(token=key)
# parse the account name to use an action on
client = WebClient(token=key)
admin_list = utility.make_admin_list(variables.admin_list_var)
# list of users who have a running configuration
active_list = []

def kill_server(message: {}):
    logger.info(f"Trigger self destruct funcion kill_server by user {app.client.users_info(user=message.get('user')).get('user').get('name')}")    
    os._exit(0)

@app.action("abort_action")
def abort_action(user_id: str, channel_id: str, say, ack):
    """
    Aborts an action
    :param user_id: Id of the action initiator
    :param channel_id: The channel the action was initiated in
    :param say: Specifying the use of the Slack function say()
    :param ack: Sending acknowledgement to Slack
    :exception: If failed to delete messages , raises an exception
    """
    username = app.client.users_info(user=user_id).get('user').get('real_name')
    ack()
    if admin_list[user_id] == "":
        say("You don't have any active sessions.")
        return
    say("Aborting...")
    # delete accounts message
    try:
        app.client.chat_delete(token=key, channel=channel_id, ts=utility.get_item(admin_list, user_id, "Timestamp"))
    except SlackApiError as e:
        logger.error(
            f"failed in function abort_action() for user {app.client.users_info(user=user_id).get('user').get('name')}",
            extra={"user_id": user_id,
                   "text": e,
                   "level": "ERROR"})
        return

    # removes user from active list
    active_list.remove(user_id)
    if utility.get_item(admin_list, user_id, "Prev") != "":  # delete leftover messages
        try:
            app.client.chat_delete(token=key, channel=channel_id, ts=utility.get_item(admin_list, user_id, "Prev"))
        except SlackApiError as e:
            logger.error(
                f"failed in function abort_action() for user {app.client.users_info(user=user_id).get('user').get('name')}",
                extra={"user_id": user_id,
                       "text": e,
                       "level": "ERROR"})
            return
    logger.info(
        f"Exited successfully from function abort_action() for user {username}",
        extra={"user_id": user_id,
               "level": "INFO"})

    utility.remove(admin_list, user_id)  # removes value from admin list
    say("You have successfully aborted the session.\nTo start a new session, please type: start")

@app.action("select_account")
def select_account(action: {}, ack, say, user_id: str, channel_id: str):
    """
    Handles the user picking an account to execute an action on and sends information about it
    :param action: Information about the action that happened due to user input
    :param ack: Sending acknowledgement to Slack
    :param say: Specifying the use of the Slack function say()
    :param user_id: Id of the action initiator
    :param channel_id: Id of the channel action occurred in
    :exception: If message could not be delete , raise exception
    """
    ack()
    utility.update(admin_list, user_id, "Account", action.get("selected_option", {}).get("text", {}).get("text"))
    #  edit message according to input
    request = requests.get(variables.change_status,
                           data={"name": utility.get_item(admin_list, user_id, "Account")}).json()
    # if an action message was not created
    if utility.get_item(admin_list, user_id, "Prev") == "":
        say(utility.update_block(request))  # send message to slack
        # save timestamp of message for future use
        try:
            utility.update(admin_list, user_id, "Prev", client.conversations_history(channel=channel_id,
                                                                                     inclusive=True,
                                                                                     latest=str(time()),
                                                                                     limit=1)["messages"][0].get('ts'))
        except SlackApiError as e:
            logger.error(
                f"failed in function select_account() for user {app.client.users_info(user=user_id).get('user').get('name')}",
                extra={"user_id": user_id,
                       "text": e,
                       "level": "ERROR"})
            return

    # if an action message was previously deleted
    else:
        app.client.chat_delete(token=key, channel=channel_id, ts=utility.get_item(admin_list, user_id, "Prev"))
        # send message to slack
        say(utility.update_block(request))
        # save timestamp of message for future use
        try:
            utility.update(admin_list, user_id, "Prev", client.conversations_history(channel=channel_id,
                                                                                     inclusive=True,
                                                                                     latest=str(time()),
                                                                                     limit=1)["messages"][0].get('ts'))
        except SlackApiError as e:
            logger.error(
                f"failed in function select_account() for user {app.client.users_info(user=user_id).get('user').get('name')}",
                extra={"user_id": user_id,
                       "text": e,
                       "level": "ERROR"})
            return
    logger.info(
        f"Function select_account() successfully finished for user {app.client.users_info(user=user_id).get('user').get('name')}",
        extra={"user_id": user_id,
               "text": action.get("selected_option", {}).get("text", {}).get("text"),
               "level": "INFO"})

@app.action("select_action")
def select_action(action: {}, ack, user_id: str):
    """
    Handles the user selecting the action they wish to perform
    :param action: Information about the action that happened due to user input
    :param ack: Sending acknowledgement to Slack
    :param user_id: Id of the action initiator
    """
    utility.update(admin_list, user_id, "Action", action.get("selected_option", {}).get("text", {}).get("text"))
    ack()
    logger.info(
        f"Function select_action() successfully finished for user {app.client.users_info(user=user_id).get('user').get('name')}",
        extra={"user_id": user_id,
               "text": utility.get_item(admin_list, user_id, 'Action'),
               "level": "INFO"})

@app.action("execute_action")
def execute_action(user_id: str, say, ack):
    """
    Executes the picked action
    :param user_id: Id of the action initiator
    :param say: Specifying the use of the Slack function say()
    :param ack: Sending acknowledgement to Slack
    """
    ack()
    name = utility.get_item(admin_list, user_id, "Account")
    data = requests.get(variables.get_id,
                            data={"id": "",
                                  "name": client.users_info(user=user_id).get("user", {}).get("real_name"),
                                  "url": name})
    response_data = data.json()
    if utility.get_item(admin_list, user_id, "Action") == "" or utility.get_item(admin_list, user_id,
                                                                                 "Account") == "":  # makes sure both fields are selected
        say(f"<@{user_id}> Please make sure that you've selected an account and action!")
    
    # execute suspend / activate / extend poc function
    elif utility.get_item(admin_list, user_id, "Action") == ":x: Suspend :x:" or \
            utility.get_item(admin_list, user_id, "Action") == ":white_check_mark: Activate :white_check_mark:":

        status = "false" if utility.get_item(admin_list, user_id, "Action") == ":x: Suspend :x:" else "true"

        #  makes an API request to Retool to suspend / activate
        requests.get(variables.suspend_activate,
                     data={"id": response_data['id'],
                           "user": response_data['name'],
                           "name": response_data['url'],
                            "status": status})
        # send confirmation message that the action successfully finished
        say(f"Account successfully {'suspended' if status == 'false' else 'activated'}. Please check "
            f"#account-mgmt-audit for more details")

    # execute extend POC 7 days
    elif utility.get_item(admin_list, user_id,
                          "Action") == ":hourglass_flowing_sand: Extend POC +7 days :hourglass_flowing_sand:":
        requests.get(
            variables.extend_poc_7_days,
            data={"id": response_data['id'],
                  "name": response_data['name'],
                  "url": response_data['url']})
        # send confirmation message that the action successfully finished
        say(f"Account successfully extended POC +7 days. Please check #account-mgmt-audit for more details")
    
    # execute extend POC 2 days
    elif utility.get_item(admin_list, user_id,
                          "Action") == ":hourglass_flowing_sand: Extend POC +2 days :hourglass_flowing_sand:":
        requests.get(
            variables.extend_poc_2_days,
            data={"id": response_data['id'],
                  "name": response_data['name'],
                  "url": response_data['url']})
        # send confirmation message that the action successfully finished
        say(f"Account successfully extended POC +2 days. Please check #account-mgmt-audit for more details")
        # if user is going to change account tier
    else:
        requests.get(variables.change_tier,
                     data={"id": response_data['id'],
                           "status": utility.get_tier(utility.get_item(admin_list, user_id, "Action")),
                           "name": response_data['name'],
                           "url": response_data['url']})
        # send confirmation message that the action successfully finished
        say(f"Account successfully changed to {utility.get_tier(utility.get_item(admin_list, user_id, 'Action'))}. Please check"
            f" #account-mgmt-audit for more details")
    logger.info(
        f"Exited successfully from function execute_action() for user {app.client.users_info(user=user_id).get('user').get('name')}",
        extra={"user_id": user_id,
               "level": "INFO"})

@app.event("reaction_added")
def handle_reaction_added_events(ack):
    """
    Handles reaction usage
    :param ack: Sending acknowledgement to Slack
    """
    ack()

def account_search_result(message: {} ,account, say, num: int):

    response = requests.get(variables.return_account,
                            data={'accountName': account, "num": num})
    request = response.json()
    m = utility.make_block(request.get('results'), account)
    if m == {}:  # if no results were returned
        say("No search results found , please try again")
        return
    say(m)

@app.action("account_search")
def handle_some_action(message: {}, ack, body, logger, say):
    ack()
    global account
    account = body['actions'][0]['value'].lower()
    account_search_result(message, account, say, 0)

def main_menu(message: {}, say, num: int):

    # adds user to list of users that have active configurations
    if message.get('user') in active_list:
        say(f"<@{message.get('user')}> Your current session is active. To start a new session, click on the END "
            f"SESSION button or type ‘end’")
        return
    
    # makes an API request to Retool that returns trial_started_last_7_days
    response_7_days = requests.get(variables.trial_started_last_7_days)
    response_about_end = requests.get(variables.trial_about_end)
    response_in_progress = requests.get(variables.trial_in_progress)
    # parse it into json
    request_7_days = response_7_days.json()
    request_about_end = response_about_end.json()
    request_in_progress = response_in_progress.json()

    m = utility.make_tel_block(request_7_days.get('results'), request_about_end.get('results'),request_in_progress.get('results'))
    if m == {}:  # if no results were returned
        say("No search results found , please try again")
        return
    # adds user to list of users that have active configurations
    active_list.append(message.get('user'))
    # send the message to the channel
    say(m)
    curr_message = client.conversations_history(channel=message.get('channel'), inclusive=True, latest=str(time()),
                                                limit=1)
    utility.add_user_info(admin_list, message.get('user'), curr_message["messages"][0].get('ts'), request_7_days, message)
    utility.add_user_info(admin_list, message.get('user'), curr_message["messages"][0].get('ts'), request_about_end, message)
    utility.add_user_info(admin_list, message.get('user'), curr_message["messages"][0].get('ts'), request_in_progress, message)
    
    logger.info(f"Function main_menu() successfully finished for user {app.client.users_info(user=message.get('user')).get('user').get('name')}")

@app.message() 
def get_chat_message(message: {}, say, ack, user_id: str, channel_id: str):
    
    if message.get('text', {}).lower() == "start":
        main_menu(message, say, 0)
    elif message.get('text', {}).lower() == "end":
        abort_action(user_id, channel_id, say, ack)
    elif message.get('text', {}).lower() == "kill":
        kill_server(message)
    else:
        say("Welcome to Telefly Admin-Bot. Type 'start' to get started.")

    logger.info(
        f"Function get_chat_message() successfully finished for user {app.client.users_info(user=message.get('user')).get('user').get('name')}",
        extra={"chat message": message.get('text')})

def main():
    """
    main function , starts Slack server connection
    """
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    # initiate main function
    main()
