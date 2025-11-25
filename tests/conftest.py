"""
Pytest configuration and shared fixtures for MLOps tests.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
import sys
import os

# Mock fastapi middleware module before any imports
# This is needed because the API now uses BaseHTTPMiddleware
if 'fastapi.middleware.base' not in sys.modules:
    mock_middleware = MagicMock()
    mock_middleware.BaseHTTPMiddleware = MagicMock
    sys.modules['fastapi.middleware.base'] = mock_middleware

# Add apps to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'api', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'airflow', 'dags', 'src'))

@pytest.fixture
def sample_raw_data():
    """Sample raw data from the API."""
    return pd.DataFrame({
        'brokered_by': ['Agent1', 'Agent2', 'Agent3', None, 'Agent5'],
        'status': ['for_sale', 'sold', 'for_sale', 'for_sale', 'sold'],
        'price': [500000, 750000, 300000, 1200000, 450000],
        'bed': [3, 4, 2, 5, 3],
        'bath': [2, 3, 1, 4, 2],
        'acre_lot': [0.25, 0.5, 0.1, 1.0, 0.3],
        'street': ['123 Main St', '456 Oak Ave', '789 Pine Rd', '321 Elm Blvd', '654 Maple Dr'],
        'city': ['Los Angeles', 'San Francisco', 'San Diego', 'Sacramento', 'Oakland'],
        'state': ['California', 'California', 'California', 'California', 'California'],
        'zip_code': ['90001', '94102', '92101', '95814', '94601'],
        'house_size': [1800, 2500, 1200, 3500, 1600],
        'prev_sold_date': ['2020-01-15', '2019-06-20', None, '2021-03-10', '2018-11-05']
    })

@pytest.fixture
def sample_clean_data():
    """Sample cleaned data ready for training."""
    return pd.DataFrame({
        'bed': [3.0, 4.0, 2.0, 5.0, 3.0],
        'bath': [2.0, 3.0, 1.0, 4.0, 2.0],
        'acre_lot': [0.25, 0.5, 0.1, 1.0, 0.3],
        'house_size': [1800.0, 2500.0, 1200.0, 3500.0, 1600.0],
        'price': [500000.0, 750000.0, 300000.0, 1200000.0, 450000.0],
        'state': ['California', 'California', 'California', 'California', 'California'],
        'status': ['for_sale', 'sold', 'for_sale', 'for_sale', 'sold']
    })

@pytest.fixture
def sample_property_input():
    """Sample property input for prediction."""
    return {
        'bed': 3.0,
        'bath': 2.0,
        'acre_lot': 0.25,
        'house_size': 1800.0,
        'state': 'California',
        'status': 'for_sale'
    }

@pytest.fixture
def mock_model():
    """Mock ML model for testing."""
    model = MagicMock()
    model.predict.return_value = np.array([500000.0])
    return model

@pytest.fixture
def mock_explainer():
    """Mock SHAP explainer for testing."""
    explainer = MagicMock()
    explainer.shap_values.return_value = np.array([[100.0, 200.0, 50.0, 150.0]])
    explainer.expected_value = 400000.0
    return explainer

@pytest.fixture
def reference_data_for_drift():
    """Reference data for drift detection tests."""
    np.random.seed(42)
    n = 1000
    return pd.DataFrame({
        'bed': np.random.normal(3, 1, n).clip(1, 10),
        'bath': np.random.normal(2, 0.5, n).clip(1, 5),
        'acre_lot': np.random.exponential(0.3, n).clip(0.01, 10),
        'house_size': np.random.normal(1800, 500, n).clip(500, 10000),
        'price': np.random.normal(500000, 150000, n).clip(50000, 2000000)
    })

@pytest.fixture
def current_data_no_drift(reference_data_for_drift):
    """Current data with no drift (similar distribution)."""
    np.random.seed(43)
    n = 500
    return pd.DataFrame({
        'bed': np.random.normal(3, 1, n).clip(1, 10),
        'bath': np.random.normal(2, 0.5, n).clip(1, 5),
        'acre_lot': np.random.exponential(0.3, n).clip(0.01, 10),
        'house_size': np.random.normal(1800, 500, n).clip(500, 10000),
        'price': np.random.normal(500000, 150000, n).clip(50000, 2000000)
    })

@pytest.fixture
def current_data_with_drift():
    """Current data with significant drift."""
    np.random.seed(44)
    n = 500
    return pd.DataFrame({
        'bed': np.random.normal(5, 1, n).clip(1, 10),  # Shifted mean
        'bath': np.random.normal(3, 0.5, n).clip(1, 5),  # Shifted mean
        'acre_lot': np.random.exponential(1.0, n).clip(0.01, 10),  # Different distribution
        'house_size': np.random.normal(2500, 500, n).clip(500, 10000),  # Shifted mean
        'price': np.random.normal(800000, 200000, n).clip(50000, 3000000)  # Shifted mean
    })

