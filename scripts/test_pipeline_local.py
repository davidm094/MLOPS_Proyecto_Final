import sys
import os
import logging
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add src to path to import modules
# Assuming script is run from project root or scripts folder
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DAGS_FOLDER = os.path.join(PROJECT_ROOT, 'apps/airflow/dags')
sys.path.append(DAGS_FOLDER)

try:
    from src.data_loader import fetch_data
    from src.preprocessing import clean_data
    from src.drift_detection import detect_drift
    from src.model_training import train_and_log_model
except ImportError as e:
    logging.error(f"Import Error: {e}. Make sure PYTHONPATH includes apps/airflow/dags")
    # Fallback for running inside pod where structure might differ
    sys.path.append('/opt/airflow/dags/repo/apps/airflow/dags')
    try:
        from src.data_loader import fetch_data
        from src.preprocessing import clean_data
        from src.drift_detection import detect_drift
        from src.model_training import train_and_log_model
    except ImportError as e2:
        logging.error(f"Second Import Attempt Failed: {e2}")
        sys.exit(1)

def test_ingestion(group_number, day):
    logging.info(f"=== TESTING INGESTION (Group: {group_number}, Day: {day}) ===")
    try:
        # Note: fetch_data might have sleep logic on failure, be aware
        df = fetch_data(group_number=group_number, day=day)
        logging.info(f"Successfully fetched {len(df)} rows")
        logging.info(f"Columns: {df.columns.tolist()}")
        logging.info(f"Sample Data:\n{df.head(2)}")
        return df
    except Exception as e:
        logging.error(f"Ingestion Failed: {e}")
        return None

def test_drift(current_df):
    logging.info("=== TESTING DRIFT DETECTION ===")
    # Simulate reference data (just a copy or subset)
    ref_df = current_df.copy()
    
    # Clean both
    try:
        current_clean = clean_data(current_df)
        ref_clean = clean_data(ref_df)
        logging.info("Data Cleaning Successful")
        
        has_drift = detect_drift(ref_clean, current_clean)
        logging.info(f"Drift Check Result: {has_drift}")
        return True
    except Exception as e:
        logging.error(f"Drift Detection Failed: {e}")
        return False

def test_training(df):
    logging.info("=== TESTING TRAINING ===")
    
    try:
        # Clean data first
        df_clean = clean_data(df)
        
        logging.info("Starting Training...")
        # Ensure we are pointing to a valid MLflow URI
        # Inside K8s pod, it should be http://mlflow:5000
        # If running local with port-forward, http://localhost:5000
        
        # Check env var or set default
        mlflow_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
        logging.info(f"Using MLflow URI: {mlflow_uri}")
        
        import mlflow
        mlflow.set_tracking_uri(mlflow_uri)
        
        run_id, rmse = train_and_log_model(df_clean, experiment_name="test_experiment_manual")
        logging.info(f"Training Successful. Run ID: {run_id}, RMSE: {rmse}")
        return True
    except Exception as e:
        logging.error(f"Training Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Configuration
    GROUP = 5
    DAYS_TO_TEST = ["Tuesday", "Wednesday"]
    
    success = False
    df = None
    
    # 1. Ingestion Loop
    for day in DAYS_TO_TEST:
        logging.info(f"--- Attempting Day: {day} ---")
        df = test_ingestion(GROUP, day)
        if df is not None and not df.empty:
            success = True
            break
        else:
            logging.warning(f"Failed to get data for {day}")
    
    if success and df is not None:
        # 2. Drift
        test_drift(df)
        
        # 3. Training
        test_training(df)
    else:
        logging.error("FATAL: Could not ingest data for any configured day.")
        sys.exit(1)

