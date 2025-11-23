from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mlflow.sklearn
import pandas as pd
import shap
import os
import logging
import joblib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Real Estate Price Prediction API")

# MLflow Setup
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-service:5000")
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

MODEL_NAME = "real_estate_price_prediction"
STAGE = "Production"

# Global variables to hold model and explainer
model = None
explainer = None

def load_artifacts():
    global model, explainer
    try:
        model_uri = f"models:/{MODEL_NAME}/{STAGE}"
        logger.info(f"Loading model from {model_uri}...")
        model = mlflow.sklearn.load_model(model_uri)
        
        # Load Explainer
        # We need to find the run_id of the production model to get the artifact
        client = mlflow.tracking.MlflowClient()
        versions = client.get_latest_versions(MODEL_NAME, stages=[STAGE])
        if versions:
            run_id = versions[0].run_id
            local_path = client.download_artifacts(run_id, "shap_explainer.pkl", ".")
            explainer = joblib.load(local_path)
            logger.info("Explainer loaded successfully.")
        else:
            logger.warning("No production model found.")
            
    except Exception as e:
        logger.error(f"Error loading artifacts: {e}")

@app.on_event("startup")
async def startup_event():
    load_artifacts()

class PropertyInput(BaseModel):
    brokered_by: float = None # Categorical encoded? Check dataset. Assuming raw values from description were categorical but passed as float/string
    status: str
    bed: float
    bath: float
    acre_lot: float
    city: str
    state: str
    zip_code: str
    house_size: float
    prev_sold_date: str = None
    
    # Add other fields if necessary or allow extra
    class Config:
        extra = "ignore"

def preprocess_input(input_data: PropertyInput) -> pd.DataFrame:
    # Convert to DataFrame
    data = input_data.dict()
    df = pd.DataFrame([data])
    
    # Apply same cleaning as training
    # Numerical conversions
    for col in ['bed', 'bath', 'acre_lot', 'house_size']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    return df

@app.post("/predict")
def predict(input_data: PropertyInput):
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        df = preprocess_input(input_data)
        prediction = model.predict(df)
        return {"price": prediction[0], "model_version": STAGE}
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/explain")
def explain(input_data: PropertyInput):
    if not model or not explainer:
        raise HTTPException(status_code=503, detail="Model or Explainer not loaded")
        
    try:
        df = preprocess_input(input_data)
        
        # Transform using the pipeline's preprocessor
        # Model is a Pipeline
        preprocessor = model.named_steps['preprocessor']
        transformed_data = preprocessor.transform(df)
        
        # Calculate SHAP
        shap_values = explainer.shap_values(transformed_data)
        
        # We also need the feature names for the visualization
        # Getting feature names from OneHotEncoder is tricky but possible
        # For now, return the values and the base value
        
        return {
            "shap_values": shap_values[0].tolist(),
            "base_value": explainer.expected_value[0] if isinstance(explainer.expected_value, list) else explainer.expected_value,
            "feature_names": "auto" # Streamlit might need to infer or we reconstruct
        }
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

