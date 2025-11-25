from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from datetime import datetime, timedelta
import logging
import os
import pandas as pd
from src.data_loader import fetch_data, save_raw_data, load_raw_data
from src.preprocessing import clean_data
from src.drift_detection import detect_drift
from src.model_training import train_and_log_model
import mlflow

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# S3 keys
CURRENT_BATCH_KEY = "current_batch.csv"
REFERENCE_KEY = "reference.csv"

def ingest_data(**kwargs):
    # Fetch data
    # Try to get params from templates_dict, then dag_run conf, then default
    group_number = kwargs.get('templates_dict', {}).get('group_number')
    day = kwargs.get('templates_dict', {}).get('day')
    
    if not group_number:
        group_number = kwargs.get('dag_run').conf.get('group_number', '5')
    if not day:
        day = kwargs.get('dag_run').conf.get('day', 'Tuesday')
    
    logging.info(f"Starting ingestion for Group: {group_number}, Day: {day}")
    df = fetch_data(group_number=group_number, day=day)
    
    # Save current batch to S3
    s3_path = save_raw_data(df, CURRENT_BATCH_KEY)
    logging.info(f"Data saved to {s3_path}")
    return CURRENT_BATCH_KEY

def check_drift(**kwargs):
    try:
        ti = kwargs['ti']
        current_key = ti.xcom_pull(task_ids='ingest_data')
        logging.info(f"Loading current data from {current_key}")
        current_df = load_raw_data(current_key)
        
        if current_df is None:
            raise ValueError("Could not load current data from S3")

        # Load reference data (previous batch or baseline)
        reference_df = load_raw_data(REFERENCE_KEY)
        
        if reference_df is None:
            logging.info("No reference data found in S3. Treating as initial run.")
            # Save this as reference for next time
            save_raw_data(current_df, REFERENCE_KEY)
            return 'train_model'
        
        # Clean both for drift detection (to handle types)
        current_clean = clean_data(current_df)
        reference_clean = clean_data(reference_df)

        has_drift = detect_drift(reference_clean, current_clean)
        
        if has_drift:
            logging.info("Drift detected! Proceeding to training.")
            # Update reference? Maybe after successful training.
            return 'train_model'
        else:
            logging.info("No drift detected. Skipping training.")
            return 'end_pipeline'
    except Exception as e:
        logging.error(f"Drift Check Failed: {e}")
        try:
            import time
            with open("/tmp/drift_error.log", "w") as f:
                f.write(str(e))
            logging.info("Sleeping for 600 seconds for debugging...")
            time.sleep(600)
        except:
            pass
        raise

def train_process(**kwargs):
    ti = kwargs['ti']
    current_key = ti.xcom_pull(task_ids='ingest_data')
    logging.info(f"Loading current data from {current_key}")
    df = load_raw_data(current_key)
    
    if df is None:
        raise ValueError("Could not load training data from S3")
    
    # Clean
    df_clean = clean_data(df)
    
    # Train
    # Use the correct MLflow service DNS
    mlflow.set_tracking_uri("http://mlflow:5000") 
    run_id, rmse = train_and_log_model(df_clean)
    
    # Update reference data since we retrained (establish new baseline)
    save_raw_data(df, REFERENCE_KEY)
    
    return run_id

with DAG(
    'mlops_full_pipeline',
    default_args=default_args,
    description='End-to-End MLOps Pipeline',
    schedule_interval=None, # Triggered manually or by API
) as dag:

    start = DummyOperator(task_id='start')

    ingest = PythonOperator(
        task_id='ingest_data',
        python_callable=ingest_data,
        op_kwargs={'dag_run': '{{ dag_run }}'}, 
        provide_context=True,
        templates_dict={'group_number': '5', 'day': 'Tuesday'} 
    )

    drift_check = BranchPythonOperator(
        task_id='check_drift',
        python_callable=check_drift,
        provide_context=True
    )

    train = PythonOperator(
        task_id='train_model',
        python_callable=train_process,
        provide_context=True
    )

    end = DummyOperator(task_id='end_pipeline')

    start >> ingest >> drift_check
    drift_check >> train >> end
    drift_check >> end
