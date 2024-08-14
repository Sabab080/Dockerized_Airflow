import logging
import json
from datetime import datetime
from sqlalchemy import create_engine
from airflow.decorators import dag, task
import pandas as pd

# Path to the credentials file
credentials_path = '/opt/airflow/db_credentials.json'


# Load database credentials from the JSON file
def load_db_credentials():
    with open(credentials_path, 'r') as f:
        return json.load(f)

# Extract data from source MySQL database
@task
def extract_data(credentials, extract_query):
    try:
        logging.info("Extracting data from source MySQL database...")
        source_connection_url = f"mysql+mysqlconnector://{credentials['user']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{credentials['target_database']}"
        engine = create_engine(source_connection_url)
        df = pd.read_sql(extract_query, engine)
        logging.info("Data extraction completed.")
        return df
    except Exception as e:
        logging.error("Error extracting data from source MySQL database: %s", str(e))
        raise

# Transform daily data to monthly table and aggregate/update required columns
@task
def aggregate_monthly_data(df, credentials, target_table, group_by_cols):
    try:
        logging.info("Aggregating monthly data...")
        df['date_value'] = pd.to_datetime(df['date_value'])
        df['month_key'] = df['date_value'].dt.strftime('%b-%y')

        # Drop less required columns
        df.drop(columns=['insertion_date', 'date_value', 'id'], inplace=True)

        # Aggregate the required columns based on the 'month_key'
        agg_cols = {
            'debit': 'sum',
            'credit': 'sum',
            'debit_count': 'sum',
            'credit_count': 'sum',
            'net': 'sum'
        }

        # Group by columns with month_key
        group_by_cols_with_month_key = ['month_key'] + group_by_cols

        # Group the DataFrame and aggregate
        df_monthly = df.groupby(group_by_cols_with_month_key).agg(agg_cols).reset_index()

        target_connection_url = f"mysql+mysqlconnector://{credentials['user']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{credentials['target_database']}"
        engine = create_engine(target_connection_url)

        # Fetch existing records from the target table
        existing_records_df = pd.read_sql_table(target_table, con=engine)

        if not existing_records_df.empty:
            existing_records_grouped = existing_records_df.groupby(group_by_cols_with_month_key)

            # Update existing rows in the target table
            for _, group_data in df_monthly.groupby(group_by_cols_with_month_key):
                group_data_dict = tuple(group_data[group_by_cols_with_month_key].iloc[0])
                if group_data_dict in existing_records_grouped.groups:
                    existing_index = existing_records_grouped.groups[group_data_dict][0]
                    for col in agg_cols.keys():
                        # Calculate the delta value
                        delta_value = group_data[col].values[0] - existing_records_df.loc[existing_index, col]
                        existing_records_df.loc[existing_index, col] += delta_value
                else:
                    existing_records_df = pd.concat([existing_records_df, group_data], ignore_index=True)
        else:
            existing_records_df = df_monthly

        # Add current insertion date
        existing_records_df['insertion_date'] = pd.Timestamp.now().date()

        logging.info("Monthly data aggregation completed.")
        return existing_records_df
    except Exception as e:
        logging.error("Error aggregating monthly data: %s", str(e))
        raise

# Load data into target MySQL database
@task
def load_data(df, credentials, target_table_name):
    try:
        logging.info("Loading data into target MySQL database...")
        target_connection_url = f"mysql+mysqlconnector://{credentials['user']}:{credentials['password']}@{credentials['host']}:{credentials['port']}/{credentials['target_database']}"
        engine = create_engine(target_connection_url)
        df.to_sql(target_table_name, engine, if_exists='replace', schema=credentials['target_database'], index=False)
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
    #schedule_interval='0 1 * * *'
    start_date=datetime(2024, 4, 18),
    max_active_runs=1,
    tags=['monthly', 'sales'],
)
def etl_monthly_sales():
    credentials = load_db_credentials()
    target_table = 'monthly_user_sales'
    extract_query = "SELECT * FROM daily_user_sales;"

    # Define task to extract data
    extracted_data = extract_data(credentials, extract_query)

    # Define the task to aggregate monthly data
    aggregated_data = aggregate_monthly_data(extracted_data, credentials, 'monthly_user_sales', ['account_id', 'parent_id', 'branch_id', 'transaction_type_id'])

    # Define task to load data
    load_data(aggregated_data, credentials, target_table)

# Instantiate the DAG
dag = etl_monthly_sales()

# Define logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

