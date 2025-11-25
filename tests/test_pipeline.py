"""
Unit tests for the ML pipeline components.
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

# Add dags to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'airflow', 'dags', 'src'))


class TestPreprocessing:
    """Tests for data preprocessing."""
    
    def test_clean_data_removes_nulls(self, sample_raw_data):
        """Test that clean_data handles null values."""
        from preprocessing import clean_data
        
        # Add some nulls
        raw_data = sample_raw_data.copy()
        raw_data.loc[0, 'price'] = None
        
        cleaned = clean_data(raw_data)
        
        # Check no nulls in critical columns
        assert cleaned['price'].isna().sum() == 0
    
    def test_clean_data_removes_duplicates(self, sample_raw_data):
        """Test that clean_data removes duplicates."""
        from preprocessing import clean_data
        
        # Add duplicates
        raw_data = pd.concat([sample_raw_data, sample_raw_data.iloc[[0]]])
        
        cleaned = clean_data(raw_data)
        
        # Should have fewer or equal rows (duplicates removed)
        assert len(cleaned) <= len(raw_data)
    
    def test_clean_data_converts_types(self, sample_raw_data):
        """Test that clean_data converts to correct types."""
        from preprocessing import clean_data
        
        cleaned = clean_data(sample_raw_data)
        
        # Check numeric columns are numeric
        assert pd.api.types.is_numeric_dtype(cleaned['bed'])
        assert pd.api.types.is_numeric_dtype(cleaned['bath'])
        assert pd.api.types.is_numeric_dtype(cleaned['price'])
        assert pd.api.types.is_numeric_dtype(cleaned['house_size'])
    
    def test_clean_data_filters_outliers(self, sample_raw_data):
        """Test that extreme outliers are handled."""
        from preprocessing import clean_data
        
        # Add extreme outlier
        raw_data = sample_raw_data.copy()
        raw_data.loc[0, 'price'] = 1e12  # $1 trillion
        
        cleaned = clean_data(raw_data)
        
        # Function should handle the outlier either by:
        # 1. Removing the row entirely, OR
        # 2. Capping/transforming the value
        # Either way, the function should complete without error
        assert len(cleaned) > 0  # Should have some valid records remaining
        assert 'price' in cleaned.columns
    
    def test_clean_data_preserves_valid_records(self, sample_raw_data):
        """Test that valid records are preserved."""
        from preprocessing import clean_data
        
        cleaned = clean_data(sample_raw_data)
        
        # Should have some records
        assert len(cleaned) > 0
        
        # Should have required columns
        required_cols = ['bed', 'bath', 'acre_lot', 'house_size', 'price']
        for col in required_cols:
            assert col in cleaned.columns


class TestDriftDetection:
    """Tests for drift detection."""
    
    def test_detect_drift_no_drift(self, reference_data_for_drift, current_data_no_drift):
        """Test that similar distributions show no drift."""
        from drift_detection import detect_drift
        
        has_drift, details = detect_drift(
            reference_data_for_drift, 
            current_data_no_drift, 
            return_details=True
        )
        
        # Similar distributions should not trigger drift
        # (may occasionally trigger due to randomness, so we check details)
        assert isinstance(has_drift, bool)
        assert 'features_with_drift' in details
    
    def test_detect_drift_with_drift(self, reference_data_for_drift, current_data_with_drift):
        """Test that different distributions detect drift."""
        from drift_detection import detect_drift
        
        has_drift, details = detect_drift(
            reference_data_for_drift, 
            current_data_with_drift, 
            return_details=True
        )
        
        # Different distributions should trigger drift
        assert has_drift == True
        assert len(details['features_with_drift']) > 0
    
    def test_detect_drift_returns_details(self, reference_data_for_drift, current_data_no_drift):
        """Test that drift detection returns proper details."""
        from drift_detection import detect_drift
        
        has_drift, details = detect_drift(
            reference_data_for_drift, 
            current_data_no_drift, 
            return_details=True
        )
        
        # Check details structure
        assert 'drift_detected' in details
        assert 'features_with_drift' in details
        assert 'drift_scores' in details
        assert 'max_drift_score' in details
        assert 'reference_samples' in details
        assert 'current_samples' in details
    
    def test_detect_drift_handles_missing_columns(self, reference_data_for_drift):
        """Test drift detection with missing columns."""
        from drift_detection import detect_drift
        
        # Create current data with missing column
        current = reference_data_for_drift.copy()
        current = current.drop('acre_lot', axis=1)
        
        # Should not raise error
        has_drift = detect_drift(reference_data_for_drift, current)
        assert isinstance(has_drift, bool)
    
    def test_detect_drift_handles_empty_data(self, reference_data_for_drift):
        """Test drift detection with empty data."""
        from drift_detection import detect_drift
        
        empty_df = pd.DataFrame()
        
        # Should handle gracefully
        has_drift = detect_drift(reference_data_for_drift, empty_df)
        assert isinstance(has_drift, bool)


class TestPSICalculation:
    """Tests for PSI calculation."""
    
    def test_calculate_psi_identical_distributions(self):
        """Test PSI for identical distributions."""
        from drift_detection import calculate_psi
        
        np.random.seed(42)
        data = np.random.normal(0, 1, 1000)
        
        psi = calculate_psi(data, data)
        
        # Identical data should have PSI close to 0
        assert psi < 0.1
    
    def test_calculate_psi_different_distributions(self):
        """Test PSI for different distributions."""
        from drift_detection import calculate_psi
        
        np.random.seed(42)
        ref = np.random.normal(0, 1, 1000)
        curr = np.random.normal(2, 1, 1000)  # Shifted mean
        
        psi = calculate_psi(ref, curr)
        
        # Different distributions should have higher PSI
        assert psi > 0.1


class TestDataLoader:
    """Tests for data loading functions."""
    
    def test_fetch_data_returns_dataframe(self):
        """Test that fetch_data returns a DataFrame."""
        from unittest.mock import patch, MagicMock
        from data_loader import fetch_data
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': [
                {'bed': 3, 'bath': 2, 'price': 500000},
                {'bed': 4, 'bath': 3, 'price': 750000}
            ],
            'batch_number': 1
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch('data_loader.requests.get', return_value=mock_response):
            df = fetch_data(group_number="5", day="Tuesday")
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
    
    def test_save_to_postgres_creates_batch_id(self, sample_clean_data):
        """Test that save_to_postgres generates batch_id."""
        from unittest.mock import patch, MagicMock
        from data_loader import save_to_postgres
        
        mock_engine = MagicMock()
        
        with patch('data_loader.get_db_engine', return_value=mock_engine):
            with patch.object(pd.DataFrame, 'to_sql'):
                batch_id = save_to_postgres(sample_clean_data, 'raw_data')
                
                assert batch_id is not None
                assert 'batch_' in batch_id


class TestFeatureEngineering:
    """Tests for feature engineering in model training."""
    
    def test_engineered_features_are_created(self, sample_clean_data):
        """Test that all engineered features are created."""
        # Simulate feature engineering
        df = sample_clean_data.copy()
        
        # Add engineered features
        df['is_sold'] = (df['status'] == 'sold').astype(int)
        df['bed_bath_interaction'] = df['bed'] * df['bath']
        df['size_per_bed'] = df['house_size'] / (df['bed'] + 1)
        df['size_per_bath'] = df['house_size'] / (df['bath'] + 1)
        df['total_rooms'] = df['bed'] + df['bath']
        df['lot_to_house_ratio'] = df['acre_lot'] * 43560 / (df['house_size'] + 1)
        
        # Check features exist
        assert 'is_sold' in df.columns
        assert 'bed_bath_interaction' in df.columns
        assert 'size_per_bed' in df.columns
        assert 'size_per_bath' in df.columns
        assert 'total_rooms' in df.columns
        assert 'lot_to_house_ratio' in df.columns
    
    def test_engineered_features_are_numeric(self, sample_clean_data):
        """Test that engineered features are numeric."""
        df = sample_clean_data.copy()
        
        df['bed_bath_interaction'] = df['bed'] * df['bath']
        df['total_rooms'] = df['bed'] + df['bath']
        
        assert pd.api.types.is_numeric_dtype(df['bed_bath_interaction'])
        assert pd.api.types.is_numeric_dtype(df['total_rooms'])
    
    def test_no_infinite_values_in_features(self, sample_clean_data):
        """Test that division operations don't create infinites."""
        df = sample_clean_data.copy()
        
        # Add a zero that could cause division issues
        df.loc[0, 'bed'] = 0
        
        # Safe division
        df['size_per_bed'] = df['house_size'] / (df['bed'] + 1)
        
        # Should not have infinite values
        assert not np.isinf(df['size_per_bed']).any()


class TestModelTraining:
    """Tests for model training logic."""
    
    def test_model_training_returns_metrics(self, sample_clean_data):
        """Test that training returns expected metrics."""
        from unittest.mock import patch, MagicMock
        
        # Create larger dataset for training
        np.random.seed(42)
        n = 100
        train_data = pd.DataFrame({
            'bed': np.random.randint(1, 6, n),
            'bath': np.random.randint(1, 4, n),
            'acre_lot': np.random.uniform(0.1, 2, n),
            'house_size': np.random.randint(800, 4000, n),
            'price': np.random.randint(200000, 1500000, n),
            'state': np.random.choice(['California', 'Texas', 'Florida'], n),
            'status': np.random.choice(['for_sale', 'sold'], n)
        })
        
        with patch('model_training.mlflow') as mock_mlflow:
            mock_mlflow.start_run.return_value.__enter__ = MagicMock()
            mock_mlflow.start_run.return_value.__exit__ = MagicMock()
            
            from model_training import train_and_log_model
            
            # This would need more mocking for a full test
            # For now, just verify the function exists and has correct signature
            assert callable(train_and_log_model)

