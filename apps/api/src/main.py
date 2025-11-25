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
from io import BytesIO

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Real Estate Price Prediction API", version="2.0")

# S3/MLflow Configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs-s3.mlops.svc:8333")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "any")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "any")
MLFLOW_BUCKET = "mlflow-artifacts"

# Feature configuration (must match training)
FEATURE_NAMES = ['bed', 'bath', 'acre_lot', 'house_size']

# Global variables
model = None
explainer = None
model_run_id = None

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

def load_latest_model():
    """Load the latest model and explainer from S3/MLflow artifacts."""
    global model, explainer, model_run_id
    
    try:
        s3 = get_s3_client()
        
        # List all objects to find the latest run
        response = s3.list_objects_v2(Bucket=MLFLOW_BUCKET)
        if 'Contents' not in response:
            logger.warning("No artifacts found in MLflow bucket")
            return False
            
        # Find unique run IDs and get the latest one
        run_ids = set()
        for obj in response['Contents']:
            parts = obj['Key'].split('/')
            if len(parts) >= 2:
                run_ids.add(parts[1])  # Format: experiment_id/run_id/artifacts/...
        
        if not run_ids:
            logger.warning("No run IDs found")
            return False
            
        # Get the most recent run (by checking for model.pkl existence)
        latest_run = None
        for run_id in run_ids:
            try:
                s3.head_object(Bucket=MLFLOW_BUCKET, Key=f"2/{run_id}/artifacts/model/model.pkl")
                latest_run = run_id
            except:
                continue
        
        if not latest_run:
            logger.warning("No valid model found")
            return False
            
        model_run_id = latest_run
        logger.info(f"Loading model from run: {model_run_id}")
        
        # Load model
        model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
        model = joblib.load(BytesIO(model_obj['Body'].read()))
        logger.info("Model loaded successfully")
        
        # Load explainer
        try:
            explainer_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/explainer.pkl")
            explainer = joblib.load(BytesIO(explainer_obj['Body'].read()))
            logger.info("SHAP Explainer loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load explainer: {e}. SHAP explanations will be unavailable.")
            explainer = None
            
        return True
        
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    load_latest_model()

class PropertyInput(BaseModel):
    bed: float = 3.0
    bath: float = 2.0
    acre_lot: float = 0.1
    house_size: float = 1500.0
    # Optional fields (not used in current model but kept for API compatibility)
    status: Optional[str] = "for_sale"
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    brokered_by: Optional[float] = None
    prev_sold_date: Optional[str] = None

class PredictionResponse(BaseModel):
    price: float
    model_run_id: str
    features_used: List[str]

class ExplanationResponse(BaseModel):
    price: float
    shap_values: List[float]
    base_value: float
    feature_names: List[str]
    feature_values: List[float]

def prepare_features(input_data: PropertyInput) -> pd.DataFrame:
    """Prepare features for prediction."""
    data = {
        'bed': [float(input_data.bed) if input_data.bed else 0],
        'bath': [float(input_data.bath) if input_data.bath else 0],
        'acre_lot': [float(input_data.acre_lot) if input_data.acre_lot else 0],
        'house_size': [float(input_data.house_size) if input_data.house_size else 0],
    }
    df = pd.DataFrame(data)
    # Handle NaN
    df = df.fillna(0)
    return df

@app.get("/")
def root():
    return {
        "service": "Real Estate Price Prediction API",
        "version": "2.0",
        "model_loaded": model is not None,
        "explainer_loaded": explainer is not None,
        "model_run_id": model_run_id
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "explainer_loaded": explainer is not None
    }

@app.post("/reload")
def reload_model():
    """Reload model from S3."""
    success = load_latest_model()
    if success:
        return {"status": "Model reloaded successfully", "run_id": model_run_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to reload model")

@app.post("/predict", response_model=PredictionResponse)
def predict(input_data: PropertyInput):
    """Predict property price."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Call /reload first.")
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        
        return PredictionResponse(
            price=float(prediction[0]),
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
            shap_vals = shap_values[0][0]  # For multi-output
        else:
            shap_vals = shap_values[0]  # Single output
        
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
            feature_values=[float(df[col].iloc[0]) for col in FEATURE_NAMES]
        )
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
