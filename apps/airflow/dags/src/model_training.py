import mlflow
import mlflow.sklearn
import pandas as pd
import numpy as np
import shap
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import logging
import time
import joblib
import os

# Threshold for promoting to production
MIN_R2_THRESHOLD = 0.35  # Model must have at least this R² to be promoted
MAX_RMSE_THRESHOLD = 700000  # Model must have RMSE below this to be promoted

def train_and_log_model(train_df, experiment_name="real_estate_price_prediction"):
    """
    Trains an advanced model with feature engineering, logs to MLflow,
    and automatically promotes to Production if metrics meet thresholds.
    """
    try:
        mlflow.set_experiment(experiment_name)
        
        with mlflow.start_run(run_name=f"auto_train_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}"):
            logging.info("="*60)
            logging.info("STARTING AUTOMATED MODEL TRAINING")
            logging.info("="*60)
            
            # Validate data
            if "price" not in train_df.columns:
                raise ValueError("Dataset missing target column 'price'")
            
            # ============================================
            # DATA PREPROCESSING
            # ============================================
            logging.info("[1/6] Preprocessing data...")
            
            df = train_df.copy()
            
            # Clean price
            df = df.dropna(subset=['price'])
            df = df[df['price'] > 0]
            
            # Remove extreme price outliers (P1-P99)
            Q1 = df['price'].quantile(0.01)
            Q3 = df['price'].quantile(0.99)
            df = df[(df['price'] >= Q1) & (df['price'] <= Q3)]
            
            # Numeric features
            num_features = ['bed', 'bath', 'acre_lot', 'house_size']
            for f in num_features:
                df[f] = pd.to_numeric(df[f], errors='coerce')
            
            # Remove feature outliers
            df = df[df['bed'] <= 10]
            df = df[df['bath'] <= 10]
            df = df[df['acre_lot'] <= 10]
            df = df[df['house_size'] <= 15000]
            df = df.dropna(subset=num_features)
            
            logging.info(f"  Samples after cleaning: {len(df):,}")
            
            # ============================================
            # FEATURE ENGINEERING
            # ============================================
            logging.info("[2/6] Feature engineering...")
            
            # Target encode state (if available)
            if 'state' in df.columns:
                state_means = df.groupby('state')['price'].mean().to_dict()
                df['state_price_mean'] = df['state'].map(state_means)
                logging.info(f"  Added state_price_mean ({len(state_means)} states)")
            else:
                state_means = {}
                df['state_price_mean'] = df['price'].mean()
                logging.info("  No state column, using global mean")
            
            # Status encoding
            if 'status' in df.columns:
                df['is_sold'] = (df['status'] == 'sold').astype(int)
            else:
                df['is_sold'] = 0
            
            # Interaction features
            df['bed_bath_interaction'] = df['bed'] * df['bath']
            df['size_per_bed'] = df['house_size'] / (df['bed'] + 1)
            df['size_per_bath'] = df['house_size'] / (df['bath'] + 1)
            df['total_rooms'] = df['bed'] + df['bath']
            df['lot_to_house_ratio'] = df['acre_lot'] * 43560 / (df['house_size'] + 1)
            
            # Final feature list
            features = [
                'bed', 'bath', 'acre_lot', 'house_size',
                'state_price_mean', 'is_sold',
                'bed_bath_interaction', 'size_per_bed', 'size_per_bath',
                'total_rooms', 'lot_to_house_ratio'
            ]
            
            X = df[features].copy()
            y = df['price'].copy()
            
            # Handle any remaining NaN
            X = X.fillna(X.median())
            
            logging.info(f"  Features: {len(features)}")
            logging.info(f"  Samples: {len(X):,}")
            
            # ============================================
            # TRAIN/TEST SPLIT
            # ============================================
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            logging.info(f"  Train: {len(X_train):,}, Test: {len(X_test):,}")
            
            # ============================================
            # MODEL TRAINING
            # ============================================
            logging.info("[3/6] Training HistGradientBoostingRegressor...")
            
            model = HistGradientBoostingRegressor(
                max_iter=500,
                max_depth=12,
                learning_rate=0.05,
                min_samples_leaf=20,
                l2_regularization=0.1,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1,
                n_iter_no_change=20,
                verbose=0
            )
            
            model.fit(X_train, y_train)
            
            # ============================================
            # EVALUATION
            # ============================================
            logging.info("[4/6] Evaluating model...")
            
            y_pred = model.predict(X_test)
            
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
            
            # Cross-validation
            cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')
            cv_mean = cv_scores.mean()
            cv_std = cv_scores.std()
            
            logging.info(f"  R²:   {r2:.4f}")
            logging.info(f"  RMSE: ${rmse:,.0f}")
            logging.info(f"  MAE:  ${mae:,.0f}")
            logging.info(f"  MAPE: {mape:.1f}%")
            logging.info(f"  CV R² (5-fold): {cv_mean:.4f} (+/- {cv_std*2:.4f})")
            
            # Log parameters
            mlflow.log_param('model_type', 'HistGradientBoostingRegressor')
            mlflow.log_param('max_iter', 500)
            mlflow.log_param('max_depth', 12)
            mlflow.log_param('learning_rate', 0.05)
            mlflow.log_param('features', str(features))
            mlflow.log_param('n_features', len(features))
            mlflow.log_param('n_samples', len(X))
            mlflow.log_param('n_states', len(state_means))
            
            # Log metrics
            mlflow.log_metric('r2', r2)
            mlflow.log_metric('rmse', rmse)
            mlflow.log_metric('mae', mae)
            mlflow.log_metric('mape', mape)
            mlflow.log_metric('cv_r2_mean', cv_mean)
            mlflow.log_metric('cv_r2_std', cv_std)
            
            # ============================================
            # SAVE ARTIFACTS
            # ============================================
            logging.info("[5/6] Saving artifacts...")
            
            # Save model
            mlflow.sklearn.log_model(model, 'model')
            
            # Save state_means for inference
            joblib.dump(state_means, '/tmp/state_means.pkl')
            mlflow.log_artifact('/tmp/state_means.pkl')
            
            # Save feature list
            with open('/tmp/features.txt', 'w') as f:
                f.write('\n'.join(features))
            mlflow.log_artifact('/tmp/features.txt')
            
            run_id = mlflow.active_run().info.run_id
            logging.info(f"  Run ID: {run_id}")
            
            # ============================================
            # AUTOMATIC PROMOTION TO PRODUCTION
            # ============================================
            logging.info("[6/6] Checking promotion criteria...")
            
            should_promote = True
            promotion_reasons = []
            
            if r2 < MIN_R2_THRESHOLD:
                should_promote = False
                promotion_reasons.append(f"R² ({r2:.4f}) < threshold ({MIN_R2_THRESHOLD})")
            
            if rmse > MAX_RMSE_THRESHOLD:
                should_promote = False
                promotion_reasons.append(f"RMSE (${rmse:,.0f}) > threshold (${MAX_RMSE_THRESHOLD:,})")
            
            if should_promote:
                logging.info("  ✅ Model meets promotion criteria!")
                logging.info("  Registering and promoting to Production...")
                
                client = mlflow.tracking.MlflowClient()
                
                # Check if model exists in registry
                try:
                    client.get_registered_model('real_estate_model')
                except:
                    client.create_registered_model(
                        'real_estate_model',
                        description='Real Estate Price Prediction Model (Auto-trained)'
                    )
                
                # Create new version
                model_uri = f'runs:/{run_id}/model'
                mv = client.create_model_version('real_estate_model', model_uri, run_id)
                logging.info(f"  Created model version: {mv.version}")
                
                # Transition to Production (archive old versions)
                client.transition_model_version_stage(
                    'real_estate_model',
                    mv.version,
                    'Production',
                    archive_existing_versions=True
                )
                logging.info(f"  ✅ Model v{mv.version} promoted to Production!")
                
                # Log promotion
                mlflow.log_param('promoted_to_production', True)
                mlflow.log_param('model_version', mv.version)
                
            else:
                logging.warning("  ❌ Model does NOT meet promotion criteria:")
                for reason in promotion_reasons:
                    logging.warning(f"    - {reason}")
                mlflow.log_param('promoted_to_production', False)
                mlflow.log_param('promotion_failure_reasons', str(promotion_reasons))
            
            logging.info("="*60)
            logging.info("TRAINING COMPLETED")
            logging.info("="*60)
            
            return run_id, rmse

    except Exception as e:
        logging.error(f"Training failed: {e}")
        try:
            with open("/tmp/training_error.log", "w") as f:
                f.write(str(e))
        except:
            pass
        logging.info("Sleeping for 600 seconds for debugging...")
        time.sleep(600)
        raise
