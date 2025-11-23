import requests
import pandas as pd
import logging

DATA_SOURCE_URL = "http://10.43.100.103:8000"

def fetch_data(group_id="1"):
    """
    Fetches data from the external API.
    """
    try:
        response = requests.get(f"{DATA_SOURCE_URL}/data/{group_id}")
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        logging.info(f"Fetched {len(df)} records.")
        return df
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        raise

def save_raw_data(df, path):
    df.to_csv(path, index=False)
    logging.info(f"Raw data saved to {path}")

