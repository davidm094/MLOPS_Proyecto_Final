from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from datetime import datetime, timedelta
import logging
import os
import pandas as pd
import requests
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

# API URL for model reload
API_URL = os.getenv("API_URL", "http://api:8000")

def ingest_data(**kwargs):
    """
    Fetch data from external API and save to S3.
    """
    group_number = kwargs.get('templates_dict', {}).get('group_number')
    day = kwargs.get('templates_dict', {}).get('day')
    
    if not group_number:
        dag_run = kwargs.get('dag_run')
        if dag_run and dag_run.conf:
            group_number = dag_run.conf.get('group_number', '5')
            day = dag_run.conf.get('day', 'Tuesday')
        else:
            group_number = '5'
            day = 'Tuesday'
    
    logging.info(f"Starting ingestion for Group: {group_number}, Day: {day}")
    df = fetch_data(group_number=group_number, day=day)
    
    # Save current batch to S3
    s3_path = save_raw_data(df, CURRENT_BATCH_KEY)
    logging.info(f"Data saved to {s3_path}")
    logging.info(f"Ingested {len(df)} records")
    return CURRENT_BATCH_KEY

def check_drift(**kwargs):
    """
    Compare current data with reference data to detect drift.
    Returns 'train_model' if drift detected or first run, 'skip_training' otherwise.
    """
    try:
        ti = kwargs['ti']
        current_key = ti.xcom_pull(task_ids='ingest_data')
        logging.info(f"Loading current data from {current_key}")
        current_df = load_raw_data(current_key)
        
        if current_df is None or current_df.empty:
            raise ValueError("Could not load current data from S3")

        # Load reference data (previous batch or baseline)
        reference_df = load_raw_data(REFERENCE_KEY)
        
        if reference_df is None or reference_df.empty:
            logging.info("="*50)
            logging.info("FIRST RUN - No reference data found")
            logging.info("Saving current batch as reference and proceeding to training")
            logging.info("="*50)
            save_raw_data(current_df, REFERENCE_KEY)
            return 'train_model'
        
        # Clean both for drift detection
        current_clean = clean_data(current_df)
        reference_clean = clean_data(reference_df)
        
        logging.info(f"Current data: {len(current_clean)} samples")
        logging.info(f"Reference data: {len(reference_clean)} samples")

        has_drift = detect_drift(reference_clean, current_clean)
        
        if has_drift:
            logging.info("="*50)
            logging.info("DRIFT DETECTED!")
            logging.info("Data distribution has changed significantly")
            logging.info("Proceeding to model retraining...")
            logging.info("="*50)
            return 'train_model'
        else:
            logging.info("="*50)
            logging.info("NO DRIFT DETECTED")
            logging.info("Data distribution is stable")
            logging.info("Skipping model retraining")
            logging.info("="*50)
            return 'skip_training'
            
    except Exception as e:
        logging.error(f"Drift Check Failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        # On error, default to training (safer)
        return 'train_model'

def train_model(**kwargs):
    """
    Train a new model and register in MLflow.
    Model is automatically promoted to Production if it meets quality thresholds.
    """
    ti = kwargs['ti']
    current_key = ti.xcom_pull(task_ids='ingest_data')
    logging.info(f"Loading training data from {current_key}")
    df = load_raw_data(current_key)
    
    if df is None or df.empty:
        raise ValueError("Could not load training data from S3")
    
    logging.info(f"Training with {len(df)} samples")
    
    # Set MLflow tracking URI
    mlflow.set_tracking_uri("http://mlflow:5000")
    
    # Train and log model (includes automatic promotion if metrics are good)
    run_id, rmse = train_and_log_model(df)
    
    logging.info(f"Training completed. Run ID: {run_id}, RMSE: ${rmse:,.0f}")
    
    # Update reference data after successful training
    save_raw_data(df, REFERENCE_KEY)
    logging.info("Reference data updated with current batch")
    
    return run_id

def reload_api(**kwargs):
    """
    Notify the API to reload the model from MLflow.
    This ensures the API uses the newly promoted Production model.
    """
    ti = kwargs['ti']
    run_id = ti.xcom_pull(task_ids='train_model')
    
    logging.info("="*50)
    logging.info("RELOADING API MODEL")
    logging.info("="*50)
    
    try:
        response = requests.post(f"{API_URL}/reload", timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            logging.info("✅ API model reloaded successfully!")
            logging.info(f"  Model Version: {result.get('model_version')}")
            logging.info(f"  Model Stage: {result.get('model_stage')}")
            logging.info(f"  Run ID: {result.get('run_id')}")
        else:
            logging.warning(f"⚠️ API reload returned status {response.status_code}")
            logging.warning(f"  Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        logging.warning("⚠️ Could not connect to API for reload")
        logging.warning("  The API will load the new model on next restart")
    except Exception as e:
        logging.warning(f"⚠️ API reload failed: {e}")
        logging.warning("  The API will load the new model on next restart")
    
    return "reload_completed"

def skip_training_task(**kwargs):
    """
    Log that training was skipped due to no drift.
    """
    logging.info("Training skipped - no data drift detected")
    logging.info("Current model remains in production")
    return "skipped"

# ============================================
# DAG DEFINITION
# ============================================
with DAG(
    'mlops_full_pipeline',
    default_args=default_args,
    description='End-to-End MLOps Pipeline with Drift Detection and Auto-Promotion',
    schedule_interval=None,  # Triggered manually or by external scheduler
    catchup=False,
    tags=['mlops', 'ml', 'training', 'drift-detection'],
) as dag:
    
    # Documentation
    dag.doc_md = """
    ## MLOps Full Pipeline
    
    This DAG implements a complete MLOps workflow:
    
    1. **Data Ingestion**: Fetch new data from external API
    2. **Drift Detection**: Compare new data with reference data
    3. **Conditional Training**: Only retrain if drift is detected
    4. **Auto-Promotion**: Promote model to Production if metrics meet thresholds
    5. **API Reload**: Notify API to load the new model
    
    ### Trigger Parameters
    
    You can pass parameters when triggering:
    ```json
    {
        "group_number": "5",
        "day": "Tuesday"
    }
    ```
    
    ### Thresholds
    
    - Minimum R² for promotion: 0.35
    - Maximum RMSE for promotion: $700,000
    """

    start = DummyOperator(task_id='start')

    ingest = PythonOperator(
        task_id='ingest_data',
        python_callable=ingest_data,
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
        python_callable=train_model,
        provide_context=True
    )
    
    reload_api_task = PythonOperator(
        task_id='reload_api',
        python_callable=reload_api,
        provide_context=True,
        trigger_rule='all_success'
    )
    
    skip_training = PythonOperator(
        task_id='skip_training',
        python_callable=skip_training_task,
        provide_context=True
    )

    end = DummyOperator(
        task_id='end_pipeline',
        trigger_rule='none_failed_min_one_success'
    )

    # Pipeline flow
    start >> ingest >> drift_check
    
    # If drift detected -> train -> reload API -> end
    drift_check >> train >> reload_api_task >> end
    
    # If no drift -> skip training -> end
    drift_check >> skip_training >> end
