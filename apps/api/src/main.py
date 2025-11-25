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

app = FastAPI(title="Real Estate Price Prediction API", version="4.0")

# Configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs-s3.mlops.svc:8333")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "any")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "any")
MLFLOW_BUCKET = "mlflow-artifacts"
MODEL_NAME = "real_estate_model"

# Feature configuration
NUMERIC_FEATURES = ['bed', 'bath', 'acre_lot', 'house_size']
ENGINEERED_FEATURES = ['bed_bath_ratio', 'sqft_per_bed', 'total_rooms', 'is_sold']
CATEGORICAL_FEATURES = ['state']
ALL_FEATURES = NUMERIC_FEATURES + ENGINEERED_FEATURES + CATEGORICAL_FEATURES

# Global variables
model = None
raw_model = None
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
    """Load the model marked as 'Production' in MLflow Model Registry."""
    global model, raw_model, explainer, model_version, model_stage, model_run_id
    
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()
        
        # Get Production model
        try:
            versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
            if versions:
                prod_version = versions[0]
                model_version = prod_version.version
                model_stage = prod_version.current_stage
                model_run_id = prod_version.run_id
                
                logger.info(f"Found Production model: {MODEL_NAME} v{model_version} (run: {model_run_id})")
                
                # Load using mlflow.sklearn (handles Pipeline correctly)
                model_uri = f"runs:/{model_run_id}/model"
                model = mlflow.sklearn.load_model(model_uri)
                logger.info("Loaded sklearn model from MLflow")
                
                # Try to load raw model for SHAP
                try:
                    s3 = get_s3_client()
                    raw_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/raw_model.pkl")
                    raw_model = joblib.load(BytesIO(raw_obj['Body'].read()))
                    explainer = shap.TreeExplainer(raw_model)
                    logger.info("Loaded raw model and created SHAP explainer")
                except Exception as e:
                    logger.warning(f"Could not load raw model for SHAP: {e}")
                    raw_model = None
                    explainer = None
                
                return True
            else:
                logger.warning(f"No Production model found for '{MODEL_NAME}'")
        except Exception as e:
            logger.warning(f"Error loading from registry: {e}")
        
        # Fallback to latest S3 model
        return load_latest_model_from_s3()
        
    except Exception as e:
        logger.error(f"Error loading production model: {e}")
        return False

def load_latest_model_from_s3():
    """Fallback: Load latest model from S3."""
    global model, raw_model, explainer, model_version, model_stage, model_run_id
    
    try:
        s3 = get_s3_client()
        response = s3.list_objects_v2(Bucket=MLFLOW_BUCKET)
        
        if 'Contents' not in response:
            return False
        
        # Find latest model.pkl
        run_times = {}
        for obj in response['Contents']:
            if 'model/model.pkl' in obj['Key']:
                parts = obj['Key'].split('/')
                if len(parts) >= 2:
                    run_id = parts[1]
                    run_times[run_id] = obj['LastModified']
        
        if not run_times:
            return False
        
        latest_run = max(run_times.keys(), key=lambda x: run_times[x])
        model_run_id = latest_run
        model_version = "latest"
        model_stage = "Fallback"
        
        # Load model
        model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
        model = joblib.load(BytesIO(model_obj['Body'].read()))
        logger.info(f"Loaded model from S3: {model_run_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading from S3: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    load_production_model()

class PropertyInput(BaseModel):
    bed: float = 3.0
    bath: float = 2.0
    acre_lot: float = 0.1
    house_size: float = 1500.0
    state: str = "California"
    status: Optional[str] = "for_sale"
    city: Optional[str] = None
    zip_code: Optional[str] = None

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
    features: List[str]

def prepare_features(input_data: PropertyInput) -> pd.DataFrame:
    """Prepare all features including engineered ones."""
    bed = float(input_data.bed) if input_data.bed else 0
    bath = float(input_data.bath) if input_data.bath else 0
    acre_lot = float(input_data.acre_lot) if input_data.acre_lot else 0
    house_size = float(input_data.house_size) if input_data.house_size else 0
    state = input_data.state if input_data.state else "California"
    is_sold = 1 if input_data.status == "sold" else 0
    
    data = {
        'bed': [bed],
        'bath': [bath],
        'acre_lot': [acre_lot],
        'house_size': [house_size],
        'bed_bath_ratio': [bed / (bath + 0.1)],
        'sqft_per_bed': [house_size / (bed + 0.1)],
        'total_rooms': [bed + bath],
        'is_sold': [is_sold],
        'state': [state]
    }
    return pd.DataFrame(data)

@app.get("/")
def root():
    return {
        "service": "Real Estate Price Prediction API",
        "version": "4.0",
        "model_name": MODEL_NAME,
        "model_version": model_version,
        "model_stage": model_stage,
        "model_run_id": model_run_id,
        "model_loaded": model is not None,
        "explainer_loaded": explainer is not None,
        "features": ALL_FEATURES
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": model is not None
    }

@app.get("/model", response_model=ModelInfo)
def get_model_info():
    return ModelInfo(
        model_name=MODEL_NAME,
        model_version=model_version or "unknown",
        model_stage=model_stage or "unknown",
        model_run_id=model_run_id or "unknown",
        model_loaded=model is not None,
        explainer_loaded=explainer is not None,
        features=ALL_FEATURES
    )

@app.post("/reload")
def reload_model():
    """Reload model from MLflow Model Registry."""
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
    """Predict property price."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        
        return PredictionResponse(
            price=float(prediction[0]),
            model_version=model_version or "unknown",
            model_stage=model_stage or "unknown",
            model_run_id=model_run_id or "unknown",
            features_used=ALL_FEATURES
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
        raise HTTPException(status_code=503, detail="SHAP Explainer not available for this model")
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        
        # Get preprocessed features for SHAP
        # Note: SHAP values are on log scale since raw_model works on log-transformed target
        preprocessor = model.named_steps['preprocessor']
        X_transformed = preprocessor.transform(df)
        
        shap_values = explainer.shap_values(X_transformed)
        
        if isinstance(shap_values, list):
            shap_vals = shap_values[0][0]
        else:
            shap_vals = shap_values[0]
        
        base_val = float(explainer.expected_value) if hasattr(explainer, 'expected_value') else 0.0
        if isinstance(base_val, np.ndarray):
            base_val = float(base_val[0])
        
        # Get feature names after transformation
        num_features = ['bed', 'bath', 'acre_lot', 'house_size', 'bed_bath_ratio', 'sqft_per_bed', 'total_rooms', 'is_sold']
        cat_features = preprocessor.named_transformers_['cat'].get_feature_names_out(['state']).tolist()
        all_features = num_features + cat_features
        
        return ExplanationResponse(
            price=float(prediction[0]),
            shap_values=[float(v) for v in shap_vals],
            base_value=base_val,
            feature_names=all_features[:len(shap_vals)],
            feature_values=[float(X_transformed[0][i]) for i in range(min(len(shap_vals), X_transformed.shape[1]))],
            model_version=model_version or "unknown"
        )
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/states")
def get_states():
    """Get list of supported states."""
    states = [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
        "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
        "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
        "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
        "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
        "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
        "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
        "Washington", "West Virginia", "Wisconsin", "Wyoming", "Puerto Rico", "Virgin Islands"
    ]
    return {"states": states}
