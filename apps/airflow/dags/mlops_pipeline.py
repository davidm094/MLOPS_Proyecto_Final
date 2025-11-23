from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from datetime import datetime, timedelta
import logging
import os
import pandas as pd
from src.data_loader import fetch_data, save_raw_data
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

DATA_PATH = "/tmp/data" # In production this should be shared volume or S3
os.makedirs(DATA_PATH, exist_ok=True)

def ingest_data(**kwargs):
    # Fetch data
    group_id = kwargs.get('dag_run').conf.get('group_id', '1')
    df = fetch_data(group_id)
    
    # Save current batch
    current_path = f"{DATA_PATH}/current_batch.csv"
    save_raw_data(df, current_path)
    return current_path

def check_drift(**kwargs):
    ti = kwargs['ti']
    current_path = ti.xcom_pull(task_ids='ingest_data')
    current_df = pd.read_csv(current_path)
    
    # Load reference data (previous batch or baseline)
    reference_path = f"{DATA_PATH}/reference.csv"
    
    if not os.path.exists(reference_path):
        logging.info("No reference data found. Treating as initial run.")
        # Save this as reference for next time
        save_raw_data(current_df, reference_path)
        return 'train_model'
        
    reference_df = pd.read_csv(reference_path)
    
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

def train_process(**kwargs):
    ti = kwargs['ti']
    current_path = ti.xcom_pull(task_ids='ingest_data')
    df = pd.read_csv(current_path)
    
    # Clean
    df_clean = clean_data(df)
    
    # Train
    mlflow.set_tracking_uri("http://mlflow-service:5000") # Service name in K8s
    run_id, rmse = train_and_log_model(df_clean)
    
    # Update reference data since we retrained
    save_raw_data(df, f"{DATA_PATH}/reference.csv")
    
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
        provide_context=True
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

