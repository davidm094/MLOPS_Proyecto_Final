import requests
import pandas as pd
import logging
import time

DATA_SOURCE_URL = "http://10.43.100.103:8000"

def fetch_data(group_number="5", day="Tuesday"):
    """
    Fetches data from the external API using query parameters.
    """
    try:
        url = f"{DATA_SOURCE_URL}/data"
        params = {
            "group_number": group_number,
            "day": day
        }
        logging.info(f"Requesting data from URL: {url} with params: {params}")
        response = requests.get(url, params=params, timeout=30) # Added timeout
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        logging.info(f"Fetched {len(df)} records from API.")
        return df
    except Exception as e:
        error_msg = f"Error fetching data: {e}"
        logging.error(error_msg)
        # Write error to file for debugging
        try:
            with open("/tmp/ingestion_error.log", "w") as f:
                f.write(str(e))
        except:
            pass
        
        logging.info("Sleeping for 600 seconds to allow debugging via kubectl exec...")
        time.sleep(600)
        raise

def save_raw_data(df, path):
    df.to_csv(path, index=False)
    logging.info(f"Raw data saved to {path}")

