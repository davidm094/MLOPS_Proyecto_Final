"""
Data preprocessing module for the MLOps pipeline.
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_data(df):
    """
    Comprehensive data cleaning for real estate data.
    
    Steps:
    1. Drop duplicates
    2. Convert types
    3. Handle missing values
    4. Remove outliers
    5. Validate data ranges
    
    Args:
        df: Raw DataFrame from API
        
    Returns:
        Cleaned DataFrame
    """
    logger.info(f"Starting data cleaning. Input rows: {len(df)}")
    
    # Make a copy to avoid modifying original
    df = df.copy()
    
    # 1. Drop duplicates
    initial_rows = len(df)
    df = df.drop_duplicates()
    logger.info(f"Removed {initial_rows - len(df)} duplicate rows")
    
    # 2. Convert types
    # Numerical columns
    num_cols = ['bed', 'bath', 'acre_lot', 'house_size', 'price']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # String columns
    str_cols = ['zip_code', 'city', 'state', 'status', 'street', 'brokered_by']
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).replace('nan', '')
    
    # 3. Handle missing values
    # Drop rows with missing critical values
    critical_cols = ['price', 'bed', 'bath', 'house_size']
    for col in critical_cols:
        if col in df.columns:
            before = len(df)
            df = df.dropna(subset=[col])
            if before - len(df) > 0:
                logger.info(f"Dropped {before - len(df)} rows with missing {col}")
    
    # Fill missing non-critical values
    if 'acre_lot' in df.columns:
        df['acre_lot'] = df['acre_lot'].fillna(df['acre_lot'].median())
    
    if 'state' in df.columns:
        df['state'] = df['state'].replace('', 'Unknown')
        df['state'] = df['state'].replace('nan', 'Unknown')
    
    if 'status' in df.columns:
        df['status'] = df['status'].replace('', 'for_sale')
        df['status'] = df['status'].replace('nan', 'for_sale')
    
    # 4. Remove outliers
    # Price outliers (keep 1st to 99th percentile)
    if 'price' in df.columns and len(df) > 100:
        p1, p99 = df['price'].quantile(0.01), df['price'].quantile(0.99)
        before = len(df)
        df = df[(df['price'] >= p1) & (df['price'] <= p99)]
        logger.info(f"Removed {before - len(df)} price outliers (range: ${p1:,.0f} - ${p99:,.0f})")
    
    # House size outliers
    if 'house_size' in df.columns and len(df) > 100:
        p1, p99 = df['house_size'].quantile(0.01), df['house_size'].quantile(0.99)
        before = len(df)
        df = df[(df['house_size'] >= p1) & (df['house_size'] <= p99)]
        logger.info(f"Removed {before - len(df)} house_size outliers")
    
    # 5. Validate data ranges
    # Ensure positive values
    for col in ['price', 'bed', 'bath', 'acre_lot', 'house_size']:
        if col in df.columns:
            df = df[df[col] > 0]
    
    # Reasonable ranges
    if 'bed' in df.columns:
        df = df[(df['bed'] >= 1) & (df['bed'] <= 20)]
    
    if 'bath' in df.columns:
        df = df[(df['bath'] >= 0.5) & (df['bath'] <= 15)]
    
    if 'acre_lot' in df.columns:
        df = df[(df['acre_lot'] >= 0.001) & (df['acre_lot'] <= 1000)]
    
    if 'house_size' in df.columns:
        df = df[(df['house_size'] >= 100) & (df['house_size'] <= 50000)]
    
    logger.info(f"Data cleaning complete. Output rows: {len(df)}")
    
    return df


def get_preprocessor():
    """
    Returns a Scikit-learn ColumnTransformer for preprocessing.
    
    This is used for more advanced preprocessing in the training pipeline.
    """
    categorical_features = ['status', 'city', 'state', 'zip_code']
    numerical_features = ['bed', 'bath', 'acre_lot', 'house_size']

    numerical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numerical_transformer, numerical_features),
            ('cat', categorical_transformer, categorical_features)
        ])

    return preprocessor


def prepare_training_data(df, target_col='price'):
    """
    Prepare data for model training.
    
    Args:
        df: Cleaned DataFrame
        target_col: Name of target column
        
    Returns:
        X: Feature DataFrame
        y: Target Series
    """
    # Ensure data is clean
    df = clean_data(df)
    
    # Define features
    feature_cols = ['bed', 'bath', 'acre_lot', 'house_size']
    
    # Filter to only available columns
    feature_cols = [c for c in feature_cols if c in df.columns]
    
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in DataFrame")
    
    X = df[feature_cols].copy()
    y = df[target_col].copy()
    
    logger.info(f"Prepared training data: {len(X)} samples, {len(feature_cols)} features")
    
    return X, y


def validate_data(df, required_cols=None):
    """
    Validate that DataFrame has required columns and data quality.
    
    Args:
        df: DataFrame to validate
        required_cols: List of required column names
        
    Returns:
        bool: True if valid, raises ValueError otherwise
    """
    if required_cols is None:
        required_cols = ['bed', 'bath', 'acre_lot', 'house_size', 'price']
    
    # Check for required columns
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Check for empty DataFrame
    if len(df) == 0:
        raise ValueError("DataFrame is empty")
    
    # Check for all-null columns
    for col in required_cols:
        if df[col].isna().all():
            raise ValueError(f"Column '{col}' is all null")
    
    logger.info(f"Data validation passed: {len(df)} rows, {len(df.columns)} columns")
    return True
