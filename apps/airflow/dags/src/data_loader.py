import requests
import pandas as pd
import logging
import time
import boto3
import os
from io import StringIO
from sqlalchemy import create_engine, text
from datetime import datetime
import uuid

# External API Configuration
DATA_SOURCE_URL = os.getenv("DATA_SOURCE_URL", "http://10.43.100.103:8000")

# S3 Configuration (SeaweedFS)
S3_ENDPOINT = os.getenv('AIRFLOW_VAR_S3_ENDPOINT', 'http://seaweedfs-s3.mlops.svc:8333')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID', 'any')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'any')
BUCKET_NAME = 'data-raw'

# PostgreSQL Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:airflow-postgres-root@postgres-postgresql.mlops.svc.cluster.local:5432/mlops_data')

def get_s3_client():
    """Get S3 client for SeaweedFS."""
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

def get_db_engine():
    """Get SQLAlchemy engine for PostgreSQL."""
    return create_engine(DATABASE_URL)

def ensure_bucket_exists(s3, bucket_name):
    """Ensure S3 bucket exists, create if not."""
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
    """
    try:
        url = f"{DATA_SOURCE_URL}/data"
        params = {
            "group_number": group_number,
            "day": day
        }
        logging.info(f"Requesting data from URL: {url} with params: {params}")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Extract the actual data array from the nested response
        if 'data' in data and isinstance(data['data'], list):
            df = pd.DataFrame(data['data'])
            logging.info(f"API returned batch_number: {data.get('batch_number')}")
        else:
            logging.warning("API response did not contain expected 'data' array.")
            df = pd.DataFrame(data)

        logging.info(f"Fetched {len(df)} records from API.")
        return df
    except Exception as e:
        error_msg = f"Error fetching data: {e}"
        logging.error(error_msg)
        raise

# ============================================
# S3 FUNCTIONS (Backup/Cache)
# ============================================

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
        if "NoSuchKey" in str(e):
            return None
        raise

# ============================================
# POSTGRESQL FUNCTIONS (Primary Storage)
# ============================================

def save_to_postgres(df, table_name, batch_id=None):
    """
    Saves DataFrame to PostgreSQL table.
    
    Args:
        df: DataFrame to save
        table_name: Target table ('raw_data', 'clean_data')
        batch_id: Optional batch identifier
    """
    try:
        engine = get_db_engine()
        
        # Add metadata columns
        df_copy = df.copy()
        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        if table_name == 'raw_data':
            df_copy['batch_id'] = batch_id
            df_copy['ingestion_timestamp'] = datetime.now()
        elif table_name == 'clean_data':
            df_copy['source_batch_id'] = batch_id
            df_copy['processing_timestamp'] = datetime.now()
        
        # Insert data
        df_copy.to_sql(table_name, engine, if_exists='append', index=False)
        logging.info(f"Saved {len(df_copy)} records to PostgreSQL table '{table_name}' (batch: {batch_id})")
        
        return batch_id
    except Exception as e:
        logging.error(f"Failed to save to PostgreSQL: {e}")
        raise

def load_from_postgres(table_name, limit=None, batch_id=None):
    """
    Loads DataFrame from PostgreSQL table.
    
    Args:
        table_name: Source table ('raw_data', 'clean_data')
        limit: Optional limit on number of rows
        batch_id: Optional filter by batch_id
    """
    try:
        engine = get_db_engine()
        
        query = f"SELECT * FROM {table_name}"
        conditions = []
        
        if batch_id:
            if table_name == 'raw_data':
                conditions.append(f"batch_id = '{batch_id}'")
            elif table_name == 'clean_data':
                conditions.append(f"source_batch_id = '{batch_id}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY id DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql(query, engine)
        logging.info(f"Loaded {len(df)} records from PostgreSQL table '{table_name}'")
        
        return df
    except Exception as e:
        logging.error(f"Failed to load from PostgreSQL: {e}")
        return None

def get_latest_batch_id(table_name='raw_data'):
    """Get the most recent batch_id from a table."""
    try:
        engine = get_db_engine()
        
        if table_name == 'raw_data':
            query = "SELECT DISTINCT batch_id FROM raw_data ORDER BY ingestion_timestamp DESC LIMIT 1"
        else:
            query = "SELECT DISTINCT source_batch_id as batch_id FROM clean_data ORDER BY processing_timestamp DESC LIMIT 1"
        
        result = pd.read_sql(query, engine)
        if len(result) > 0:
            return result.iloc[0]['batch_id']
        return None
    except Exception as e:
        logging.error(f"Failed to get latest batch_id: {e}")
        return None

def get_reference_data():
    """
    Get reference data for drift detection.
    Returns the second-to-last batch (or oldest if only one batch exists).
    """
    try:
        engine = get_db_engine()
        
        # Get distinct batches ordered by time
        query = """
            SELECT DISTINCT batch_id, MIN(ingestion_timestamp) as first_timestamp
            FROM raw_data 
            GROUP BY batch_id
            ORDER BY first_timestamp DESC
            LIMIT 2
        """
        batches = pd.read_sql(query, engine)
        
        if len(batches) >= 2:
            # Return second-to-last batch as reference
            reference_batch = batches.iloc[1]['batch_id']
        elif len(batches) == 1:
            # Only one batch, use it as reference
            reference_batch = batches.iloc[0]['batch_id']
        else:
            return None
        
        return load_from_postgres('raw_data', batch_id=reference_batch)
    except Exception as e:
        logging.error(f"Failed to get reference data: {e}")
        return None

def log_drift_result(drift_detected, drift_score, features_with_drift, 
                     reference_batch_id, current_batch_id, action_taken):
    """Log drift detection result to database."""
    try:
        engine = get_db_engine()
        
        data = {
            'timestamp': [datetime.now()],
            'drift_detected': [drift_detected],
            'drift_score': [drift_score],
            'features_with_drift': [str(features_with_drift)],
            'reference_batch_id': [reference_batch_id],
            'current_batch_id': [current_batch_id],
            'action_taken': [action_taken]
        }
        
        df = pd.DataFrame(data)
        df.to_sql('drift_history', engine, if_exists='append', index=False)
        logging.info(f"Logged drift result: detected={drift_detected}, action={action_taken}")
    except Exception as e:
        logging.error(f"Failed to log drift result: {e}")

def log_model_training(run_id, model_version, r2_score, rmse, mae, mape,
                       promoted, promotion_reason, training_samples, features_used):
    """Log model training result to database."""
    try:
        engine = get_db_engine()
        
        data = {
            'timestamp': [datetime.now()],
            'run_id': [run_id],
            'model_version': [model_version],
            'r2_score': [r2_score],
            'rmse': [rmse],
            'mae': [mae],
            'mape': [mape],
            'promoted_to_production': [promoted],
            'promotion_reason': [promotion_reason],
            'training_samples': [training_samples],
            'features_used': [str(features_used)]
        }
        
        df = pd.DataFrame(data)
        df.to_sql('model_history', engine, if_exists='append', index=False)
        logging.info(f"Logged model training: run_id={run_id}, promoted={promoted}")
    except Exception as e:
        logging.error(f"Failed to log model training: {e}")

def get_row_count(table_name):
    """Get total row count from a table."""
    try:
        engine = get_db_engine()
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        result = pd.read_sql(query, engine)
        return result.iloc[0]['count']
    except Exception as e:
        logging.error(f"Failed to get row count: {e}")
        return 0
