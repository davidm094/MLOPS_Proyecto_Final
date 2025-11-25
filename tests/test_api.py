"""
Unit tests for the FastAPI prediction API.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
import sys
import os

# Mock external dependencies before importing the app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'api', 'src'))


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_health_endpoint_returns_200(self):
        """Test that /health returns 200."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.get_db_engine') as mock_engine:
                    mock_engine.return_value = None
                    from main import app
                    client = TestClient(app)
                    response = client.get("/health")
                    assert response.status_code == 200
                    data = response.json()
                    assert "status" in data
                    assert "model_loaded" in data
                    assert "database_connected" in data
    
    def test_root_endpoint_returns_info(self):
        """Test that / returns API info."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                from main import app
                client = TestClient(app)
                response = client.get("/")
                assert response.status_code == 200
                data = response.json()
                assert "service" in data
                assert "version" in data


class TestPredictionEndpoint:
    """Tests for the /predict endpoint."""
    
    def test_predict_with_valid_input(self, sample_property_input, mock_model):
        """Test prediction with valid input."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model', mock_model):
                    with patch('main.model_version', 'test_v1'):
                        with patch('main.model_stage', 'Production'):
                            with patch('main.model_run_id', 'test_run_123'):
                                with patch('main.feature_names', ['bed', 'bath', 'acre_lot', 'house_size']):
                                    with patch('main.state_means', {'California': 800000}):
                                        with patch('main.log_inference'):
                                            from main import app
                                            client = TestClient(app)
                                            response = client.post("/predict", json=sample_property_input)
                                            assert response.status_code == 200
                                            data = response.json()
                                            assert "price" in data
                                            assert "model_version" in data
                                            assert "request_id" in data
                                            assert data["price"] > 0
    
    def test_predict_with_missing_fields_uses_defaults(self, mock_model):
        """Test that missing fields use default values."""
        minimal_input = {"bed": 2}
        
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model', mock_model):
                    with patch('main.model_version', 'test_v1'):
                        with patch('main.model_stage', 'Production'):
                            with patch('main.model_run_id', 'test_run_123'):
                                with patch('main.feature_names', ['bed', 'bath', 'acre_lot', 'house_size']):
                                    with patch('main.state_means', {}):
                                        with patch('main.log_inference'):
                                            from main import app
                                            client = TestClient(app)
                                            response = client.post("/predict", json=minimal_input)
                                            assert response.status_code == 200
    
    def test_predict_without_model_returns_503(self):
        """Test that prediction without model returns 503."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model', None):
                    from main import app
                    client = TestClient(app)
                    response = client.post("/predict", json={"bed": 3})
                    assert response.status_code == 503
    
    def test_predict_with_invalid_input_returns_422(self):
        """Test that invalid input returns 422."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                from main import app
                client = TestClient(app)
                # Send invalid data type
                response = client.post("/predict", json={"bed": "invalid"})
                assert response.status_code == 422


class TestExplainEndpoint:
    """Tests for the /explain endpoint."""
    
    def test_explain_with_valid_input(self, sample_property_input, mock_model, mock_explainer):
        """Test explanation with valid input."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model', mock_model):
                    with patch('main.explainer', mock_explainer):
                        with patch('main.model_version', 'test_v1'):
                            with patch('main.feature_names', ['bed', 'bath', 'acre_lot', 'house_size']):
                                with patch('main.state_means', {'California': 800000}):
                                    from main import app
                                    client = TestClient(app)
                                    response = client.post("/explain", json=sample_property_input)
                                    assert response.status_code == 200
                                    data = response.json()
                                    assert "price" in data
                                    assert "shap_values" in data
                                    assert "base_value" in data
                                    assert "feature_names" in data
    
    def test_explain_without_explainer_returns_503(self, mock_model):
        """Test that explain without explainer returns 503."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model', mock_model):
                    with patch('main.explainer', None):
                        from main import app
                        client = TestClient(app)
                        response = client.post("/explain", json={"bed": 3})
                        assert response.status_code == 503


class TestModelEndpoints:
    """Tests for model-related endpoints."""
    
    def test_model_info_endpoint(self):
        """Test /model endpoint returns model info."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model_version', 'v1'):
                    with patch('main.model_stage', 'Production'):
                        with patch('main.model_run_id', 'run_123'):
                            with patch('main.model', MagicMock()):
                                with patch('main.explainer', MagicMock()):
                                    with patch('main.state_means', {'CA': 500000}):
                                        with patch('main.feature_names', ['bed', 'bath']):
                                            from main import app
                                            client = TestClient(app)
                                            response = client.get("/model")
                                            assert response.status_code == 200
                                            data = response.json()
                                            assert data["model_version"] == "v1"
                                            assert data["model_stage"] == "Production"
                                            assert data["model_loaded"] == True
    
    def test_states_endpoint(self):
        """Test /states endpoint returns available states."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.state_means', {'California': 800000, 'Texas': 400000}):
                    from main import app
                    client = TestClient(app)
                    response = client.get("/states")
                    assert response.status_code == 200
                    data = response.json()
                    assert "states" in data
                    assert len(data["states"]) == 2


class TestBatchPrediction:
    """Tests for batch prediction endpoint."""
    
    def test_batch_predict_multiple_properties(self, mock_model):
        """Test batch prediction with multiple properties."""
        batch_input = [
            {"bed": 3, "bath": 2, "house_size": 1800, "state": "California"},
            {"bed": 4, "bath": 3, "house_size": 2500, "state": "Texas"},
            {"bed": 2, "bath": 1, "house_size": 1200, "state": "Florida"}
        ]
        
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.model', mock_model):
                    with patch('main.model_version', 'test_v1'):
                        with patch('main.feature_names', ['bed', 'bath', 'acre_lot', 'house_size']):
                            with patch('main.state_means', {'California': 800000, 'Texas': 400000, 'Florida': 500000}):
                                from main import app
                                client = TestClient(app)
                                response = client.post("/batch_predict", json=batch_input)
                                assert response.status_code == 200
                                data = response.json()
                                assert "predictions" in data
                                assert len(data["predictions"]) == 3


class TestMetricsEndpoint:
    """Tests for metrics endpoints."""
    
    def test_metrics_endpoint_exists(self):
        """Test that /metrics endpoint exists for Prometheus."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                from main import app
                client = TestClient(app)
                response = client.get("/metrics")
                assert response.status_code == 200
                # Prometheus metrics are returned as text
                assert "http_requests" in response.text or "predictions" in response.text or "process" in response.text


class TestFeaturePreparation:
    """Tests for feature preparation logic."""
    
    def test_prepare_features_creates_correct_columns(self):
        """Test that prepare_features creates all engineered features."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.state_means', {'California': 800000}):
                    with patch('main.feature_names', None):  # Allow all features
                        from main import prepare_features, PropertyInput
                        
                        input_data = PropertyInput(
                            bed=3,
                            bath=2,
                            acre_lot=0.25,
                            house_size=1800,
                            state="California",
                            status="for_sale"
                        )
                        
                        df = prepare_features(input_data)
                        
                        # Check that engineered features are created
                        assert 'bed' in df.columns
                        assert 'bath' in df.columns
                        assert 'acre_lot' in df.columns
                        assert 'house_size' in df.columns
                        assert 'state_price_mean' in df.columns
                        assert 'bed_bath_interaction' in df.columns
                        assert 'size_per_bed' in df.columns
                        assert 'total_rooms' in df.columns
    
    def test_prepare_features_handles_unknown_state(self):
        """Test that unknown states get default mean price."""
        with patch.dict(os.environ, {
            'MLFLOW_TRACKING_URI': 'http://mock:5000',
            'DATABASE_URL': 'postgresql://mock:mock@localhost/mock'
        }):
            with patch('main.load_production_model'):
                with patch('main.state_means', {'California': 800000, 'Texas': 400000}):
                    with patch('main.feature_names', None):
                        from main import prepare_features, PropertyInput
                        
                        input_data = PropertyInput(
                            bed=3,
                            bath=2,
                            acre_lot=0.25,
                            house_size=1800,
                            state="UnknownState",  # Unknown state
                            status="for_sale"
                        )
                        
                        df = prepare_features(input_data)
                        
                        # Should use mean of known states
                        expected_mean = (800000 + 400000) / 2
                        assert df['state_price_mean'].iloc[0] == expected_mean

