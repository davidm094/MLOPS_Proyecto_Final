import streamlit as st
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# Configuration
API_URL = os.getenv("API_URL", "http://api:8000")

st.set_page_config(
    page_title="🏡 Real Estate Price Predictor",
    page_icon="🏡",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .prediction-box {
        background-color: #E3F2FD;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin: 20px 0;
    }
    .price-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1565C0;
    }
    .shap-positive {
        color: #D32F2F;
    }
    .shap-negative {
        color: #388E3C;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🏡 Real Estate Price Predictor</p>', unsafe_allow_html=True)

# Sidebar for API status
with st.sidebar:
    st.header("🔧 System Status")
    
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        st.success("✅ API Connected")
        st.write(f"Model Loaded: {'✅' if health.get('model_loaded') else '❌'}")
        st.write(f"Explainer Loaded: {'✅' if health.get('explainer_loaded') else '❌'}")
        
        # Reload button
        if st.button("🔄 Reload Model"):
            try:
                reload_resp = requests.post(f"{API_URL}/reload", timeout=30)
                if reload_resp.status_code == 200:
                    st.success("Model reloaded!")
                    st.rerun()
                else:
                    st.error(f"Reload failed: {reload_resp.text}")
            except Exception as e:
                st.error(f"Error: {e}")
                
    except Exception as e:
        st.error(f"❌ API Unavailable: {e}")
    
    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This app predicts real estate prices using a 
    Machine Learning model trained on US housing data.
    
    **Features used:**
    - Bedrooms
    - Bathrooms  
    - Lot Size (acres)
    - House Size (sqft)
    
    **Model:** Random Forest Regressor
    """)

# Main content
tabs = st.tabs(["🏠 Predict Price", "📊 SHAP Explanation", "📈 Model Info"])

# Tab 1: Prediction
with tabs[0]:
    st.header("Enter Property Details")
    
    col1, col2 = st.columns(2)
    
    with col1:
        bed = st.number_input(
            "🛏️ Bedrooms",
            min_value=0.0,
            max_value=20.0,
            value=3.0,
            step=1.0,
            help="Number of bedrooms"
        )
        bath = st.number_input(
            "🚿 Bathrooms",
            min_value=0.0,
            max_value=10.0,
            value=2.0,
            step=0.5,
            help="Number of bathrooms"
        )
    
    with col2:
        acre_lot = st.number_input(
            "🌳 Lot Size (acres)",
            min_value=0.0,
            max_value=100.0,
            value=0.25,
            step=0.05,
            format="%.2f",
            help="Size of the lot in acres"
        )
        house_size = st.number_input(
            "📐 House Size (sqft)",
            min_value=0.0,
            max_value=50000.0,
            value=1800.0,
            step=100.0,
            help="Total living area in square feet"
        )
    
    # Optional fields (collapsed)
    with st.expander("📋 Additional Info (Optional)"):
        status = st.selectbox("Status", ["for_sale", "ready_to_build", "sold"])
        city = st.text_input("City", "")
        state = st.text_input("State", "")
        zip_code = st.text_input("Zip Code", "")
    
    if st.button("🔮 Predict Price", type="primary", use_container_width=True):
        payload = {
            "bed": bed,
            "bath": bath,
            "acre_lot": acre_lot,
            "house_size": house_size,
            "status": status,
            "city": city if city else None,
            "state": state if state else None,
            "zip_code": zip_code if zip_code else None
        }
        
        with st.spinner("Calculating..."):
            try:
                response = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                # Store in session for SHAP tab
                st.session_state['last_prediction'] = result
                st.session_state['last_payload'] = payload
                
                # Display result
                st.markdown(f"""
                <div class="prediction-box">
                    <p>Estimated Property Value</p>
                    <p class="price-value">${result['price']:,.0f}</p>
                    <p style="color: #666; font-size: 0.9rem;">Model Run: {result.get('model_run_id', 'N/A')[:8]}...</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Quick insights
                st.markdown("### 💡 Quick Insights")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    price_per_sqft = result['price'] / house_size if house_size > 0 else 0
                    st.metric("Price per sqft", f"${price_per_sqft:,.0f}")
                with col_b:
                    price_per_bed = result['price'] / bed if bed > 0 else 0
                    st.metric("Price per bedroom", f"${price_per_bed:,.0f}")
                with col_c:
                    price_per_acre = result['price'] / acre_lot if acre_lot > 0 else 0
                    st.metric("Price per acre", f"${price_per_acre:,.0f}")
                    
            except requests.exceptions.RequestException as e:
                st.error(f"❌ API Error: {e}")
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Tab 2: SHAP Explanation
with tabs[1]:
    st.header("🔍 Understanding the Prediction")
    
    if 'last_payload' not in st.session_state:
        st.info("👆 Make a prediction first to see the explanation!")
    else:
        payload = st.session_state['last_payload']
        
        with st.spinner("Generating explanation..."):
            try:
                response = requests.post(f"{API_URL}/explain", json=payload, timeout=30)
                response.raise_for_status()
                exp_data = response.json()
                
                shap_values = exp_data['shap_values']
                base_value = exp_data['base_value']
                feature_names = exp_data['feature_names']
                feature_values = exp_data['feature_values']
                predicted_price = exp_data['price']
                
                # Summary
                st.markdown(f"""
                **Base Price:** ${base_value:,.0f}  
                **Predicted Price:** ${predicted_price:,.0f}  
                **Total SHAP Adjustment:** ${sum(shap_values):,.0f}
                """)
                
                st.markdown("---")
                
                # SHAP Waterfall Chart
                st.subheader("📊 Feature Contributions")
                
                # Create waterfall-style visualization
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Sort by absolute value
                indices = np.argsort(np.abs(shap_values))[::-1]
                sorted_features = [feature_names[i] for i in indices]
                sorted_values = [shap_values[i] for i in indices]
                sorted_feature_vals = [feature_values[i] for i in indices]
                
                colors = ['#D32F2F' if v > 0 else '#388E3C' for v in sorted_values]
                
                bars = ax.barh(range(len(sorted_features)), sorted_values, color=colors)
                ax.set_yticks(range(len(sorted_features)))
                ax.set_yticklabels([f"{f} = {v:.1f}" for f, v in zip(sorted_features, sorted_feature_vals)])
                ax.set_xlabel("Impact on Price ($)")
                ax.set_title("Feature Impact on Predicted Price")
                ax.axvline(x=0, color='black', linewidth=0.5)
                
                # Add value labels
                for bar, val in zip(bars, sorted_values):
                    width = bar.get_width()
                    label_x = width + (5000 if width > 0 else -5000)
                    ax.text(label_x, bar.get_y() + bar.get_height()/2, 
                           f'${val:+,.0f}', va='center', fontsize=10)
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
                
                # Explanation text
                st.markdown("### 📝 Interpretation")
                st.markdown("""
                - **Red bars** indicate features that **increase** the predicted price
                - **Green bars** indicate features that **decrease** the predicted price
                - The length of each bar shows the magnitude of the impact
                """)
                
                # Feature breakdown table
                st.markdown("### 📋 Detailed Breakdown")
                breakdown_df = pd.DataFrame({
                    'Feature': feature_names,
                    'Value': feature_values,
                    'Impact ($)': shap_values,
                    'Direction': ['↑ Increases' if v > 0 else '↓ Decreases' for v in shap_values]
                })
                st.dataframe(breakdown_df, use_container_width=True)
                
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Could not get explanation: {e}")
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Tab 3: Model Info
with tabs[2]:
    st.header("📈 Model Information")
    
    try:
        info = requests.get(f"{API_URL}/", timeout=5).json()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🤖 Model Status")
            st.json({
                "Service": info.get('service', 'N/A'),
                "Version": info.get('version', 'N/A'),
                "Model Loaded": info.get('model_loaded', False),
                "Explainer Loaded": info.get('explainer_loaded', False),
                "Run ID": info.get('model_run_id', 'N/A')
            })
        
        with col2:
            st.markdown("### 📊 Model Details")
            st.markdown("""
            **Algorithm:** Random Forest Regressor
            
            **Features:**
            - `bed` - Number of bedrooms
            - `bath` - Number of bathrooms
            - `acre_lot` - Lot size in acres
            - `house_size` - Living area in sqft
            
            **Training Data:** ~360,000 US real estate listings
            
            **Metrics:**
            - RMSE: ~$1.4M (high variance in luxury properties)
            - R²: Varies by run
            """)
            
    except Exception as e:
        st.error(f"Could not fetch model info: {e}")
    
    st.markdown("---")
    st.markdown("### 🔗 Related Links")
    st.markdown("""
    - [MLflow Dashboard](http://localhost:30500) - View experiments and models
    - [Airflow Dashboard](http://localhost:30080) - View ML pipelines
    - [Argo CD Dashboard](http://localhost:30443) - View deployments
    """)
