import ssl
import requests
import pymongo
import snowflake.connector
# import config
from datetime import datetime
import pytz
import logging
import os
from requests.auth import HTTPBasicAuth
from pythonjsonlogger import jsonlogger


# Configure logger
formatter = jsonlogger.JsonFormatter("%(asctime)s - %(message)s")
json_handler = logging.StreamHandler()
json_handler.setFormatter(formatter)
logger = logging.getLogger('my_json')
logger.setLevel(logging.INFO)
logger.addHandler(json_handler)

# Get env vars
# SETTINGS = config.Vars()

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.environ.get("MONGO_COLLECTION_NAME")
db = client[MONGO_DB_NAME]
collection = db[MONGO_COLLECTION_NAME]

# Snowflake configuration
table = os.environ.get("TABLE")

# Firefly API details
FIREFLY_API_URL=os.environ.get("FIREFLY_API_URL")

# Snowflake connection
snowflake_conn = snowflake.connector.connect(
    user=os.environ.get("USER"),
    password=os.environ.get("PASSWORD"),
    account=os.environ.get("ACCOUNT"),
    warehouse=os.environ.get("WAREHOUSE"),
    database=os.environ.get("DATABASE"),
    schema=os.environ.get("SCHEMA")
)

def send_api_request(account_id):
    headers = {'x-firefly-accountid': str(account_id)}
    basic = HTTPBasicAuth(os.environ.get("API_USERNAME"), os.environ.get("API_PASSWORD"))    
    try:
        response = requests.post(FIREFLY_API_URL, headers=headers, auth=basic)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(msg=f'Failed to send API request for account_id {account_id}.', extra={"Error": str(e)})
        return None

def main():
    try:
        query = {'active': True, 'onbording_status': 'done'}
        result = collection.find(query, {'_id': 1})

        for record in result:
            account_id = str(record.get('_id'))
            logger.info(msg=f'Sending API request for account_id: {account_id}')
            api_response = send_api_request(account_id)

            if api_response is not None:
                multiplied_value = int(api_response * 12)
                logger.info(msg=f'The total cost for {account_id} is {multiplied_value}')
                IsraelTz = pytz.timezone("Israel") 
                timeInIsrael = datetime.now(IsraelTz)
                timestamp = timeInIsrael.strftime("%Y-%m-%d %H:%M:%S")
                cursor = snowflake_conn.cursor()
                try:
                    cursor.execute(f"""
                        INSERT INTO {table} (TIMESTAMP, ACCOUNT_ID, TOTAL_COST)
                        VALUES (%s, %s, %s)
                    """, (timestamp, account_id, multiplied_value))
                    cursor.close()
                    snowflake_conn.commit()

                    logger.info(msg=f'Data for account_id {account_id} (multiplied by 12) inserted into Snowflake.')
                except snowflake.connector.errors.Error as error:
                    logger.error(msg=f'Error inserting data into Snowflake for account_id {account_id}.', extra={"Error": str(error)})
    finally:
        client.close()
        snowflake_conn.close()

if __name__ == '__main__':
    main()
