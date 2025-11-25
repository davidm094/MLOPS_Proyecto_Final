import pandas as pd
import numpy as np
import logging
from scipy.stats import ks_2samp

def detect_drift(reference_df, current_df, p_value_threshold=0.05, return_details=False):
    """
    Detects data drift using Kolmogorov-Smirnov test on numerical columns.
    
    Args:
        reference_df: Reference DataFrame (baseline)
        current_df: Current DataFrame to compare
        p_value_threshold: Threshold for drift detection (default 0.05)
        return_details: If True, returns (drift_detected, details_dict)
    
    Returns:
        If return_details=False: bool (drift detected)
        If return_details=True: tuple (bool, dict with drift details)
    """
    numerical_features = ['bed', 'bath', 'acre_lot', 'house_size', 'price']
    drift_detected = False
    features_with_drift = []
    drift_scores = {}
    max_drift_score = 0.0
    
    logging.info("="*50)
    logging.info("DRIFT DETECTION ANALYSIS")
    logging.info("="*50)
    logging.info(f"Reference samples: {len(reference_df)}")
    logging.info(f"Current samples: {len(current_df)}")
    logging.info(f"P-value threshold: {p_value_threshold}")
    logging.info("-"*50)
    
    for feature in numerical_features:
        if feature in reference_df.columns and feature in current_df.columns:
            ref_data = reference_df[feature].dropna().values
            curr_data = current_df[feature].dropna().values
            
            if len(ref_data) < 10 or len(curr_data) < 10:
                logging.warning(f"  {feature}: Insufficient data for KS test")
                continue
            
            # Kolmogorov-Smirnov test
            statistic, p_value = ks_2samp(ref_data, curr_data)
            
            drift_scores[feature] = {
                'statistic': statistic,
                'p_value': p_value,
                'drift': p_value < p_value_threshold
            }
            
            if p_value < p_value_threshold:
                logging.warning(f"  {feature}: DRIFT DETECTED (KS={statistic:.4f}, p={p_value:.6f})")
                drift_detected = True
                features_with_drift.append(feature)
                if statistic > max_drift_score:
                    max_drift_score = statistic
            else:
                logging.info(f"  {feature}: No drift (KS={statistic:.4f}, p={p_value:.6f})")
    
    logging.info("-"*50)
    logging.info(f"RESULT: {'DRIFT DETECTED' if drift_detected else 'NO DRIFT'}")
    if features_with_drift:
        logging.info(f"Features with drift: {features_with_drift}")
    logging.info("="*50)
    
    if return_details:
        details = {
            'drift_detected': drift_detected,
            'features_with_drift': features_with_drift,
            'drift_scores': drift_scores,
            'max_drift_score': max_drift_score,
            'reference_samples': len(reference_df),
            'current_samples': len(current_df)
        }
        return drift_detected, details
    
    return drift_detected

def calculate_psi(reference, current, bins=10):
    """
    Calculate Population Stability Index (PSI) for a feature.
    PSI < 0.1: No significant change
    PSI 0.1-0.25: Moderate change
    PSI > 0.25: Significant change
    """
    # Create bins based on reference data
    min_val = min(reference.min(), current.min())
    max_val = max(reference.max(), current.max())
    
    if min_val == max_val:
        return 0.0
    
    bin_edges = np.linspace(min_val, max_val, bins + 1)
    
    # Calculate proportions in each bin
    ref_counts, _ = np.histogram(reference, bins=bin_edges)
    curr_counts, _ = np.histogram(current, bins=bin_edges)
    
    # Add small value to avoid division by zero
    ref_proportions = (ref_counts + 1) / (len(reference) + bins)
    curr_proportions = (curr_counts + 1) / (len(current) + bins)
    
    # Calculate PSI
    psi = np.sum((curr_proportions - ref_proportions) * np.log(curr_proportions / ref_proportions))
    
    return psi
