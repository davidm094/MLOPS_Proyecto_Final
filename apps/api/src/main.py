from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
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

# Global variables
model = None
state_means = None  # For state encoding
explainer = None
model_version = None
model_stage = None
model_run_id = None
feature_names = None

# Default state mean for unknown states
DEFAULT_STATE_MEAN = 1_000_000

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

def load_production_model():
    """Load the model marked as 'Production' in MLflow Model Registry."""
    global model, state_means, explainer, model_version, model_stage, model_run_id, feature_names
    
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()
        
        # Get Production model from registry
        try:
            versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
            if versions:
                prod_version = versions[0]
                model_version = prod_version.version
                model_stage = prod_version.current_stage
                model_run_id = prod_version.run_id
                
                logger.info(f"Found Production model: {MODEL_NAME} v{model_version} (run: {model_run_id})")
                
                s3 = get_s3_client()
                
                # Load model
                try:
                    # Try sklearn model path first
                    model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
                    model = joblib.load(BytesIO(model_obj['Body'].read()))
                    logger.info("Model loaded successfully")
                except Exception as e:
                    logger.error(f"Could not load model: {e}")
                    return False
                
                # Load state_means for feature engineering
                try:
                    state_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/state_means.pkl")
                    state_means = joblib.load(BytesIO(state_obj['Body'].read()))
                    logger.info(f"Loaded state_means with {len(state_means)} states")
                except Exception as e:
                    logger.warning(f"Could not load state_means: {e}. Using defaults.")
                    state_means = {}
                
                # Load feature names
                try:
                    feat_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/features.txt")
                    feature_names = feat_obj['Body'].read().decode('utf-8').strip().split('\n')
                    logger.info(f"Feature names: {feature_names}")
                except Exception as e:
                    logger.warning(f"Could not load feature names: {e}")
                    feature_names = ['bed', 'bath', 'acre_lot', 'house_size']
                
                # Create SHAP explainer (if possible)
                try:
                    explainer = shap.TreeExplainer(model)
                    logger.info("SHAP Explainer created")
                except Exception as e:
                    logger.warning(f"Could not create explainer: {e}")
                    explainer = None
                
                return True
            else:
                logger.warning(f"No Production model found for '{MODEL_NAME}'")
        except mlflow.exceptions.MlflowException as e:
            logger.warning(f"Model '{MODEL_NAME}' not registered: {e}")
        
        # Fallback to latest S3 model
        return load_latest_model_from_s3()
        
    except Exception as e:
        logger.error(f"Error loading production model: {e}")
        return load_latest_model_from_s3()

def load_latest_model_from_s3():
    """Fallback: Load the most recent model from S3."""
    global model, state_means, explainer, model_version, model_stage, model_run_id, feature_names
    
    try:
        s3 = get_s3_client()
        response = s3.list_objects_v2(Bucket=MLFLOW_BUCKET)
        
        if 'Contents' not in response:
            logger.warning("No artifacts found in MLflow bucket")
            return False
        
        # Find most recent model
        run_times = {}
        for obj in response['Contents']:
            parts = obj['Key'].split('/')
            if len(parts) >= 2 and 'model.pkl' in obj['Key'] and 'artifacts/model/' in obj['Key']:
                run_id = parts[1]
                last_modified = obj['LastModified']
                if run_id not in run_times or last_modified > run_times[run_id]:
                    run_times[run_id] = last_modified
        
        if not run_times:
            return False
        
        latest_run = max(run_times.keys(), key=lambda x: run_times[x])
        model_run_id = latest_run
        model_version = "latest"
        model_stage = "Fallback"
        
        logger.info(f"Loading model from run: {model_run_id}")
        
        model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/model/model.pkl")
        model = joblib.load(BytesIO(model_obj['Body'].read()))
        
        # Try to load state_means
        try:
            state_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/state_means.pkl")
            state_means = joblib.load(BytesIO(state_obj['Body'].read()))
        except:
            state_means = {}
        
        # Try to load feature names
        try:
            feat_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"2/{model_run_id}/artifacts/features.txt")
            feature_names = feat_obj['Body'].read().decode('utf-8').strip().split('\n')
        except:
            feature_names = ['bed', 'bath', 'acre_lot', 'house_size']
        
        try:
            explainer = shap.TreeExplainer(model)
        except:
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
    acre_lot: float = 0.25
    house_size: float = 1800.0
    state: Optional[str] = "California"
    status: Optional[str] = "for_sale"
    city: Optional[str] = None
    zip_code: Optional[str] = None

class PredictionResponse(BaseModel):
    price: float
    model_version: str
    model_stage: str
    model_run_id: str
    features_used: List[str]
    input_summary: Dict[str, float]

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
    available_states: List[str]
    feature_names: List[str]

def prepare_features(input_data: PropertyInput) -> pd.DataFrame:
    """Prepare all features including engineered ones."""
    bed = float(input_data.bed) if input_data.bed else 3.0
    bath = float(input_data.bath) if input_data.bath else 2.0
    acre_lot = float(input_data.acre_lot) if input_data.acre_lot else 0.25
    house_size = float(input_data.house_size) if input_data.house_size else 1800.0
    
    # Get state mean (target encoding)
    state = input_data.state or "California"
    if state_means and state in state_means:
        state_price_mean = state_means[state]
    elif state_means:
        state_price_mean = np.mean(list(state_means.values()))
    else:
        state_price_mean = DEFAULT_STATE_MEAN
    
    # Status encoding
    is_sold = 1 if input_data.status == "sold" else 0
    
    # Feature engineering
    data = {
        'bed': bed,
        'bath': bath,
        'acre_lot': acre_lot,
        'house_size': house_size,
        'state_price_mean': state_price_mean,
        'is_sold': is_sold,
        'bed_bath_interaction': bed * bath,
        'size_per_bed': house_size / (bed + 1),
        'size_per_bath': house_size / (bath + 1),
        'total_rooms': bed + bath,
        'lot_to_house_ratio': acre_lot * 43560 / (house_size + 1)
    }
    
    # Only include features the model expects
    if feature_names:
        data = {k: v for k, v in data.items() if k in feature_names}
    
    return pd.DataFrame([data])

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
        "features": feature_names
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
        explainer_loaded=explainer is not None,
        available_states=list(state_means.keys()) if state_means else [],
        feature_names=feature_names or []
    )

@app.get("/states")
def get_states():
    """Get list of available states and their average prices."""
    if state_means:
        sorted_states = sorted(state_means.items(), key=lambda x: x[1], reverse=True)
        return {
            "states": [{"state": k, "avg_price": v} for k, v in sorted_states]
        }
    return {"states": []}

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
            "run_id": model_run_id,
            "features": feature_names
        }
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
            model_version=model_version or "unknown",
            model_stage=model_stage or "unknown",
            model_run_id=model_run_id or "unknown",
            features_used=list(df.columns),
            input_summary={
                "bed": input_data.bed,
                "bath": input_data.bath,
                "acre_lot": input_data.acre_lot,
                "house_size": input_data.house_size,
                "state": input_data.state or "California"
            }
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
        raise HTTPException(status_code=503, detail="SHAP Explainer not available for this model type")
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        
        # Get SHAP values
        shap_values = explainer.shap_values(df)
        
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
            feature_names=list(df.columns),
            feature_values=[float(df[col].iloc[0]) for col in df.columns],
            model_version=model_version or "unknown"
        )
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch_predict")
def batch_predict(properties: List[PropertyInput]):
    """Predict prices for multiple properties."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    results = []
    for prop in properties:
        try:
            df = prepare_features(prop)
            pred = model.predict(df)[0]
            results.append({
                "input": {
                    "bed": prop.bed,
                    "bath": prop.bath,
                    "house_size": prop.house_size,
                    "state": prop.state
                },
                "price": float(pred)
            })
        except Exception as e:
            results.append({
                "input": {"bed": prop.bed, "bath": prop.bath},
                "error": str(e)
            })
    
    return {"predictions": results, "model_version": model_version}
