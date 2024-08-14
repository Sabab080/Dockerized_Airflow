import logging
import json
from datetime import datetime
from sqlalchemy import create_engine
from airflow.decorators import dag, task
import pandas as pd

# Path to the credentials file
credentials_path = '/opt/airflow/db_credentials.json'
target_table = 'daily_user_sales'

# Load database credentials from the JSON file
def load_db_credentials():
    with open(credentials_path, 'r') as f:
        return json.load(f)

# Extract data from source MySQL database
@task
def extract_data(extract_query):
    try:
        credentials = load_db_credentials()
        logging.info("Extracting data from source MySQL database...")
        source_connection_url = f"mysql+mysqlconnector://{credentials['user']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{credentials['source_database']}"
        engine = create_engine(source_connection_url)
        df = pd.read_sql(extract_query, engine)
        logging.info("Data extraction completed.")
        return df  # Return the dataframe as JSON string
    except Exception as e:
        logging.error("Error extracting data from source MySQL database: %s", str(e))
        raise

# Load data into target MySQL database
@task
def load_data(df, target_table_name):
    try:
        credentials = load_db_credentials()
        logging.info("Loading data into target MySQL database...")
        target_connection_url = f"mysql+mysqlconnector://{credentials['user']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{credentials['target_database']}"
        engine = create_engine(target_connection_url)
        #df = pd.read_json(df_json)  # Convert JSON string back to dataframe
        df.to_sql(target_table_name, engine, if_exists='append', schema=credentials['target_database'], index=False)
        logging.info("Data loading completed.")
    except Exception as e:
        logging.error("Error loading data into target MySQL database: %s", str(e))
        raise

# Define default arguments for the DAG
default_args = {
    'owner': '',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': False,
}

# Define the DAG
@dag(
    default_args=default_args,
    description='Transfer data from source MySQL database to target MySQL database',
    schedule_interval=None,
    #schedule_interval='0 0 * * *',
    start_date=datetime(2024, 4, 18),
    max_active_runs=1,
    tags=['daily', 'sales'],
)
def etl_daily_sales():

    extract_query = """
    				Your extraction logic goes here !
                    """

    # Define task to extract data
    extracted_data = extract_data(extract_query)

    # Define task to load data
    load_data(extracted_data, target_table)

# Instantiate the DAG
dag = etl_daily_sales()

# Define logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

