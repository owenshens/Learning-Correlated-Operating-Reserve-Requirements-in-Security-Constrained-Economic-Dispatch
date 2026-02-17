"""
Shared utilities for both decoupled and coupled experiments.

Provides common data loading, splitting, and evaluation functions
used by run_experiment.py and run_coupled_experiment.py.
"""

import os
import json
import numpy as np
import pandas as pd

from sced import build_zone_gen_map

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
UNCERT_DIR = os.path.join(DATA_DIR, "uncertainty")


def load_data():
    """Load all data needed for the experiment.

    Returns:
        dict with keys: U, Xi, L_true_t, A, metadata, split,
                        gen_data, zone_loads, zone_gens
    """
    print("=" * 60)
    print("Loading data...")
    print("=" * 60)

    # Uncertainty vectors (T, 15)
    u_df = pd.read_parquet(os.path.join(UNCERT_DIR, "uncertainty_15d.parquet"))
    U = u_df.values
    print(f"  Uncertainty: {U.shape}")

    # Context features (T, 7)
    ctx_df = pd.read_parquet(os.path.join(UNCERT_DIR, "context_7d.parquet"))
    Xi = ctx_df.values
    print(f"  Context: {Xi.shape}")

    # Ground-truth L (T, 15, 15)
    L_true_t = np.load(os.path.join(UNCERT_DIR, "L_true_t.npy"))
    print(f"  L_true: {L_true_t.shape}")

    # Allocation matrix (10, 15)
    A = np.load(os.path.join(UNCERT_DIR, "allocation_matrix.npy"))
    print(f"  Allocation A: {A.shape}")

    # Metadata (split indices)
    with open(os.path.join(UNCERT_DIR, "metadata.json")) as f:
        metadata = json.load(f)
    split = metadata["split_indices"]
    print(f"  Split: train={split['train']}, tune={split['tune']}, cal={split['calibrate']}")

    # Generator data
    gen_data = pd.read_csv(os.path.join(DATA_DIR, "generator_data.csv"))
    print(f"  Generators: {len(gen_data)}")

    # Zone loads
    zone_df = pd.read_csv(os.path.join(DATA_DIR, "zone_summary.csv"))
    zone_loads = {}
    for _, row in zone_df.iterrows():
        zone_loads[int(row['zone'])] = float(row['load_mw'])
    print(f"  Zone loads: {zone_loads}")

    # Zone-generator mapping
    zone_gens = build_zone_gen_map(gen_data)
    zone_gen_counts = {k: len(v) for k, v in sorted(zone_gens.items())}
    print(f"  Zone-gen map: {zone_gen_counts}")

    return {
        "U": U, "Xi": Xi, "L_true_t": L_true_t, "A": A,
        "metadata": metadata, "split": split,
        "gen_data": gen_data, "zone_loads": zone_loads, "zone_gens": zone_gens,
    }


def split_data(data):
    """Split data into train/tune/calibrate/test sets.

    Args:
        data: dict from load_data()
    Returns:
        dict with keys: u_train, u_tune, u_cal, u_test,
                        xi_train, xi_tune, xi_cal, xi_test,
                        L_true_cal, L_true_test
    """
    split = data["split"]
    t_train = split["train"]
    t_tune = split["tune"]
    t_cal = split["calibrate"]
    t_test = split["test"]

    return {
        "u_train": data["U"][t_train[0]:t_train[1]],
        "u_tune": data["U"][t_tune[0]:t_tune[1]],
        "u_cal": data["U"][t_cal[0]:t_cal[1]],
        "u_test": data["U"][t_test[0]:t_test[1]],
        "xi_train": data["Xi"][t_train[0]:t_train[1]],
        "xi_tune": data["Xi"][t_tune[0]:t_tune[1]],
        "xi_cal": data["Xi"][t_cal[0]:t_cal[1]],
        "xi_test": data["Xi"][t_test[0]:t_test[1]],
        "L_true_cal": data["L_true_t"][t_cal[0]:t_cal[1]],
        "L_true_test": data["L_true_t"][t_test[0]:t_test[1]],
    }


def compute_frob_error(L, L_true_avg):
    """Scale-invariant Frobenius error on normalized correlation matrices.

    Compares correlation structure: normalize both to correlation matrices, then compare.
    ||corr(LL^T) - corr(L_true L_true^T)||_F

    Args:
        L: (d, d) Cholesky factor
        L_true_avg: (d, d) ground-truth Cholesky factor
    Returns:
        scalar Frobenius error
    """
    def to_corr(Sigma):
        d = np.sqrt(np.diag(Sigma))
        d = np.maximum(d, 1e-12)
        return Sigma / np.outer(d, d)

    Sigma = L @ L.T
    Sigma_true = L_true_avg @ L_true_avg.T
    return np.linalg.norm(to_corr(Sigma) - to_corr(Sigma_true), 'fro')
