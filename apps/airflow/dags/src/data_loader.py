import requests
import pandas as pd
import logging
import time
import boto3
import os
from io import StringIO

DATA_SOURCE_URL = "http://10.43.100.103:8000"

# S3 Configuration
S3_ENDPOINT = os.getenv('AIRFLOW_VAR_S3_ENDPOINT', 'http://seaweedfs-s3.mlops.svc:8333')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID', 'any')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'any')
BUCKET_NAME = 'data-raw'

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

def ensure_bucket_exists(s3, bucket_name):
    try:
        s3.head_bucket(Bucket=bucket_name)
    except:
        try:
            s3.create_bucket(Bucket=bucket_name)
            logging.info(f"Created bucket {bucket_name}")
        except Exception as e:
            logging.warning(f"Could not create bucket {bucket_name}: {e}")

def fetch_data(group_number="5", day="Tuesday"):
    """
    Fetches data from the external API using query parameters.
    The API returns: {"group_number": X, "day": Y, "batch_number": Z, "data": [...]}
    We extract the "data" array and convert it to a DataFrame.
    """
    try:
        url = f"{DATA_SOURCE_URL}/data"
        params = {
            "group_number": group_number,
            "day": day
        }
        logging.info(f"Requesting data from URL: {url} with params: {params}")
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        json_response = response.json()
        
        # Extract the actual data array from the response
        if isinstance(json_response, dict) and 'data' in json_response:
            records = json_response['data']
            logging.info(f"API returned batch_number: {json_response.get('batch_number', 'N/A')}")
        elif isinstance(json_response, list):
            # If API returns a list directly
            records = json_response
        else:
            raise ValueError(f"Unexpected API response format: {type(json_response)}")
        
        df = pd.DataFrame(records)
        logging.info(f"Fetched {len(df)} records from API.")
        logging.info(f"Columns: {df.columns.tolist()}")
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

def save_raw_data(df, filename):
    """
    Saves DataFrame to S3. Filename should be the object key (e.g. 'current_batch.csv')
    """
    try:
        s3 = get_s3_client()
        ensure_bucket_exists(s3, BUCKET_NAME)
        
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        
        s3.put_object(Body=csv_buffer.getvalue(), Bucket=BUCKET_NAME, Key=filename)
        logging.info(f"Saved {filename} to S3 bucket {BUCKET_NAME}")
        return f"s3://{BUCKET_NAME}/{filename}"
    except Exception as e:
        logging.error(f"Failed to save to S3: {e}")
        raise

def load_raw_data(filename):
    """
    Loads DataFrame from S3.
    """
    try:
        s3 = get_s3_client()
        logging.info(f"Loading {filename} from S3 bucket {BUCKET_NAME}")
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=filename)
        df = pd.read_csv(obj['Body'])
        return df
    except Exception as e:
        logging.error(f"Failed to load from S3: {e}")
        # Return empty dataframe or raise depending on logic
        if "NoSuchKey" in str(e):
             return None
        raise
