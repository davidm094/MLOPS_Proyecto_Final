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

# Custom CSS
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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    .price-value {
        font-size: 3rem;
        font-weight: bold;
        color: white;
    }
    .price-label {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🏡 Real Estate Price Predictor</p>', unsafe_allow_html=True)

# Load states from API
@st.cache_data(ttl=300)
def get_available_states():
    try:
        resp = requests.get(f"{API_URL}/states", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [s['state'] for s in data.get('states', [])]
    except:
        pass
    # Fallback list of common states
    return ["California", "Texas", "Florida", "New York", "Arizona", "Colorado", 
            "Washington", "Oregon", "Nevada", "Hawaii", "Massachusetts", "Illinois"]

# Sidebar
with st.sidebar:
    st.header("🔧 System Status")
    
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        model_info = requests.get(f"{API_URL}/", timeout=5).json()
        
        st.success("✅ API Connected")
        st.write(f"Model: v{model_info.get('model_version', 'N/A')}")
        st.write(f"Stage: {model_info.get('model_stage', 'N/A')}")
        st.write(f"Model Loaded: {'✅' if health.get('model_loaded') else '❌'}")
        st.write(f"Explainer: {'✅' if health.get('explainer_loaded') else '❌'}")
        
        if st.button("🔄 Reload Model"):
            try:
                reload_resp = requests.post(f"{API_URL}/reload", timeout=30)
                if reload_resp.status_code == 200:
                    st.success("Model reloaded!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Reload failed: {reload_resp.text}")
            except Exception as e:
                st.error(f"Error: {e}")
                
    except Exception as e:
        st.error(f"❌ API Unavailable: {e}")
    
    st.markdown("---")
    st.markdown("### 📊 Model Info")
    st.markdown("""
    **Algorithm:** HistGradientBoosting
    
    **Key Features:**
    - Property characteristics
    - Location (state) encoding
    - Feature interactions
    
    **Metrics:**
    - R²: ~0.47
    - MAPE: ~31%
    """)

# Main content
tabs = st.tabs(["🏠 Predict Price", "📊 SHAP Explanation", "🗺️ Compare Locations", "📈 Model Info"])

# Tab 1: Prediction
with tabs[0]:
    st.header("Enter Property Details")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        bed = st.number_input(
            "🛏️ Bedrooms",
            min_value=1.0,
            max_value=10.0,
            value=3.0,
            step=1.0
        )
        bath = st.number_input(
            "🚿 Bathrooms",
            min_value=1.0,
            max_value=10.0,
            value=2.0,
            step=0.5
        )
    
    with col2:
        acre_lot = st.number_input(
            "🌳 Lot Size (acres)",
            min_value=0.01,
            max_value=10.0,
            value=0.25,
            step=0.05,
            format="%.2f"
        )
        house_size = st.number_input(
            "📐 House Size (sqft)",
            min_value=100.0,
            max_value=15000.0,
            value=1800.0,
            step=100.0
        )
    
    with col3:
        states = get_available_states()
        state = st.selectbox(
            "📍 State",
            options=states,
            index=states.index("California") if "California" in states else 0,
            help="Location significantly impacts price"
        )
        status = st.selectbox(
            "📋 Status",
            options=["for_sale", "sold"],
            index=0
        )
    
    if st.button("🔮 Predict Price", type="primary", use_container_width=True):
        payload = {
            "bed": bed,
            "bath": bath,
            "acre_lot": acre_lot,
            "house_size": house_size,
            "state": state,
            "status": status
        }
        
        with st.spinner("Calculating..."):
            try:
                response = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                st.session_state['last_prediction'] = result
                st.session_state['last_payload'] = payload
                
                # Display result
                st.markdown(f"""
                <div class="prediction-box">
                    <p class="price-label">Estimated Property Value in {state}</p>
                    <p class="price-value">${result['price']:,.0f}</p>
                    <p class="price-label">Model v{result.get('model_version', 'N/A')} ({result.get('model_stage', 'N/A')})</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Metrics
                st.markdown("### 💡 Quick Insights")
                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    price_per_sqft = result['price'] / house_size if house_size > 0 else 0
                    st.metric("$/sqft", f"${price_per_sqft:,.0f}")
                with col_b:
                    price_per_bed = result['price'] / bed if bed > 0 else 0
                    st.metric("$/bedroom", f"${price_per_bed:,.0f}")
                with col_c:
                    price_per_bath = result['price'] / bath if bath > 0 else 0
                    st.metric("$/bathroom", f"${price_per_bath:,.0f}")
                with col_d:
                    price_per_acre = result['price'] / acre_lot if acre_lot > 0 else 0
                    st.metric("$/acre", f"${price_per_acre:,.0f}")
                    
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
                
                if response.status_code == 503:
                    st.warning("⚠️ SHAP explanations not available for this model type (HistGradientBoosting)")
                    st.info("The model uses HistGradientBoostingRegressor which doesn't support TreeSHAP directly.")
                else:
                    response.raise_for_status()
                    exp_data = response.json()
                    
                    shap_values = exp_data['shap_values']
                    base_value = exp_data['base_value']
                    feature_names = exp_data['feature_names']
                    feature_values = exp_data['feature_values']
                    predicted_price = exp_data['price']
                    
                    st.markdown(f"""
                    **Base Price:** ${base_value:,.0f}  
                    **Predicted Price:** ${predicted_price:,.0f}  
                    **Total Adjustment:** ${sum(shap_values):,.0f}
                    """)
                    
                    # SHAP Chart
                    fig, ax = plt.subplots(figsize=(10, 6))
                    
                    indices = np.argsort(np.abs(shap_values))[::-1]
                    sorted_features = [feature_names[i] for i in indices]
                    sorted_values = [shap_values[i] for i in indices]
                    sorted_feature_vals = [feature_values[i] for i in indices]
                    
                    colors = ['#e74c3c' if v > 0 else '#27ae60' for v in sorted_values]
                    
                    bars = ax.barh(range(len(sorted_features)), sorted_values, color=colors)
                    ax.set_yticks(range(len(sorted_features)))
                    ax.set_yticklabels([f"{f} = {v:.2f}" for f, v in zip(sorted_features, sorted_feature_vals)])
                    ax.set_xlabel("Impact on Price ($)")
                    ax.set_title("Feature Impact on Predicted Price")
                    ax.axvline(x=0, color='black', linewidth=0.5)
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close()
                    
                    st.markdown("""
                    - **Red bars**: Features that **increase** the price
                    - **Green bars**: Features that **decrease** the price
                    """)
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Tab 3: Compare Locations
with tabs[2]:
    st.header("🗺️ Compare Prices Across States")
    
    st.markdown("See how the same property would be priced in different states.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        compare_bed = st.number_input("Bedrooms", min_value=1.0, max_value=10.0, value=3.0, step=1.0, key="compare_bed")
        compare_bath = st.number_input("Bathrooms", min_value=1.0, max_value=10.0, value=2.0, step=0.5, key="compare_bath")
    
    with col2:
        compare_acre = st.number_input("Lot Size (acres)", min_value=0.01, max_value=10.0, value=0.25, step=0.05, key="compare_acre")
        compare_size = st.number_input("House Size (sqft)", min_value=100.0, max_value=15000.0, value=1800.0, step=100.0, key="compare_size")
    
    states_to_compare = st.multiselect(
        "Select states to compare",
        options=get_available_states(),
        default=["California", "Texas", "Florida", "New York", "Hawaii"]
    )
    
    if st.button("📊 Compare Prices", type="primary"):
        if not states_to_compare:
            st.warning("Please select at least one state")
        else:
            results = []
            
            with st.spinner("Calculating prices..."):
                for state in states_to_compare:
                    try:
                        payload = {
                            "bed": compare_bed,
                            "bath": compare_bath,
                            "acre_lot": compare_acre,
                            "house_size": compare_size,
                            "state": state,
                            "status": "for_sale"
                        }
                        resp = requests.post(f"{API_URL}/predict", json=payload, timeout=10)
                        if resp.status_code == 200:
                            price = resp.json()['price']
                            results.append({"State": state, "Price": price})
                    except:
                        pass
            
            if results:
                df = pd.DataFrame(results).sort_values("Price", ascending=False)
                
                # Bar chart
                fig, ax = plt.subplots(figsize=(10, 6))
                colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(df)))
                bars = ax.barh(df['State'], df['Price'], color=colors)
                ax.set_xlabel("Predicted Price ($)")
                ax.set_title(f"Price Comparison: {int(compare_bed)} bed, {compare_bath} bath, {int(compare_size)} sqft")
                
                for bar, price in zip(bars, df['Price']):
                    ax.text(bar.get_width() + 10000, bar.get_y() + bar.get_height()/2, 
                           f'${price:,.0f}', va='center')
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
                
                # Table
                df['Price'] = df['Price'].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Insights
                prices = [r['Price'] for r in results]
                min_state = results[prices.index(min(prices))]['State']
                max_state = results[prices.index(max(prices))]['State']
                diff = max(prices) - min(prices)
                
                st.markdown(f"""
                ### 💡 Insights
                - **Most expensive:** {max_state} (${max(prices):,.0f})
                - **Least expensive:** {min_state} (${min(prices):,.0f})
                - **Price difference:** ${diff:,.0f} ({diff/min(prices)*100:.0f}% more)
                """)

# Tab 4: Model Info
with tabs[3]:
    st.header("📈 Model Information")
    
    try:
        info = requests.get(f"{API_URL}/", timeout=5).json()
        model_info = requests.get(f"{API_URL}/model", timeout=5).json()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🤖 Current Model")
            st.json({
                "Name": model_info.get('model_name', 'N/A'),
                "Version": model_info.get('model_version', 'N/A'),
                "Stage": model_info.get('model_stage', 'N/A'),
                "Run ID": model_info.get('model_run_id', 'N/A')[:12] + "...",
                "Features": len(model_info.get('feature_names', [])),
                "States": len(model_info.get('available_states', []))
            })
        
        with col2:
            st.markdown("### 📊 Features Used")
            features = model_info.get('feature_names', [])
            if features:
                for f in features:
                    st.write(f"• `{f}`")
            else:
                st.write("Feature list not available")
        
        st.markdown("---")
        
        st.markdown("### 🎯 Model Performance")
        st.markdown("""
        | Metric | Value | Description |
        |--------|-------|-------------|
        | **R²** | ~0.47 | Explains 47% of price variance |
        | **RMSE** | ~$532K | Average prediction error |
        | **MAE** | ~$322K | Median prediction error |
        | **MAPE** | ~31% | Average percentage error |
        """)
        
        st.markdown("### 🔗 Quick Links")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("[🔬 MLflow](http://localhost:30500)")
        with col_b:
            st.markdown("[🌀 Airflow](http://localhost:30080)")
        with col_c:
            st.markdown("[🚀 Argo CD](http://localhost:30443)")
            
    except Exception as e:
        st.error(f"Could not fetch model info: {e}")
