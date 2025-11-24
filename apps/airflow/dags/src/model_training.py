import mlflow
import mlflow.sklearn
import pandas as pd
import shap
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, r2_score
import logging
from .preprocessing import get_preprocessor
import time
import joblib

def train_and_log_model(train_df, experiment_name="real_estate_price_prediction"):
    """
    Trains a Random Forest model, logs metrics, model, and SHAP explainer to MLflow.
    """
    try:
        mlflow.set_experiment(experiment_name)
        
        with mlflow.start_run():
            # Prepare data
            if "price" not in train_df.columns:
                raise ValueError("Dataset missing target column 'price'")

            X = train_df.drop("price", axis=1)
            y = train_df["price"]
            
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Define pipeline
            preprocessor = get_preprocessor()
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            clf = Pipeline(steps=[('preprocessor', preprocessor),
                                  ('regressor', model)])
            
            # Train
            logging.info("Training model...")
            clf.fit(X_train, y_train)
            
            # Evaluate
            y_pred = clf.predict(X_test)
            rmse = mean_squared_error(y_test, y_pred, squared=False)
            r2 = r2_score(y_test, y_pred)
            
            logging.info(f"RMSE: {rmse}")
            logging.info(f"R2: {r2}")
            
            # Log metrics
            mlflow.log_metric("rmse", rmse)
            mlflow.log_metric("r2", r2)
            
            # Log Model
            mlflow.sklearn.log_model(clf, "model")
            
            # --- SHAP ---
            logging.info("Generating SHAP explainer...")
            
            # Transform X_train to get features for SHAP
            X_train_transformed = clf.named_steps['preprocessor'].transform(X_train)
            
            # Using TreeExplainer since we use RandomForest
            rf_model = clf.named_steps['regressor']
            
            # TreeExplainer sometimes requires simpler input or just the model
            explainer = shap.TreeExplainer(rf_model)
            
            # Save explainer locally then log artifact
            joblib.dump(explainer, "shap_explainer.pkl")
            mlflow.log_artifact("shap_explainer.pkl")
            
            return mlflow.active_run().info.run_id, rmse

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


