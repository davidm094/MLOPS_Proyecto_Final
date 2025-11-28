from fastapi import FastAPI, HTTPException, Request
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
import time
import uuid
from io import BytesIO
from datetime import datetime
from sqlalchemy import create_engine, text
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log transform functions (must match training code for model deserialization)
def log_transform(y):
    """Log transform for target variable."""
    return np.log1p(y)

def inverse_log_transform(y):
    """Inverse log transform."""
    return np.expm1(y)

# Register in module for joblib deserialization
import sys
sys.modules['src'] = type(sys)('src')
sys.modules['src.model_training'] = type(sys)('src.model_training')
sys.modules['src.model_training'].log_transform = log_transform
sys.modules['src.model_training'].inverse_log_transform = inverse_log_transform

app = FastAPI(title="Real Estate Price Prediction API", version="5.0")

# ============================================
# PROMETHEUS METRICS
# ============================================
PREDICTIONS_TOTAL = Counter(
    'predictions_total', 
    'Total number of predictions made',
    ['state', 'model_version']
)
PREDICTION_LATENCY = Histogram(
    'prediction_latency_seconds',
    'Prediction request latency',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)
PREDICTION_PRICE = Histogram(
    'prediction_price_dollars',
    'Distribution of predicted prices',
    buckets=[100000, 250000, 500000, 750000, 1000000, 1500000, 2000000, 5000000]
)
MODEL_INFO = Info('model', 'Information about the loaded model')
MODEL_LOADED = Gauge('model_loaded', 'Whether a model is currently loaded')
EXPLAINER_LOADED = Gauge('explainer_loaded', 'Whether SHAP explainer is loaded')

# Prometheus HTTP metrics (will be instrumented via middleware)
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Middleware to instrument HTTP requests (excludes health checks)
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip instrumentation for health checks and metrics
        if request.url.path in ["/ready", "/health", "/metrics"]:
            return await call_next(request)
        
        method = request.method
        endpoint = request.url.path
        
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        
        return response

# ============================================
# CONFIGURATION
# ============================================
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs-s3.mlops.svc:8333")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "any")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "any")
MLFLOW_BUCKET = "mlflow-artifacts"
MODEL_NAME = "real_estate_model"

# PostgreSQL for inference logging
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:airflow-postgres-root@postgres-postgresql.mlops.svc.cluster.local:5432/mlops_data')

# Global variables
model = None
state_means = None
explainer = None
model_version = None
model_stage = None
model_run_id = None
feature_names = None

DEFAULT_STATE_MEAN = 1_000_000

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

def get_db_engine():
    """Get SQLAlchemy engine for PostgreSQL."""
    try:
        return create_engine(DATABASE_URL)
    except Exception as e:
        logger.warning(f"Could not create DB engine: {e}")
        return None

def log_inference(input_data, prediction, response_time_ms, request_id, client_ip):
    """Log inference to PostgreSQL."""
    try:
        engine = get_db_engine()
        if engine is None:
            return
        
        data = {
            'timestamp': [datetime.now()],
            'bed': [input_data.bed],
            'bath': [input_data.bath],
            'acre_lot': [input_data.acre_lot],
            'house_size': [input_data.house_size],
            'state': [input_data.state],
            'status': [input_data.status],
            'predicted_price': [prediction],
            'model_version': [model_version],
            'model_run_id': [model_run_id],
            'response_time_ms': [response_time_ms],
            'client_ip': [client_ip],
            'request_id': [request_id]
        }
        
        df = pd.DataFrame(data)
        df.to_sql('inference_logs', engine, if_exists='append', index=False)
        logger.debug(f"Logged inference: {request_id}")
    except Exception as e:
        logger.warning(f"Failed to log inference: {e}")

def load_production_model():
    """Load the model marked as 'Production' in MLflow Model Registry."""
    global model, state_means, explainer, model_version, model_stage, model_run_id, feature_names
    
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()
        
        try:
            versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
            if versions:
                prod_version = versions[0]
                model_version = prod_version.version
                model_stage = prod_version.current_stage
                model_run_id = prod_version.run_id
                
                logger.info(f"Found Production model: {MODEL_NAME} v{model_version} (run: {model_run_id})")
                
                s3 = get_s3_client()
                
                # Load model (experiment ID is 1)
                try:
                    model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/model/model.pkl")
                    model = joblib.load(BytesIO(model_obj['Body'].read()))
                    logger.info("Model loaded successfully")
                except Exception as e:
                    logger.error(f"Could not load model: {e}")
                    return False
                
                # Load state_means
                try:
                    state_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/state_means.pkl")
                    state_means = joblib.load(BytesIO(state_obj['Body'].read()))
                    logger.info(f"Loaded state_means with {len(state_means)} states")
                except Exception as e:
                    logger.warning(f"Could not load state_means: {e}")
                    state_means = {}
                
                # Load feature names
                try:
                    feat_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/features.txt")
                    feature_names = feat_obj['Body'].read().decode('utf-8').strip().split('\n')
                    logger.info(f"Feature names: {feature_names}")
                except Exception as e:
                    logger.warning(f"Could not load feature names: {e}")
                    feature_names = ['bed', 'bath', 'acre_lot', 'house_size']
                
                # Create SHAP explainer using KernelExplainer (compatible with all models)
                try:
                    fitted_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/fitted_model.pkl")
                    fitted_model = joblib.load(BytesIO(fitted_obj['Body'].read()))
                    # Background data for KernelExplainer (typical house values)
                    background = np.array([[3, 2, 0.25, 1800, 500000, 0, 6, 450, 600, 5, 6.0]])
                    explainer = shap.KernelExplainer(fitted_model.predict, background)
                    logger.info("SHAP KernelExplainer created successfully")
                except Exception as e:
                    logger.warning(f"Could not create explainer: {e}")
                    explainer = None
                
                # Update Prometheus metrics
                MODEL_LOADED.set(1)
                EXPLAINER_LOADED.set(1 if explainer else 0)
                MODEL_INFO.info({
                    'name': MODEL_NAME,
                    'version': str(model_version),
                    'stage': model_stage,
                    'run_id': model_run_id[:12]
                })
                
                return True
            else:
                logger.warning(f"No Production model found for '{MODEL_NAME}'")
        except mlflow.exceptions.MlflowException as e:
            logger.warning(f"Model '{MODEL_NAME}' not registered: {e}")
        
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
            MODEL_LOADED.set(0)
            return False
        
        run_times = {}
        for obj in response['Contents']:
            parts = obj['Key'].split('/')
            if len(parts) >= 2 and 'model.pkl' in obj['Key'] and 'artifacts/model/' in obj['Key']:
                run_id = parts[1]
                last_modified = obj['LastModified']
                if run_id not in run_times or last_modified > run_times[run_id]:
                    run_times[run_id] = last_modified
        
        if not run_times:
            MODEL_LOADED.set(0)
            return False
        
        latest_run = max(run_times.keys(), key=lambda x: run_times[x])
        model_run_id = latest_run
        model_version = "latest"
        model_stage = "Fallback"
        
        logger.info(f"Loading model from run: {model_run_id}")
        
        model_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/model/model.pkl")
        model = joblib.load(BytesIO(model_obj['Body'].read()))
        
        try:
            state_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/state_means.pkl")
            state_means = joblib.load(BytesIO(state_obj['Body'].read()))
        except:
            state_means = {}
        
        try:
            feat_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/features.txt")
            feature_names = feat_obj['Body'].read().decode('utf-8').strip().split('\n')
        except:
            feature_names = ['bed', 'bath', 'acre_lot', 'house_size']
        
        try:
            fitted_obj = s3.get_object(Bucket=MLFLOW_BUCKET, Key=f"1/{model_run_id}/artifacts/fitted_model.pkl")
            fitted_model = joblib.load(BytesIO(fitted_obj['Body'].read()))
            background = np.array([[3, 2, 0.25, 1800, 500000, 0, 6, 450, 600, 5, 6.0]])
            explainer = shap.KernelExplainer(fitted_model.predict, background)
        except:
            explainer = None
        
        MODEL_LOADED.set(1)
        EXPLAINER_LOADED.set(1 if explainer else 0)
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading model from S3: {e}")
        MODEL_LOADED.set(0)
        return False

# Add Prometheus middleware (excludes health checks)
app.add_middleware(PrometheusMiddleware)

@app.on_event("startup")
async def startup_event():
    load_production_model()
    logger.info("Prometheus middleware initialized")

# ============================================
# PYDANTIC MODELS
# ============================================
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
    input_summary: Dict
    request_id: str

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

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    explainer_loaded: bool
    database_connected: bool

# ============================================
# HELPER FUNCTIONS
# ============================================
def prepare_features(input_data: PropertyInput) -> pd.DataFrame:
    """Prepare all features including engineered ones."""
    bed = float(input_data.bed) if input_data.bed else 3.0
    bath = float(input_data.bath) if input_data.bath else 2.0
    acre_lot = float(input_data.acre_lot) if input_data.acre_lot else 0.25
    house_size = float(input_data.house_size) if input_data.house_size else 1800.0
    
    state = input_data.state or "California"
    if state_means and state in state_means:
        state_price_mean = state_means[state]
    elif state_means:
        state_price_mean = np.mean(list(state_means.values()))
    else:
        state_price_mean = DEFAULT_STATE_MEAN
    
    is_sold = 1 if input_data.status == "sold" else 0
    
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
    
    if feature_names:
        data = {k: v for k, v in data.items() if k in feature_names}
    
    return pd.DataFrame([data])

# ============================================
# ENDPOINTS
# ============================================
# Health check endpoints defined first to ensure they're always available
@app.get("/ready", include_in_schema=False)
def ready():
    """Readiness probe - returns 200 only if model is loaded."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}

@app.get("/health", response_model=HealthResponse, include_in_schema=False)
def health():
    db_connected = False
    try:
        engine = get_db_engine()
        if engine:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_connected = True
    except:
        pass
    
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        model_loaded=model is not None,
        explainer_loaded=explainer is not None,
        database_connected=db_connected
    )

@app.get("/")
def root():
    return {
        "service": "Real Estate Price Prediction API",
        "version": "5.0",
        "model_name": MODEL_NAME,
        "model_version": model_version,
        "model_stage": model_stage,
        "model_run_id": model_run_id,
        "model_loaded": model is not None,
        "explainer_loaded": explainer is not None,
        "features": feature_names
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
        available_states=list(state_means.keys()) if state_means else [],
        feature_names=feature_names or []
    )

@app.get("/states")
def get_states():
    if state_means:
        sorted_states = sorted(state_means.items(), key=lambda x: x[1], reverse=True)
        return {"states": [{"state": k, "avg_price": v} for k, v in sorted_states]}
    return {"states": []}

@app.post("/reload")
def reload_model():
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
def predict(input_data: PropertyInput, request: Request):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Call /reload first.")
    
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        price = float(prediction[0])
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Update Prometheus metrics
        state = input_data.state or "unknown"
        PREDICTIONS_TOTAL.labels(state=state, model_version=str(model_version)).inc()
        PREDICTION_LATENCY.observe(response_time_ms / 1000)
        PREDICTION_PRICE.observe(price)
        
        # Log to PostgreSQL (async-like, non-blocking)
        try:
            client_ip = request.client.host if request.client else "unknown"
            log_inference(input_data, price, response_time_ms, request_id, client_ip)
        except Exception as e:
            logger.warning(f"Failed to log inference: {e}")
        
        return PredictionResponse(
            price=price,
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
            },
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/explain", response_model=ExplanationResponse)
def explain(input_data: PropertyInput):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if explainer is None:
        raise HTTPException(status_code=503, detail="SHAP Explainer not available")
    
    try:
        df = prepare_features(input_data)
        prediction = model.predict(df)
        
        # Transform data through the preprocessor before SHAP
        # The model is TransformedTargetRegressor -> Pipeline (preprocessor + model)
        try:
            preprocessor = model.regressor_.named_steps['preprocessor']
            df_transformed = preprocessor.transform(df)
        except Exception as e:
            logger.warning(f"Could not transform data for SHAP: {e}, using raw")
            df_transformed = df.values
        
        shap_values = explainer.shap_values(df_transformed)
        
        if isinstance(shap_values, list):
            shap_vals = shap_values[0][0] if len(shap_values[0].shape) > 1 else shap_values[0]
        else:
            shap_vals = shap_values[0] if len(shap_values.shape) > 1 else shap_values
        
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
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    results = []
    for prop in properties:
        try:
            df = prepare_features(prop)
            pred = model.predict(df)[0]
            results.append({
                "input": {"bed": prop.bed, "bath": prop.bath, "house_size": prop.house_size, "state": prop.state},
                "price": float(pred)
            })
        except Exception as e:
            results.append({"input": {"bed": prop.bed, "bath": prop.bath}, "error": str(e)})
    
    return {"predictions": results, "model_version": model_version}

@app.get("/predictions/history")
def get_prediction_history(limit: int = 100, state: Optional[str] = None):
    """Get recent prediction history from database."""
    try:
        engine = get_db_engine()
        if engine is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        query = "SELECT * FROM inference_logs"
        if state:
            query += f" WHERE state = '{state}'"
        query += f" ORDER BY timestamp DESC LIMIT {limit}"
        
        df = pd.read_sql(query, engine)
        return {"predictions": df.to_dict(orient='records'), "count": len(df)}
    except Exception as e:
        logger.error(f"Failed to get prediction history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/summary")
def get_metrics_summary():
    """Get summary of prediction metrics."""
    try:
        engine = get_db_engine()
        if engine is None:
            return {"error": "Database not available"}
        
        query = """
            SELECT 
                COUNT(*) as total_predictions,
                AVG(predicted_price) as avg_price,
                MIN(predicted_price) as min_price,
                MAX(predicted_price) as max_price,
                AVG(response_time_ms) as avg_response_time_ms,
                COUNT(DISTINCT state) as unique_states,
                COUNT(DISTINCT model_version) as model_versions_used
            FROM inference_logs
            WHERE timestamp > NOW() - INTERVAL '24 hours'
        """
        
        df = pd.read_sql(query, engine)
        return df.to_dict(orient='records')[0] if len(df) > 0 else {}
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        return {"error": str(e)}

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Prometheus instrumentation is now handled via custom middleware
# This avoids conflicts with health check endpoints
