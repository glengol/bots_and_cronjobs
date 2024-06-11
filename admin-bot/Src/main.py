import os
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


def configure_instance(message: {} ,say, num: int):
    """
    Start a new configuration (instance)
    :param message: The message that was picked up by the listener
    :param say: Specifying the use of the Slack function say()
    :param num: if num == 0 then a string will be queried if == 1 a number will be queried
    """
    text = message.get('text')
    # parse the account name to use an action on
    name = utility.parse_account_name(text, num)
    # check if user has permissions
    # if message.get('user') not in admin_list:
    #     say(f"<@{message.get('user')}> you don't have permission to use the app!")
    #     return
    # if an empty string was provided
    if name == "":
        say(f"<@{message.get('user')}> Please enter a valid input!")
        return
    # adds user to list of users that have active configurations
    elif message.get('user') in active_list:
        say(f"<@{message.get('user')}> Your current session is active. To start a new session, click on the END "
            f"SESSION button or type ‘end’")
        return
    # makes an API request to Retool that returns all accounts
    response = requests.get(variables.return_account,
                            data={'accountName': name, "num": num})

    # that contain the string "name"
    request = response.json()

    m = utility.make_block(request.get('results'), name)
    if m == {}:  # if no results were returned
        say("No search results found , please try again")
        return
    # adds user to list of users that have active configurations
    active_list.append(message.get('user'))
    # send the message to the channel
    say(m)
    curr_message = client.conversations_history(channel=message.get('channel'), inclusive=True, latest=str(time()),
                                                limit=1)
    utility.add_user_info(admin_list, message.get('user'), curr_message["messages"][0].get('ts'), request, message)
    logger.info(f"Function configure_instance() successfully finished for user {app.client.users_info(user=message.get('user')).get('user').get('name')}",
                extra={"user_id": message.get("user"),
                       "text": message,
                       "level": "INFO"})

def configure_telemetry_instance(message: {}, say, num: int):
    """
    Start a new configuration (instance)
    :param message: The message that was picked up by the listener
    :param say: Specifying the use of the Slack function say()
    :param num: if num == 0 then a string will be queried if == 1 a number will be queried
    """
    # check if user has permissions
    if message.get('user') not in admin_list:
        say(f"<@{message.get('user')}> you don't have permission to use the app!")
        return
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
    
    logger.info(f"Function configure_instance() successfully finished for user {app.client.users_info(user=message.get('user')).get('user').get('name')}",
                extra={"user_id": message.get("user"),
                       "text": message,
                       "level": "INFO"})

@app.message()  # configure bot to do a command
def query_name(message: {}, say, ack, user_id: str, channel_id: str):
    """
    Configures the bot according to user input
    :param message: The message that was picked up by the listener
    :param say: Specifying the use of the Slack function say()
    :param ack: Sending acknowledgement to Slack
    :param user_id: Id of the message sender
    :param channel_id:  Id of the channel the message was sent in
    """
    
    if message.get('text', {})[0] == '!':
        configure_instance(message, say, 0)
    elif message.get('text', {})[0] == '?':
        configure_instance(message, say, 1)
    elif message.get('text', {}) == "start":
        configure_telemetry_instance(message, say, 0)
    else:
        try:
            if message.get('text', {}).index('end') == 0:
                abort_action(user_id, channel_id, say, ack)
        except ValueError:  # if 'end' was not found , handle ValueError exception
            try:
                if message.get('text', {}).index('End') == 0:
                    abort_action(user_id, channel_id, say, ack)
            except ValueError:
                pass
    logger.info(
        f"Function query_name() successfully finished for user {app.client.users_info(user=message.get('user')).get('user').get('name')}",
        extra={"user_id": user_id,
               "text": message.get('text'),
               "level": "INFO"})

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
    
@app.action("account_search")
def account_search(ack, body, logger):
    ack()
    # Extract the input value from the modal
    logger.info(body)

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
    if utility.get_item(admin_list, user_id, "Action") == "" or utility.get_item(admin_list, user_id,
                                                                                 "Account") == "":  # makes sure both fields are selected
        say(f"<@{user_id}> Please make sure that you've selected an account and action!")

    # execute suspend / activate / extend poc function
    elif utility.get_item(admin_list, user_id, "Action") == ":x: Suspend :x:" or \
            utility.get_item(admin_list, user_id, "Action") == ":white_check_mark: Activate :white_check_mark:":

        status = "false" if utility.get_item(admin_list, user_id, "Action") == ":x: Suspend :x:" else "true"
        #  makes an API request to Retool to suspend / activate
        requests.get(variables.suspend_activate,
                     data={"id": utility.get_id(utility.get_item(admin_list, user_id, "Request"), name),
                           "user": client.users_info(user=user_id).get("user", {}).get("real_name"),
                           "name": name, "status": status})
        # send confirmation message that the action successfully finished
        say(f"Account successfully {'suspended' if status == 'false' else 'activated'}. Please check "
            f"#account-mgmt-audit for more details")



    # execute extend POC 7 days
    elif utility.get_item(admin_list, user_id,
                          "Action") == ":hourglass_flowing_sand: Extend POC +7 days :hourglass_flowing_sand:":
        requests.get(
            variables.extend_poc_7_days,
            data={"id": utility.get_id(utility.get_item(admin_list, user_id, "Request"), name),
                  "name": client.users_info(user=user_id).get("user", {}).get("real_name"),
                  "url": name})
        # send confirmation message that the action successfully finished
        say(f"Account successfully extended POC +7 days. Please check #account-mgmt-audit for more details")
    
    # execute extend POC 2 days
    elif utility.get_item(admin_list, user_id,
                          "Action") == ":hourglass_flowing_sand: Extend POC +2 days :hourglass_flowing_sand:":
        requests.get(
            variables.extend_poc_2_days,
            data={"id": utility.get_id(utility.get_item(admin_list, user_id, "Request"), name),
                  "name": client.users_info(user=user_id).get("user", {}).get("real_name"),
                  "url": name})
        # send confirmation message that the action successfully finished
        say(f"Account successfully extended POC +2 days. Please check #account-mgmt-audit for more details")
        # if user is going to change account tier
    else:
        requests.get(variables.change_tier,
                     data={"id": utility.get_id(utility.get_item(admin_list, user_id, "Request"), name),
                           "status": utility.get_tier(utility.get_item(admin_list, user_id, "Action")),
                           "name": client.users_info(user=user_id).get("user", {}).get("real_name"),
                           "url": name})
        # send confirmation message that the action successfully finished
        say(f"Account successfully changed to {utility.get_tier(utility.get_item(admin_list, user_id, 'Action'))}. Please check"
            f" #account-mgmt-audit for more details")
    logger.info(
        f"Exited successfully from function execute_action() for user {app.client.users_info(user=user_id).get('user').get('name')}",
        extra={"user_id": user_id,
               "level": "INFO"})

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
    say("An active configuration was successfully aborted , to reconfigure use !<account> or ?<number>")

@app.event("reaction_added")
def handle_reaction_added_events(ack):
    """
    Handles reaction usage
    :param ack: Sending acknowledgement to Slack
    """
    ack()


def main():
    """
    main function , starts Slack server connection
    """
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    # initiate main function
    main()
