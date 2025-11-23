import pandas as pd
import numpy as np
from alibi_detect.cd import KolmogorovSmirnov
import logging

def detect_drift(reference_df, current_df, p_value_threshold=0.05):
    """
    Detects data drift using Kolmogorov-Smirnov test on numerical columns.
    Returns True if drift is detected, False otherwise.
    """
    numerical_features = ['bed', 'bath', 'acre_lot', 'house_size', 'price']
    drift_detected = False
    
    for feature in numerical_features:
        if feature in reference_df.columns and feature in current_df.columns:
            ref_data = reference_df[feature].dropna().values
            curr_data = current_df[feature].dropna().values
            
            # Simple KS test implementation or use alibi/evidently
            # Using alibi-detect's KS logic concept (simplified here for dependency minimization if needed, 
            # but we added alibi-detect to requirements)
            
            # Use scipy ks_2samp for simplicity and reliability
            from scipy.stats import ks_2samp
            statistic, p_value = ks_2samp(ref_data, curr_data)
            
            if p_value < p_value_threshold:
                logging.warning(f"Drift detected in feature: {feature} (p-value: {p_value})")
                drift_detected = True
                
    return drift_detected

