#!/usr/bin/env python3
"""
Script to migrate data from S3 (SeaweedFS) to PostgreSQL.

This script:
1. Connects to SeaweedFS S3
2. Lists and downloads CSV files from the data-raw bucket
3. Inserts the data into PostgreSQL tables

Usage:
    python scripts/migrate_s3_to_postgres.py
    
    # Or from within a Kubernetes pod:
    kubectl exec -n mlops <scheduler-pod> -c scheduler -- python3 /path/to/migrate_s3_to_postgres.py
"""
import os
import sys
import logging
import pandas as pd
import boto3
from io import StringIO
from sqlalchemy import create_engine
from datetime import datetime
import uuid

# Configuration
S3_ENDPOINT = os.getenv('S3_ENDPOINT', 'http://seaweedfs-s3.mlops.svc:8333')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID', 'any')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'any')
BUCKET_NAME = os.getenv('S3_BUCKET', 'data-raw')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:airflow-postgres-root@postgres-postgresql.mlops.svc.cluster.local:5432/mlops_data')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_s3_client():
    """Create S3 client for SeaweedFS."""
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )


def get_db_engine():
    """Create SQLAlchemy engine for PostgreSQL."""
    return create_engine(DATABASE_URL)


def list_s3_files(s3_client, bucket, prefix=''):
    """List all CSV files in S3 bucket."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' not in response:
            logger.warning(f"No files found in bucket {bucket}")
            return []
        
        files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.csv')]
        logger.info(f"Found {len(files)} CSV files in {bucket}")
        return files
    except Exception as e:
        logger.error(f"Error listing S3 files: {e}")
        return []


def download_csv_from_s3(s3_client, bucket, key):
    """Download CSV file from S3 and return as DataFrame."""
    try:
        logger.info(f"Downloading {key} from {bucket}...")
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(obj['Body'])
        logger.info(f"Downloaded {len(df)} rows from {key}")
        return df
    except Exception as e:
        logger.error(f"Error downloading {key}: {e}")
        return None


def migrate_to_postgres(df, engine, table_name, batch_id=None):
    """Insert DataFrame into PostgreSQL table."""
    try:
        if batch_id is None:
            batch_id = f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        df_copy = df.copy()
        
        # Add metadata columns based on table
        if table_name == 'raw_data':
            df_copy['batch_id'] = batch_id
            df_copy['ingestion_timestamp'] = datetime.now()
        elif table_name == 'clean_data':
            df_copy['source_batch_id'] = batch_id
            df_copy['processing_timestamp'] = datetime.now()
        
        # Insert data
        df_copy.to_sql(table_name, engine, if_exists='append', index=False)
        logger.info(f"Inserted {len(df_copy)} rows into {table_name} (batch: {batch_id})")
        
        return True
    except Exception as e:
        logger.error(f"Error inserting into {table_name}: {e}")
        return False


def main():
    """Main migration function."""
    logger.info("="*60)
    logger.info("S3 to PostgreSQL Migration Script")
    logger.info("="*60)
    
    # Initialize clients
    try:
        s3 = get_s3_client()
        engine = get_db_engine()
        logger.info("Connected to S3 and PostgreSQL")
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        sys.exit(1)
    
    # List files
    files = list_s3_files(s3, BUCKET_NAME)
    
    if not files:
        logger.info("No files to migrate")
        return
    
    # Migrate each file
    total_rows = 0
    success_count = 0
    
    for file_key in files:
        logger.info(f"\nProcessing: {file_key}")
        
        # Download
        df = download_csv_from_s3(s3, BUCKET_NAME, file_key)
        if df is None or df.empty:
            continue
        
        # Determine table based on filename
        if 'reference' in file_key.lower():
            table_name = 'raw_data'
            batch_id = f"reference_{datetime.now().strftime('%Y%m%d')}"
        elif 'current' in file_key.lower():
            table_name = 'raw_data'
            batch_id = f"current_{datetime.now().strftime('%Y%m%d')}"
        else:
            table_name = 'raw_data'
            batch_id = f"import_{file_key.replace('/', '_').replace('.csv', '')}"
        
        # Migrate
        if migrate_to_postgres(df, engine, table_name, batch_id):
            total_rows += len(df)
            success_count += 1
    
    logger.info("\n" + "="*60)
    logger.info("Migration Complete!")
    logger.info(f"Files processed: {success_count}/{len(files)}")
    logger.info(f"Total rows migrated: {total_rows}")
    logger.info("="*60)


if __name__ == '__main__':
    main()

