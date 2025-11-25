"""
Model training module with XGBoost, feature engineering, and hyperparameter tuning.
"""
import mlflow
import mlflow.sklearn
import mlflow.xgboost
import pandas as pd
import numpy as np
import shap
import joblib
import logging
import os
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.impute import SimpleImputer

# Try to import XGBoost, fall back to HistGradientBoosting
try:
    import xgboost as xgb
    USE_XGBOOST = True
    logging.info("Using XGBoost")
except ImportError:
    from sklearn.ensemble import HistGradientBoostingRegressor
    USE_XGBOOST = False
    logging.info("XGBoost not available, using HistGradientBoostingRegressor")

# Try to import Optuna
try:
    import optuna
    from optuna.integration import OptunaSearchCV
    USE_OPTUNA = True
    logging.info("Optuna available for hyperparameter tuning")
except ImportError:
    USE_OPTUNA = False
    logging.info("Optuna not available, using default hyperparameters")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MODEL_NAME = "real_estate_model"

# Promotion thresholds
R2_THRESHOLD = 0.35
RMSE_THRESHOLD = 700000  # $700K


def calculate_mape(y_true, y_pred):
    """Calculate Mean Absolute Percentage Error."""
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def log_transform(y):
    """Log transform for target variable."""
    return np.log1p(y)


def inverse_log_transform(y):
    """Inverse log transform."""
    return np.expm1(y)


def engineer_features(df):
    """
    Create engineered features from raw data.
    
    Features created:
    - is_sold: Binary indicator if property is sold
    - bed_bath_interaction: bed * bath
    - size_per_bed: house_size / (bed + 1)
    - size_per_bath: house_size / (bath + 1)
    - total_rooms: bed + bath
    - lot_to_house_ratio: acre_lot * 43560 / (house_size + 1)
    - state_price_mean: Target encoding for state
    """
    df = df.copy()
    
    # Basic feature engineering
    df['is_sold'] = (df['status'] == 'sold').astype(int) if 'status' in df.columns else 0
    df['bed_bath_interaction'] = df['bed'] * df['bath']
    df['size_per_bed'] = df['house_size'] / (df['bed'] + 1)
    df['size_per_bath'] = df['house_size'] / (df['bath'] + 1)
    df['total_rooms'] = df['bed'] + df['bath']
    df['lot_to_house_ratio'] = df['acre_lot'] * 43560 / (df['house_size'] + 1)
    
    # Handle infinites
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    return df


def create_state_encoding(df, target_col='price'):
    """Create target encoding for state."""
    state_means = df.groupby('state')[target_col].mean().to_dict()
    df['state_price_mean'] = df['state'].map(state_means)
    df['state_price_mean'].fillna(df[target_col].mean(), inplace=True)
    return df, state_means


def optimize_hyperparameters(X_train, y_train, n_trials=20):
    """
    Use Optuna to find optimal hyperparameters.
    """
    if not USE_OPTUNA:
        logging.info("Optuna not available, returning default hyperparameters")
        if USE_XGBOOST:
            return {
                'n_estimators': 200,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 3,
                'reg_alpha': 0.1,
                'reg_lambda': 1.0
            }
        else:
            return {
                'max_iter': 200,
                'max_depth': 8,
                'learning_rate': 0.1
            }
    
    def objective(trial):
        if USE_XGBOOST:
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                'random_state': 42,
                'n_jobs': -1
            }
            model = xgb.XGBRegressor(**params)
        else:
            params = {
                'max_iter': trial.suggest_int('max_iter', 100, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 15),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'random_state': 42
            }
            model = HistGradientBoostingRegressor(**params)
        
        # Use cross-validation
        scores = cross_val_score(model, X_train, y_train, cv=3, scoring='r2', n_jobs=-1)
        return scores.mean()
    
    logging.info(f"Starting Optuna optimization with {n_trials} trials...")
    study = optuna.create_study(direction='maximize', study_name='xgboost_optimization')
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    
    logging.info(f"Best trial: {study.best_trial.number}")
    logging.info(f"Best R2: {study.best_value:.4f}")
    logging.info(f"Best params: {study.best_params}")
    
    return study.best_params


def train_and_log_model(train_df, experiment_name="real_estate_price_prediction"):
    """
    Train model with XGBoost, log to MLflow, and optionally promote to production.
    
    Returns:
        tuple: (run_id, rmse)
    """
    try:
        mlflow.set_experiment(experiment_name)
        
        logging.info("="*60)
        logging.info("STARTING MODEL TRAINING")
        logging.info("="*60)
        logging.info(f"Input data: {len(train_df)} rows")
        
        # Filter outliers
        p1, p99 = train_df['price'].quantile(0.01), train_df['price'].quantile(0.99)
        df = train_df[(train_df['price'] >= p1) & (train_df['price'] <= p99)].copy()
        logging.info(f"After outlier removal: {len(df)} rows")
        
        # Feature engineering
        df = engineer_features(df)
        df, state_means = create_state_encoding(df)
        
        # Define features
        feature_names = [
            'bed', 'bath', 'acre_lot', 'house_size',
            'state_price_mean', 'is_sold',
            'bed_bath_interaction', 'size_per_bed', 'size_per_bath',
            'total_rooms', 'lot_to_house_ratio'
        ]
        
        # Prepare data
        X = df[feature_names].copy()
        y = df['price'].copy()
        
        # Handle missing values
        X.fillna(X.median(), inplace=True)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        logging.info(f"Training set: {len(X_train)} samples")
        logging.info(f"Test set: {len(X_test)} samples")
        
        # Hyperparameter optimization (limited trials for speed)
        best_params = optimize_hyperparameters(X_train, np.log1p(y_train), n_trials=10)
        
        # Create model
        if USE_XGBOOST:
            base_model = xgb.XGBRegressor(**best_params, random_state=42, n_jobs=-1)
            model_type = "XGBRegressor"
        else:
            base_model = HistGradientBoostingRegressor(**best_params, random_state=42)
            model_type = "HistGradientBoostingRegressor"
        
        # Create pipeline with preprocessing
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', Pipeline([
                    ('imputer', SimpleImputer(strategy='median')),
                    ('scaler', StandardScaler())
                ]), feature_names)
            ],
            remainder='passthrough'
        )
        
        # Wrap with target transformation
        model = TransformedTargetRegressor(
            regressor=Pipeline([
                ('preprocessor', preprocessor),
                ('model', base_model)
            ]),
            func=log_transform,
            inverse_func=inverse_log_transform
        )
        
        with mlflow.start_run(run_name=f"{model_type}_{datetime.now().strftime('%Y%m%d_%H%M')}"):
            run_id = mlflow.active_run().info.run_id
            
            # Log parameters
            mlflow.log_params({
                "model_type": model_type,
                "use_xgboost": USE_XGBOOST,
                "use_optuna": USE_OPTUNA,
                "target_transform": "log1p",
                "n_features": len(feature_names),
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                **{f"hp_{k}": v for k, v in best_params.items()}
            })
            
            # Train
            logging.info(f"Training {model_type}...")
            model.fit(X_train, y_train)
            
            # Predict
            y_pred = model.predict(X_test)
            
            # Calculate metrics
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            mape = calculate_mape(y_test.values, y_pred)
            
            logging.info("-"*40)
            logging.info("METRICS:")
            logging.info(f"  RMSE: ${rmse:,.0f}")
            logging.info(f"  MAE:  ${mae:,.0f}")
            logging.info(f"  R2:   {r2:.4f}")
            logging.info(f"  MAPE: {mape:.2f}%")
            logging.info("-"*40)
            
            # Log metrics
            mlflow.log_metrics({
                "rmse": rmse,
                "mae": mae,
                "r2": r2,
                "mape": mape
            })
            
            # Cross-validation
            cv_scores = cross_val_score(model, X, y, cv=5, scoring='r2', n_jobs=-1)
            mlflow.log_metrics({
                "cv_r2_mean": np.mean(cv_scores),
                "cv_r2_std": np.std(cv_scores)
            })
            logging.info(f"CV R2: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")
            
            # Save and log model
            # Extract the actual fitted model for direct use
            fitted_model = model.regressor_.named_steps['model']
            
            # Save model.pkl
            joblib.dump(fitted_model, "model.pkl")
            mlflow.log_artifact("model.pkl", "model")
            
            # Save state_means.pkl
            joblib.dump(state_means, "state_means.pkl")
            mlflow.log_artifact("state_means.pkl")
            
            # Save feature names
            with open("features.txt", "w") as f:
                f.write("\n".join(feature_names))
            mlflow.log_artifact("features.txt")
            
            # Log full pipeline for MLflow model registry
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="sklearn_model",
                registered_model_name=MODEL_NAME
            )
            
            # Create SHAP explainer
            logging.info("Creating SHAP explainer...")
            try:
                if USE_XGBOOST:
                    explainer = shap.TreeExplainer(fitted_model)
                else:
                    explainer = shap.TreeExplainer(fitted_model)
                
                # Save explainer
                joblib.dump(explainer, "shap_explainer.pkl")
                mlflow.log_artifact("shap_explainer.pkl")
                
                # Generate and log SHAP summary plot
                X_sample = X_test.sample(min(100, len(X_test)), random_state=42)
                # Transform for SHAP
                X_transformed = model.regressor_.named_steps['preprocessor'].transform(X_sample)
                shap_values = explainer.shap_values(X_transformed)
                
                mlflow.log_param("shap_explainer_created", True)
                logging.info("SHAP explainer created and logged")
            except Exception as e:
                logging.warning(f"Could not create SHAP explainer: {e}")
                mlflow.log_param("shap_explainer_created", False)
            
            # Model promotion logic
            logging.info("="*40)
            logging.info("MODEL PROMOTION CHECK")
            logging.info(f"  R2 threshold:   >= {R2_THRESHOLD}")
            logging.info(f"  RMSE threshold: <= ${RMSE_THRESHOLD:,}")
            logging.info(f"  Current R2:     {r2:.4f}")
            logging.info(f"  Current RMSE:   ${rmse:,.0f}")
            
            client = mlflow.tracking.MlflowClient()
            
            # Get the model version just created
            model_versions = client.search_model_versions(f"run_id='{run_id}'")
            new_version = model_versions[0].version if model_versions else None
            
            if new_version:
                if r2 >= R2_THRESHOLD and rmse <= RMSE_THRESHOLD:
                    logging.info(f"  PROMOTING version {new_version} to Production!")
                    client.transition_model_version_stage(
                        name=MODEL_NAME,
                        version=new_version,
                        stage="Production",
                        archive_existing_versions=True
                    )
                    mlflow.log_param("promoted_to_production", True)
                    mlflow.log_param("promotion_reason", "Metrics met thresholds")
                else:
                    logging.info(f"  NOT promoting version {new_version}")
                    logging.info(f"  Reason: R2 {r2:.4f} < {R2_THRESHOLD} or RMSE ${rmse:,.0f} > ${RMSE_THRESHOLD:,}")
                    mlflow.log_param("promoted_to_production", False)
                    mlflow.log_param("promotion_reason", f"R2={r2:.4f}, RMSE=${rmse:,.0f}")
            
            logging.info("="*40)
            
            # Cleanup temp files
            for f in ["model.pkl", "state_means.pkl", "features.txt", "shap_explainer.pkl"]:
                if os.path.exists(f):
                    os.remove(f)
            
            return run_id, rmse
            
    except Exception as e:
        logging.error(f"Training failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise
