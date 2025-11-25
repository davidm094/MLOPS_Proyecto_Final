from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import numpy as np
import shap
import os
import logging
import joblib
import boto3
import mlflow
from io import BytesIO

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Real Estate Price Prediction API", version="3.0")

# Configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs-s3.mlops.svc:8333")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "any")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "any")
MLFLOW_BUCKET = "mlflow-artifacts"
MODEL_NAME = "real_estate_model"  # Registered model name in MLflow

# Feature configuration (must match training)
FEATURE_NAMES = ['bed', 'bath', 'acre_lot', 'house_size']

# Global variables
model = None
raw_model = None  # For SHAP (the underlying model without wrapper)
explainer = None
model_version = None
model_stage = None
model_run_id = None

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

def load_production_model():
    """
    Load the model marked as 'Production' in MLflow Model Registry.
    This is the recommended approach for production deployments.
    """
    global model, raw_model, explainer, model_version, model_stage, model_run_id
    
    try:
        # Set MLflow tracking URI
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()
        
        # Try to get the Production model from registry
        try:
            versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
            if versions:
                prod_version = versions[0]
                model_version = prod_version.version
                model_stage = prod_version.current_stage
                model_run_id = prod_version.run_id
                
                logger.info(f"Found Production model: {MODEL_NAME} v{model_version} (run: {model_run_id})")
                
                # Load model from S3 using run_id
                s3 = get_s3_client()
                
                # Try to load the wrapped model first
                try:
                    model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
                    model = joblib.load(BytesIO(model_obj['Body'].read()))
                    logger.info("Loaded wrapped model from MLflow artifacts")
                except Exception as e:
                    logger.warning(f"Could not load wrapped model: {e}")
                    # Fallback: try sklearn model
                    model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
                    model = joblib.load(BytesIO(model_obj['Body'].read()))
                
                # Try to load raw model for SHAP
                try:
                    raw_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/raw_model.pkl")
                    raw_model = joblib.load(BytesIO(raw_obj['Body'].read()))
                    logger.info("Loaded raw model for SHAP")
                except:
                    raw_model = None
                    logger.warning("Raw model not found, SHAP will use wrapped model")
                
                # Try to load pre-computed explainer
                try:
                    exp_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/explainer.pkl")
                    explainer = joblib.load(BytesIO(exp_obj['Body'].read()))
                    logger.info("Loaded pre-computed SHAP explainer")
                except Exception as e:
                    logger.warning(f"Could not load explainer: {e}")
                    # Create explainer on-demand
                    try:
                        target_model = raw_model if raw_model else model
                        if hasattr(target_model, 'model'):
                            explainer = shap.TreeExplainer(target_model.model)
                        else:
                            explainer = shap.TreeExplainer(target_model)
                        logger.info("Created SHAP explainer on-demand")
                    except Exception as e2:
                        logger.warning(f"Could not create explainer: {e2}")
                        explainer = None
                
                return True
            else:
                logger.warning(f"No Production model found for '{MODEL_NAME}'")
        except mlflow.exceptions.MlflowException as e:
            logger.warning(f"Model '{MODEL_NAME}' not registered: {e}")
        
        # Fallback: load latest model from S3 by modification time
        logger.info("Falling back to loading latest model from S3...")
        return load_latest_model_from_s3()
        
    except Exception as e:
        logger.error(f"Error loading production model: {e}")
        return load_latest_model_from_s3()

def load_latest_model_from_s3():
    """Fallback: Load the most recent model from S3 by modification time."""
    global model, raw_model, explainer, model_version, model_stage, model_run_id
    
    try:
        s3 = get_s3_client()
        
        response = s3.list_objects_v2(Bucket=MLFLOW_BUCKET)
        if 'Contents' not in response:
            logger.warning("No artifacts found in MLflow bucket")
            return False
            
        # Find run IDs with their latest modification time
        run_times = {}
        for obj in response['Contents']:
            parts = obj['Key'].split('/')
            if len(parts) >= 2 and 'model.pkl' in obj['Key'] and 'artifacts/model/' in obj['Key']:
                run_id = parts[1]
                last_modified = obj['LastModified']
                if run_id not in run_times or last_modified > run_times[run_id]:
                    run_times[run_id] = last_modified
        
        if not run_times:
            logger.warning("No run IDs with models found")
            return False
            
        # Get the most recent run by modification time
        latest_run = max(run_times.keys(), key=lambda x: run_times[x])
        model_run_id = latest_run
        model_version = "latest"
        model_stage = "Fallback"
        
        logger.info(f"Loading model from run: {model_run_id} (modified: {run_times[latest_run]})")
        
        # Load model
        model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
        model = joblib.load(BytesIO(model_obj['Body'].read()))
        logger.info("Model loaded successfully")
        
        # Try to load raw model
        try:
            raw_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/raw_model.pkl")
            raw_model = joblib.load(BytesIO(raw_obj['Body'].read()))
        except:
            raw_model = None
        
        # Create SHAP explainer
        try:
            target_model = raw_model if raw_model else model
            if hasattr(target_model, 'model'):
                explainer = shap.TreeExplainer(target_model.model)
            else:
                explainer = shap.TreeExplainer(target_model)
            logger.info("SHAP Explainer created successfully")
        except Exception as e:
            logger.warning(f"Could not create explainer: {e}")
            explainer = None
            
        return True
        
    except Exception as e:
        logger.error(f"Error loading model from S3: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    load_production_model()

class PropertyInput(BaseModel):
    bed: float = 3.0
    bath: float = 2.0
    acre_lot: float = 0.1
    house_size: float = 1500.0
    status: Optional[str] = "for_sale"
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    brokered_by: Optional[float] = None
    prev_sold_date: Optional[str] = None

class PredictionResponse(BaseModel):
    price: float
    model_version: str
    model_stage: str
    model_run_id: str
    features_used: List[str]

class ExplanationResponse(BaseModel):
    price: float
    shap_values: List[float]
    base_value: float
    feature_names: List[str]
    feature_values: List[float]
    model_version: str

class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    model_stage: str
    model_run_id: str
    model_loaded: bool
    explainer_loaded: bool

def prepare_features(input_data: PropertyInput) -> pd.DataFrame:
    """Prepare features for prediction."""
    data = {
        'bed': [float(input_data.bed) if input_data.bed else 0],
        'bath': [float(input_data.bath) if input_data.bath else 0],
        'acre_lot': [float(input_data.acre_lot) if input_data.acre_lot else 0],
        'house_size': [float(input_data.house_size) if input_data.house_size else 0],
    }
    df = pd.DataFrame(data)
    df = df.fillna(0)
    return df

@app.get("/")
def root():
    return {
        "service": "Real Estate Price Prediction API",
        "version": "3.0",
        "model_name": MODEL_NAME,
        "model_version": model_version,
        "model_stage": model_stage,
        "model_run_id": model_run_id,
        "model_loaded": model is not None,
        "explainer_loaded": explainer is not None
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "explainer_loaded": explainer is not None
    }

@app.get("/model", response_model=ModelInfo)
def get_model_info():
    """Get information about the currently loaded model."""
    return ModelInfo(
        model_name=MODEL_NAME,
        model_version=model_version or "unknown",
        model_stage=model_stage or "unknown",
        model_run_id=model_run_id or "unknown",
        model_loaded=model is not None,
        explainer_loaded=explainer is not None
    )

@app.post("/reload")
def reload_model():
    """
    Reload model from MLflow Model Registry.
    This will load the model currently marked as 'Production'.
    """
    success = load_production_model()
    if success:
        return {
            "status": "Model reloaded successfully",
            "model_name": MODEL_NAME,
            "model_version": model_version,
            "model_stage": model_stage,
            "run_id": model_run_id
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to reload model")

@app.post("/predict", response_model=PredictionResponse)
def predict(input_data: PropertyInput):
    """Predict property price using the Production model."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Call /reload first.")
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        
        return PredictionResponse(
            price=float(prediction[0]),
            model_version=model_version or "unknown",
            model_stage=model_stage or "unknown",
            model_run_id=model_run_id or "unknown",
            features_used=FEATURE_NAMES
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/explain", response_model=ExplanationResponse)
def explain(input_data: PropertyInput):
    """Get SHAP explanation for prediction."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if explainer is None:
        raise HTTPException(status_code=503, detail="SHAP Explainer not loaded")
    
    try:
        df = prepare_features(input_data)
        
        # Get prediction
        prediction = model.predict(df)
        
        # Get SHAP values
        shap_values = explainer.shap_values(df)
        
        # Handle different SHAP output formats
        if isinstance(shap_values, list):
            shap_vals = shap_values[0][0]
        else:
            shap_vals = shap_values[0]
        
        # Get base value
        if hasattr(explainer, 'expected_value'):
            if isinstance(explainer.expected_value, (list, np.ndarray)):
                base_val = float(explainer.expected_value[0]) if len(explainer.expected_value) > 0 else float(explainer.expected_value)
            else:
                base_val = float(explainer.expected_value)
        else:
            base_val = 0.0
        
        return ExplanationResponse(
            price=float(prediction[0]),
            shap_values=[float(v) for v in shap_vals],
            base_value=base_val,
            feature_names=FEATURE_NAMES,
            feature_values=[float(df[col].iloc[0]) for col in FEATURE_NAMES],
            model_version=model_version or "unknown"
        )
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
