import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

def clean_data(df):
    """
    Basic data cleaning.
    """
    # Drop duplicates
    df = df.drop_duplicates()
    
    # Convert types if necessary (e.g., zip_code to string)
    if 'zip_code' in df.columns:
        df['zip_code'] = df['zip_code'].astype(str)
        
    # Handle missing values (simplified for now)
    # Numerical columns
    num_cols = ['bed', 'bath', 'acre_lot', 'house_size']
    for col in num_cols:
        if col in df.columns:
             df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows with missing target 'price'
    df = df.dropna(subset=['price'])
    
    return df

def get_preprocessor():
    """
    Returns a Scikit-learn ColumnTransformer for preprocessing.
    """
    categorical_features = ['status', 'city', 'state', 'zip_code'] # simplified
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

