import datetime
import http.client
import json
import logging
import config
import requests
from snowflake import connector
from pythonjsonlogger import jsonlogger


# configure logger
formatter = jsonlogger.JsonFormatter("%(asctime)s - %(message)s")
json_handler = logging.StreamHandler()
json_handler.setFormatter(formatter)
logger = logging.getLogger('my_json')
logger.setLevel(logging.INFO)
logger.addHandler(json_handler)


# Get env vars
env_vars = config.Vars()
USER = env_vars.USER
PASSWORD = env_vars.PASSWORD
WAREHOUSE = env_vars.WAREHOUSE
ACCOUNT = env_vars.ACCOUNT

AWS_ACCESS_KEY_ID = env_vars.AWS_ACCESS_KEY
AWS_SECRET_ACCESS_KEY = env_vars.AWS_SECRET_KEY

ES_USER = env_vars.ES_USERNAME
ES_PASSWORD = env_vars.ES_PASSWORD


def json_to_list(data) -> []:
    """
    Make the elastic output into a Python list
    :param data: The elastic data that was returned from the query
    :return: List to write to Snowflake
    """
    list_of_lists = []
    logger.info("Making list...")
    try:
        for index in data.get('aggregations', {}).get('index_count', {}).get('buckets', []):  # for each index
            index_name = index.get('key')
            for integration in index.get('integration_count', {}).get('buckets', []):  # for each integration
                integration_id = integration.get('key')
                provider = integration.get('provider', {}).get('buckets', [{}])[0].get('key')
                for state_bucket in integration.get('state_count', {}).get('buckets', []):  # for each state
                    state = state_bucket.get('key')
                    doc_count = state_bucket.get('doc_count')
                    times = str(datetime.datetime.now())
                    list_of_lists.append([times, index_name, integration_id, state, provider, doc_count])  # add to list
    except KeyError as err:
        logger.error(f"Function json_to_list() failed: {err}")
        exit(0)

    return list_of_lists


def write_to_snowflake(list_of_rows) -> None:
    """
    This function writes the list from json_to_list() into Snowflake
    :param list_of_rows: The returned list from json_to_list()
    :return: None
    """
    # Establish the connection
    logger.info("Establishing connection to Snowflake...")
    try:
        connector.paramstyle = 'qmark'
        conn = connector.connect(
            user=USER,
            password=PASSWORD,
            account=ACCOUNT,
            warehouse=WAREHOUSE,
            database="FIREFLY",
            schema="MRR"
        ).cursor()

    except connector.errors.Error as error:
        logger.error(msg=f"Failed to connect to snowflake. Error: {error}")
        exit(0)
    # Get the cursor object

    cur = conn
    # Execute SQL statement to insert data
    logger.info("Inserting to Snowflake...")
    try:
        sql = "INSERT INTO EMBEDIFLY_COVERAGE (TIMESTAMP, _INDEX, INTEGRATIONID, STATE_ASSET , PROVIDER, DOC_COUNT) VALUES (?, ?, ?, ?, ?, ?)"
        cur.executemany(sql, list_of_rows)
    except connector.errors.Error as snowflakeError:
        logger.error(f"Error inserting to table: {snowflakeError}")
        # close cursor and connection
        cur.close()
        conn.close()
        exit(0)

    # Commit changes and close cursor and connection
    cur.close()
    conn.close()


def main():
    query_size = 0
    agg_size = 10000
    endpoint = env_vars.ES_ENDPOINT
    query = json.dumps(
                        {
                          "size": query_size,
                          "aggs": {
                            "index_count": {
                              "terms": {
                                "field": "_index",
                                "size": agg_size
                              },
                              "aggs": {
                                "integration_count": {
                                  "terms": {
                                    "field": "integrationId.keyword",
                                    "size": agg_size
                                  },
                                  "aggs": {
                                    "provider": {
                                      "terms": {
                                        "field": "provider.keyword",
                                        "size": agg_size
                                      }
                                    },
                                    "state_count": {
                                      "terms": {
                                        "field": "state.keyword",
                                        "size": agg_size
                                      }
                                    }
                                  }
                                }
                              }
                            }
                          },
                          "query": {
                            "bool": {
                              "must": [
                                {
                                  "match": {
                                    "_index": "*meta*"
                                  }
                                },
                                {
                                  "match": {
                                    "isExcluded": False
                                  }
                                }
                              ]
                            }
                          }
                        })
    try:
        logger.info("Making request to Elastic...")
        es = requests.post(url=endpoint, json=json.loads(query))
    except (http.client.error, requests.exceptions.ConnectionError, requests.HTTPError) as HTTP_Error:
        logger.error(f"HTTP error when making POST request: {HTTP_Error}")
        exit(0)

    try:
        content = json.loads(es.content)
        if content.get("error", "") != "":
            logger.error(f"HTTP error when making POST request", extra={"status_code": content.get("status", "")})
            exit(0)
        else:
            logger.info("Successfully queried Elasticsearch", extra={"status_code": 200})
    except ValueError as err:
        logger.error(f"Got empty / bad response from Elastic: {err}")
        exit(0)
    list_of_rows = json_to_list(content)
    write_to_snowflake(list_of_rows)


main()
