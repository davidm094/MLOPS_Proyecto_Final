import streamlit as st
import requests
import pandas as pd
import shap
import matplotlib.pyplot as plt
import mlflow
import json
import streamlit.components.v1 as components

API_URL = "http://api-service:8000"
MLFLOW_TRACKING_URI = "http://mlflow-service:5000"

st.set_page_config(page_title="Real Estate Predictor", layout="wide")

st.title("🏡 Real Estate Price Prediction & Explanation")

tabs = st.tabs(["Prediction", "Model History"])

with tabs[0]:
    st.header("Predict Property Price")
    
    col1, col2 = st.columns(2)
    
    with col1:
        bed = st.number_input("Bedrooms", min_value=0.0, value=3.0)
        bath = st.number_input("Bathrooms", min_value=0.0, value=2.0)
        acre_lot = st.number_input("Acre Lot", min_value=0.0, value=0.1)
        house_size = st.number_input("House Size (sqft)", min_value=0.0, value=1500.0)
        
    with col2:
        status = st.selectbox("Status", ["for_sale", "ready_to_build"])
        city = st.text_input("City", "New York")
        state = st.text_input("State", "NY")
        zip_code = st.text_input("Zip Code", "10001")
        
    if st.button("Predict"):
        payload = {
            "bed": bed,
            "bath": bath,
            "acre_lot": acre_lot,
            "house_size": house_size,
            "status": status,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "brokered_by": 1.0 # Default
        }
        
        try:
            # Predict
            response = requests.post(f"{API_URL}/predict", json=payload)
            response.raise_for_status()
            result = response.json()
            
            st.success(f"Predicted Price: ${result['price']:,.2f}")
            st.info(f"Model Version: {result['model_version']}")
            
            # Explain
            st.subheader("Why this price?")
            exp_response = requests.post(f"{API_URL}/explain", json=payload)
            exp_response.raise_for_status()
            exp_data = exp_response.json()
            
            shap_values = exp_data["shap_values"]
            base_value = exp_data["base_value"]
            
            # Visualizing SHAP
            # Force plot requires Javascript. We can use matplotlib for waterfall if available or stick to force plot HTML
            st.write("SHAP Force Plot:")
            shap.initjs()
            
            # We need to construct a robust visualization. 
            # Since we don't have the exact feature names transformed here easily (it was done in API),
            # we might just show the raw values or try to map them.
            # For simplicity in this demo, we display the values.
            
            st.bar_chart(shap_values)
            st.caption("Feature contributions (Transformed space)")
            
        except Exception as e:
            st.error(f"Error: {e}")

with tabs[1]:
    st.header("Model History")
    
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name("real_estate_price_prediction")
        
        if experiment:
            runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])
            st.dataframe(runs[['run_id', 'status', 'start_time', 'metrics.rmse', 'metrics.r2']])
            
            st.subheader("Production Models")
            versions = client.get_latest_versions("real_estate_price_prediction", stages=["Production"])
            for v in versions:
                st.write(f"Version: {v.version}, Run ID: {v.run_id}, Status: {v.current_stage}")
        else:
            st.warning("No experiment found.")
            
    except Exception as e:
        st.error(f"Could not connect to MLflow: {e}")

