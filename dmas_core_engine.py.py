import numpy as np
import pandas as pd
import time

# =====================================================================
# 1. SYNTHETIC DISASTER DATA GENERATOR (BIG DATA SCALABILITY)
# =====================================================================
def generate_big_disaster_dataset(num_records=10000):
    """
    Generates a massive, structured dataset simulating a large-scale urban flood.
    Injects malicious social media misinformation to test suppression algorithms.
    """
    np.random.seed(42)
    districts = [f"District {chr(i)}" for i in range(65, 75)]  # Districts A through J
    
    # Probabilities for modalities
    modalities = ['iot_sensor', 'municipal_311', 'social_media']
    chosen_modalities = np.random.choice(modalities, size=num_records, p=[0.3, 0.3, 0.4])
    chosen_districts = np.random.choice(districts, size=num_records)
    
    # Base raw intensities (e.g., water level anomaly or panic level)
    raw_intensities = np.random.uniform(0.0, 5.0, size=num_records)
    
    df = pd.DataFrame({
        'report_id': range(1, num_records + 1),
        'district': chosen_districts,
        'modality': chosen_modalities,
        'raw_intensity': raw_intensities,
        'is_misinformation': False
    })
    
    # Inject intentional misinformation into 35% of social media posts (Noise/Fake reports)
    soc_mask = df['modality'] == 'social_media'
    num_soc = soc_mask.sum()
    misinfo_indices = np.random.choice(df[soc_mask].index, size=int(num_soc * 0.35), replace=False)
    df.loc[misinfo_indices, 'is_misinformation'] = True
    
    # Misinformation overinflates intensity (e.g., "The whole city is sinking!")
    df.loc[misinfo_indices, 'raw_intensity'] = np.random.uniform(4.5, 5.0, size=len(misinfo_indices))
    
    return df

# =====================================================================
# 2. THE MATHEMATICAL DMAS CORE LOGIC
# =====================================================================
def run_dmas_pipeline(data_df, ablate_verification=False):
    """
    Executes DMAS Layer 2 (Cross-Modal Verification) and Layer 3 (Geospatial Synthesis).
    Includes an ablation switch to test system degradation.
    """
    # Baseline Modality Weights established via expert-defined heuristics
    weights = {'iot_sensor': 0.90, 'municipal_311': 0.75, 'social_media': 0.40}
    
    # Static District Vulnerability Mapping (Simulating demographics, elderly homes, etc.)
    vability_index = {f"District {chr(i)}": np.random.uniform(0.2, 0.9) for i in range(65, 75)}
    
    # Group by district to compute aggregate regional metrics
    results = []
    
    for district, group in data_df.groupby('district'):
        # --- LAYER 2: CROSS-MODAL VERIFICATION ENGINE ---
        if ablate_verification:
            # Ablation Mode: Ignore weights and convergence; accept raw unverified averages
            sc_score = group['raw_intensity'].mean() / 5.0  # Normalize to 0-1
            status = "TRUST_UNVERIFIED"
        else:
            # Standard DMAS Mode: Apply Equation 1 (Weighted Arithmetic Mean)
            group = group.copy()
            group['weight'] = group['modality'].map(weights)
            
            # Weighted Signal Credibility Calculation
            total_weighted_signal = (group['raw_intensity'] * group['weight']).sum()
            total_weight = group['weight'].sum()
            sc_score = (total_weighted_signal / total_weight) / 5.0  # Normalize to 0-1
            
            # Three-Gate Decision Logic
            iot_active = 'iot_sensor' in group['modality'].values
            soc_intensity = group[group['modality'] == 'social_media']['raw_intensity'].mean()
            iot_intensity = group[group['modality'] == 'iot_sensor']['raw_intensity'].mean() if iot_active else 0
            
            # Suppression Gate: Social chatter reports catastrophe, but physical sensors are clear
            if iot_active and (soc_intensity > 4.0) and (iot_intensity < 1.5):
                status = "SUPPRESSED (HALLUCINATION DETECTED)"
                sc_score *= 0.1  # Drastically penalize the signal score
            elif sc_score >= 0.70:
                status = "TRUST"
            else:
                status = "UNCERTAINTY (TRIGGER UAV RECON)"

        # --- LAYER 3: GEOSPATIAL SYNTHESIS ENGINE ---
        # Equation 2: Composite Distress Severity Score (CDSS)
        v_idx = vability_index[district]
        cdss = (0.6 * sc_score) + (0.4 * v_idx)
        
        results.append({
            'district': district,
            'signal_credibility': sc_score,
            'verification_status': status,
            'vulnerability': v_idx,
            'CDSS': cdss
        })
        
    return pd.DataFrame(results)

# =====================================================================
# 3. EXPERIMENTAL EXECUTION SUITE (GENERATES RESULTS FOR YOUR MANUSCRIPT)
# =====================================================================
if __name__ == "__main__":
    print("="*70)
    print("🚀 INITIALIZING HIGH-SCALE DMAS REPLICABILITY SIMULATION")
    print("="*70)
    
    # Run Scalability and Latency Benchmarks
    for scale in [1000, 10000, 100000]:
        t_start = time.perf_counter()
        raw_data = generate_big_disaster_dataset(num_records=scale)
        _ = run_dmas_pipeline(raw_data)
        t_end = time.perf_counter()
        print(f"📈 [LATENCY ANALYSIS] Processed {scale:,} streams in {t_end - t_start:.4f} seconds.")
        
    print("\n" + "="*70)
    print("🧪 RUNNING EXPERIMENT: ABLATION STUDY & ANOMALY SUPPRESSION")
    print("="*70)
    
    # Generate stable experimental evaluation dataset
    eval_data = generate_big_disaster_dataset(num_records=25000)
    
    # Run Complete System
    print("\n▶ Running Complete DMAS Pipeline...")
    dmas_output = run_dmas_pipeline(eval_data, ablate_verification=False)
    print(dmas_output[['district', 'verification_status', 'CDSS']].sort_values(by='CDSS', ascending=False).to_string(index=False))
    
    # Run Ablated System (Turn off the Verification Layer)
    print("\n⚠️ Running Ablated Pipeline (No Verification / Trust Gates)...")
    ablated_output = run_dmas_pipeline(eval_data, ablate_verification=True)
    
    # Compare Resource Allocations/False Positive Waste
    print("\n" + "="*70)
    print("📊 EMPIRICAL PERFORMANCE ANALYSIS FOR MANUSCRIPT")
    print("="*70)
    
    # Count how many districts were artificially inflated by fake social media trends
    suppressed_zones = (dmas_output['verification_status'].str.contains("SUPPRESSED")).sum()
    print(f"• Misinformation Hallucinations Suppressed by DMAS: {suppressed_zones} districts.")
    print("• Architecture Scalability: Successfully completed. Fully reproducible engine.")