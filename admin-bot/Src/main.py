import os
import signal
import json
from pydantic_settings import BaseSettings
from pydantic import Field
from slack_sdk import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from time import time
from datetime import datetime, timedelta, timezone
from slack_sdk.errors import SlackApiError
import utility
import requests
import config
import logging
import pickle
import faiss
from pythonjsonlogger import jsonlogger
from langchain.text_splitter import TokenTextSplitter
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from openai import BadRequestError

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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


####################################################
AZURE_API_KEY = variables.AZURE_API_KEY
AZURE_OPENAI_ENDPOINT = variables.AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_VERSION = "2024-02-01"
AZURE_DEPLOYMENT_NAME = "text-embedding-ada-002"

FAISS_LOCAL_DIR = "./data"

FAISS_INDEX_PATHS = {
    "firefly": os.path.join(FAISS_LOCAL_DIR, "faiss_index_firefly"),
    "confluence": os.path.join(FAISS_LOCAL_DIR, "faiss_index_confluence"),
    "slack": os.path.join(FAISS_LOCAL_DIR, "faiss_index_slack")
}
FAISS_METADATA_PATHS = {
    "firefly": os.path.join(FAISS_LOCAL_DIR, "faiss_metadata_firefly.pkl"),
    "confluence": os.path.join(FAISS_LOCAL_DIR, "faiss_metadata_confluence.pkl"),
    "slack": os.path.join(FAISS_LOCAL_DIR, "faiss_metadata_slack.pkl")
}

# 🔺 Initialize Embeddings Model
embeddings_model = AzureOpenAIEmbeddings(
    api_key=AZURE_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    deployment=AZURE_DEPLOYMENT_NAME,
    openai_api_version=AZURE_OPENAI_API_VERSION,
)

# 🔺 Load FAISS Index from Downloaded S3 Data
def load_faiss_index(index_key):
    """
    Loads a FAISS index from the downloaded S3 files.
    """
    if not os.path.exists(FAISS_INDEX_PATHS[index_key]):
        logger.warning(f"🚨 FAISS index not found for {index_key}. Exiting...")
        return None

    try:
        logger.info(f"🔄 Loading FAISS index from {FAISS_INDEX_PATHS[index_key]}...")
        
        # ✅ Pass the embeddings model to fix the error
        vector_store = FAISS.load_local(
            FAISS_INDEX_PATHS[index_key], 
            embeddings_model,  # ✅ Fix: Add missing argument
            allow_dangerous_deserialization=True
        )
        
        logger.info(f"✅ FAISS index loaded successfully for {index_key}.")
        return vector_store
    except Exception as e:
        logger.error(f"🚨 Error loading FAISS index for {index_key}: {str(e)}", exc_info=True)
        return None


# 🔺 Load FAISS indices
faiss_indices = {}
for source in FAISS_INDEX_PATHS.keys():
    faiss_index = load_faiss_index(source)
    if faiss_index:
        faiss_indices[source] = faiss_index

print("🚀 FAISS indices are ready to use!")

# 🔺 Initialize Retrieval QA for Each Source
qa_chains = {}
for source, faiss_index in faiss_indices.items():
    qa_chains[source] = RetrievalQA.from_chain_type(
        llm=AzureChatOpenAI(
            model="testdeployment",
            api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        ),
        retriever=faiss_index.as_retriever()
    )


####################################################

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
    """
    Executes the account search and returns results.
    """
    logger.info(f"🔍 Executing account search for: '{account}' with num: {num}")
    logger.info(f"📝 Message context: {json.dumps(message, indent=2)}")
    
    try:
        # Log the API endpoint being called
        logger.info(f"🌐 Calling API endpoint: {variables.return_account}")
        logger.info(f"📊 Search parameters: accountName='{account}', num={num}")
        
        # Make the API request
        response = requests.get(variables.return_account,
                                data={'accountName': account, "num": num})
        
        logger.info(f"📡 API Response Status: {response.status_code}")
        logger.info(f"📡 API Response Headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            logger.error(f"❌ API request failed with status {response.status_code}")
            logger.error(f"❌ Response text: {response.text}")
            say(f"⚠️ Search failed with status {response.status_code}. Please try again later.")
            return
            
        # Parse the response
        try:
            request = response.json()
            logger.info(f"✅ API response parsed successfully: {json.dumps(request, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response: {str(e)}")
            logger.error(f"❌ Raw response: {response.text}")
            say("⚠️ Error parsing search results. Please try again.")
            return
            
        # Check if results exist
        if 'results' not in request:
            logger.warning("⚠️ No 'results' key found in API response")
            logger.warning(f"⚠️ Available keys: {list(request.keys())}")
            say("⚠️ Unexpected response format from search API.")
            return
            
        # Create the Slack block
        logger.info(f"🔨 Creating Slack block with {len(request.get('results', []))} results")
        m = utility.make_block(request.get('results'), account)
        
        if m == {}:  # if no results were returned
            logger.info(f"🔍 No search results found for query: '{account}'")
            say("No search results found, please try again")
            return
            
        logger.info(f"✅ Slack block created successfully: {json.dumps(m, indent=2)}")
        say(m)
        logger.info(f"✅ Search results sent to Slack for query: '{account}'")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"🚨 Network error during account search: {str(e)}", exc_info=True)
        say("⚠️ Network error occurred while searching. Please check your connection and try again.")
    except Exception as e:
        logger.error(f"🚨 Unexpected error in account_search_result: {str(e)}", exc_info=True)
        say("⚠️ An unexpected error occurred while searching. Please try again.")

@app.action("account_search")
def handle_some_action(message: {}, ack, body, logger, say):
    """
    Handles the account search action from the Slack interface.
    This function is triggered when a user types in the search box and submits.
    """
    try:
        # Acknowledge the action
        ack()
        
        # Extract the search value
        if 'actions' not in body or not body['actions']:
            say("⚠️ Error: No search action found. Please try again.")
            return
            
        action = body['actions'][0]
        
        if 'value' not in action:
            say("⚠️ Error: No search value found. Please try again.")
            return
            
        global account
        account = action['value'].lower()
        
        # Check if account is empty or just whitespace
        if not account or account.strip() == "":
            say("⚠️ Please enter a valid account name to search for.")
            return
            
        account_search_result(message, account, say, 0)
        
    except Exception as e:
        logger.error(f"Error in account_search handler: {str(e)}")
        say(f"⚠️ An error occurred while processing your search: {str(e)}")

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
    sandbox_last_7_days = utility.get_users_created_in_last_seven_days()

    # parse it into json
    request_7_days = response_7_days.json()
    request_about_end = response_about_end.json()
    request_in_progress = response_in_progress.json()
    request_sandbox_last_7_days = sandbox_last_7_days
    
    m = utility.make_tel_block(request_7_days.get('results'), request_about_end.get('results'),request_in_progress.get('results'), sandbox_last_7_days, client)
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
    utility.add_user_info(admin_list, message.get('user'), curr_message["messages"][0].get('ts'), request_sandbox_last_7_days, message)

    logger.info(f"Function main_menu() successfully finished for user {app.client.users_info(user=message.get('user')).get('user').get('name')}")

########################################################################################################
@app.event("block_actions")
def handle_block_actions(payload):
    """
    Handles all block actions including the account search functionality.
    """
    logger.info("🔘 BLOCK_ACTIONS EVENT TRIGGERED")
    logger.info(f"📝 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        if 'actions' not in payload or not payload['actions']:
            logger.warning("⚠️ No actions found in block_actions payload")
            return
            
        action_id = payload['actions'][0]['action_id']
        
        if action_id == "view_sandbox_details":
            utility.handle_view_sandbox_details(payload)
        elif action_id == "view_deals_details":
            utility.handle_view_deals_details(payload)
        elif action_id == "account_search":
            # This should be handled by the @app.action("account_search") decorator
            pass
        else:
            logger.info(f"Unhandled action_id: {action_id}")
            
    except Exception as e:
        logger.error(f"Error in handle_block_actions: {str(e)}")



@app.action("view_sandbox_details")
def handle_view_sandbox_details(ack, body, client):
    """
    Handles the 'View Details' button click and posts a formatted text block of sandbox user data.
    """
    ack()  # Acknowledge the action
    
    # Fetch users created in the last 7 days
    arr_sandbox_last_7_days = utility.get_users_created_in_last_seven_days()  # Ensure this is defined
    if not arr_sandbox_last_7_days:
        message = "No sandbox users found in the last 7 days."
    else:
        arr_sandbox_last_7_days = sorted(
            arr_sandbox_last_7_days,
            key=lambda user: user.get('created_at', 'N/A'),
            reverse=True
        )
        # Start with the header
        message = "Sandbox Users Report (Last 7 Days)\n-------------\n"

        # Add details for each user
        for user in arr_sandbox_last_7_days:
            name = user.get('name', 'N/A').replace(",", " ")  # Replace commas to avoid formatting issues
            email = user.get('email', 'N/A').replace(",", " ")
            account = user.get('app_metadata', {}).get('account_name', 'N/A').replace(",", " ")
            created_at = user.get('created_at', 'N/A')
            created_at = created_at.split("T")[0] if "T" in created_at else created_at

            # Add user details
            message += (
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Account: {account}\n"
                f"Created At: {created_at}\n"
                "-------------\n"
            )

    # Wrap the message in triple backticks for a code block
    message_blob = f"```\n{message.strip()}\n```"

    # Post the formatted content to Slack
    try:
        client.chat_postMessage(
            channel=body['channel']['id'],
            text="Here is the sandbox user data for the last 7 days:",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message_blob}
                }
            ]
        )
        logger.info(
            "Successfully used handle_view_sandbox_details function",
            extra={"channel_id": body['channel']['id'], "level": "INFO"}
        )
    except Exception as e:
        print("Failed to post message to Slack:", str(e))


def chunk_text(text, chunk_size=2900):
    """Splits text into smaller chunks of max 2900 characters for Slack."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

@app.action("view_deals_details")
def handle_view_deals_details(payload, body, ack, client):
    logger.debug("✅ Event Triggered: view_deals_details")
    print("✅ Event Triggered: view_deals_details")
    ack()

    # Get the channel ID
    channel_id = (
        body.get("channel", {}).get("id")
        or payload.get("container", {}).get("channel_id")
        or payload.get("channel", {}).get("id")
        or "D0807TR5EBC"
    )
    logger.debug(f"📌 Channel ID: {channel_id}")

    if not channel_id:
        logger.error("❌ Unable to retrieve channel ID")
        print("❌ Unable to retrieve channel ID")
        return

    # Fetch deals
    try:
        deals = utility.get_recent_deals_by_type(utility.DEAL_TYPE, utility.DAYS, utility.owners_map)
        logger.debug(f"📊 Retrieved {len(deals)} deals")
    except Exception as e:
        logger.error(f"❌ Error fetching deals: {str(e)}")
        return

    # Build the message (Keeping your format)
    message = "New Deals Report (Last 7 Days)\n-------------\n"

    for deal in deals:
        deal_name = deal['properties'].get('dealname', 'N/A').replace(",", " ")
        amount = deal['properties'].get('amount', 'N/A')
        owner_id = deal['properties'].get('hubspot_owner_id', 'N/A')
        deal_owner = utility.owners_map.get(owner_id, "Unknown Owner").replace(",", " ")
        deal_source_1 = deal['properties'].get('deal_source_1', 'N/A') or 'N/A'
        deal_source_2 = deal['properties'].get('deal_source_2', 'N/A') or 'N/A'
        created_at = deal['properties'].get('createdate', 'N/A')
        created_at = created_at.split("T")[0] if "T" in created_at else created_at

        message += (
            f"Name: {deal_name}\n"
            f"Amount: {amount}\n"
            f"Owner: {deal_owner}\n"
            f"Source 1: {deal_source_1}\n"
            f"Source 2: {deal_source_2}\n"
            f"Created: {created_at}\n"
            "-------------\n"
        )

    # Split the message into chunks (max 2900 characters per part)
    message_chunks = chunk_text(message)

    try:
        for idx, chunk in enumerate(message_chunks):
            client.chat_postMessage(
                channel=channel_id,
                text=f"Here are the new deals added in the last 7 days (Part {idx + 1}):",
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": chunk}}]
            )
            logger.info(f"✅ Sent Part {idx + 1} of deals to Slack")
            print(f"✅ Sent Part {idx + 1} of deals to Slack")
    except Exception as e:
        logger.error(f"❌ Failed to post message to Slack: {str(e)}")
        print(f"❌ Failed to post message to Slack: {str(e)}")





########################################################################################################

@app.event("message")
def handle_message_events(body, say):
    """Handles Slack messages and responds with the best answer from FAISS or executes bot commands."""
    event = body.get("event", {})
    user_id = event.get("user")
    text = event.get("text", "").strip().lower()
    channel_id = event.get("channel")

    # IGNORE messages from the website visitors channel - bot should only READ from it, not respond
    if channel_id == "C08N60KMEA2":
        return

    if not text:
        return

    # Handle bot commands first
    if text == "start":
        logger.info(f"🚀 Triggering main_menu() for {user_id}")
        main_menu(event, say, 0)
        return
    elif text == "end":
        logger.info(f"🛑 Triggering abort_action() for {user_id}")
        abort_action(user_id, event.get("channel"), say, lambda: None)
        return
    elif text == "kill":
        logger.info(f"💀 Triggering kill_server() for {user_id}")
        kill_server(event)
        return

    # 🔄 Process normal messages (search FAISS)
    logger.info(f"🔍 Processing normal message for search: '{text}'")
    try:
        best_answer = None
        combined_context = ""
        max_score = -float("inf")
        max_retrieved_docs = 5  # Number of documents to retrieve from FAISS

        logger.debug("🔍 Searching FAISS indexes...")

        for source, qa_chain in qa_chains.items():
            try:
                logger.debug(f"🔎 Querying FAISS index: {source}")

                # 🔹 Invoke LLM to get an answer
                result = qa_chain.invoke(text)
                answer = result["result"] if isinstance(result, dict) else result
                logger.debug(f"📝 {source} response: {answer}")

                # Filter out generic "I don't know" responses
                if not any(phrase in answer.lower() for phrase in ["i'm sorry", "i don't know", "i don't have"]):
                    combined_context += f"{answer}\n"

                    # Retrieve supporting documents
                    docs = qa_chain.retriever.invoke(text, search_kwargs={"k": max_retrieved_docs})

                    if docs:
                        score = docs[0].metadata.get("score", 0)  # Get score from metadata
                        if score > max_score:
                            max_score = score
                            best_answer = answer

            except BadRequestError as e:
                if "context_length_exceeded" in str(e):
                    say("⚠️ *FireflyBot Alert:* Your query is too broad and exceeds the token limit. Try rewording your question.")
                    return
                logger.error(f"🚨 OpenAI BadRequestError in {source}: {str(e)}")

            except Exception as e:
                logger.error(f"🚨 Error processing FAISS index {source}: {str(e)}", exc_info=True)

        # 🔹 Token Limit Check - Ensure within Model Context Length
        max_tokens = 16000  # Keep below model max limit (16385 tokens)
        text_splitter = TokenTextSplitter(chunk_size=max_tokens, chunk_overlap=0)

        # Select the best answer or fallback to combined context
        if best_answer:
            split_text = text_splitter.split_text(best_answer)
        else:
            split_text = text_splitter.split_text(combined_context)

        truncated_context = split_text[0] if split_text else ""

        if truncated_context.strip():
            logger.info(f"✅ Responding with: {truncated_context}")
            say(f"🧐 *FireflyBot Answer:*\n{truncated_context}\n")
        else:
            logger.warning("⚠️ No valid answer found or response too long.")
            say("⚠️ *FireflyBot Alert:* Your query is too broad and exceeds the token limit. Try elaborating on a more specific question.")

    except Exception as e:
        logger.error(f"🚨 Unexpected error: {str(e)}", exc_info=True)
        if "say" in locals():
            say("⚠️ *FireflyBot Alert:* An error occurred while processing your question.")

########################################################################################################

def main():
    """
    main function , starts Slack server connection
    """
    try:
        SocketModeHandler(app, app_token).start()
        logger.info("Admin-bot is now running and listening for events!")
    except Exception as e:
        logger.error(f"Failed to start SocketModeHandler: {str(e)}")
        raise


if __name__ == "__main__":
    # initiate main function
    main()
