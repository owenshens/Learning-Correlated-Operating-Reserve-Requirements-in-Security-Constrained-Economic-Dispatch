"""
Block bootstrap confidence intervals for test coverage (decoupled experiment).

Loads saved models from run_experiment.py to ensure consistency.
Also runs sensitivity analysis at block lengths 48h and 168h.

Usage:
    python run_block_bootstrap.py
"""

import sys
import os
import json
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))

from sced import conformal_calibrate
from methods import (
    box_method, sample_cov_method, ContextNN,
    compute_scores_static, compute_scores_context
)
from utils import load_data, split_data

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")


def wilson_ci(p_hat, n, z=1.96):
    """Wilson confidence interval for a proportion (i.i.d. assumption)."""
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) / denom
    return center - margin, center + margin


def block_bootstrap_ci(indicators, block_length=24, n_bootstrap=10000, alpha=0.05,
                       seed=42):
    """Block bootstrap CI for the mean of a binary time series."""
    n = len(indicators)
    rng = np.random.default_rng(seed)

    n_blocks = int(np.ceil(n / block_length))
    max_start = n - block_length

    if max_start < 0:
        return wilson_ci(indicators.mean(), n)

    boot_means = np.zeros(n_bootstrap)
    for b in range(n_bootstrap):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        resampled = np.concatenate([indicators[s:s + block_length] for s in starts])[:n]
        boot_means[b] = resampled.mean()

    ci_lo = np.percentile(boot_means, 100 * alpha / 2)
    ci_hi = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return ci_lo, ci_hi


def main():
    print("=" * 60)
    print("Block Bootstrap CIs for Test Coverage (Decoupled)")
    print("=" * 60)

    data = load_data()
    splits = split_data(data)
    A = data["A"]

    u_train = splits["u_train"]
    u_cal = splits["u_cal"]
    u_test = splits["u_test"]
    xi_cal = splits["xi_cal"]
    xi_test = splits["xi_test"]

    tau = 0.95
    d = 15
    block_lengths = [24, 48, 168]
    n_bootstrap = 10000
    models_dir = os.path.join(DATA_DIR, "models")

    # --- Build coverage indicators for each method ---
    methods_info = {}

    # Method 1: Box
    print("\nBox method...")
    L_box = box_method(u_train)
    scores_box_cal = compute_scores_static(L_box, u_cal)
    rho_box = conformal_calibrate(scores_box_cal, tau)
    scores_box_test = compute_scores_static(L_box, u_test)
    indicators_box = (scores_box_test <= rho_box).astype(int)
    methods_info["Box"] = {"indicators": indicators_box, "coverage": float(indicators_box.mean())}

    # Method 2: Sample Covariance
    print("Sample Covariance method...")
    L_cov = sample_cov_method(u_train)
    scores_cov_cal = compute_scores_static(L_cov, u_cal)
    rho_cov = conformal_calibrate(scores_cov_cal, tau)
    scores_cov_test = compute_scores_static(L_cov, u_test)
    indicators_cov = (scores_cov_test <= rho_cov).astype(int)
    methods_info["SampleCov"] = {"indicators": indicators_cov, "coverage": float(indicators_cov.mean())}

    # Method 3: Static L (load saved model)
    print("Static L method (loading saved model)...")
    L_static = np.load(os.path.join(models_dir, "L_static_decoupled.npy"))
    scores_static_cal = compute_scores_static(L_static, u_cal)
    rho_static = conformal_calibrate(scores_static_cal, tau)
    scores_static_test = compute_scores_static(L_static, u_test)
    indicators_static = (scores_static_test <= rho_static).astype(int)
    methods_info["StaticL"] = {"indicators": indicators_static, "coverage": float(indicators_static.mean())}

    # Method 4: NN (load saved model)
    print("NN method (loading saved model)...")
    model = ContextNN(d_context=7, d_uncertainty=d, hidden_dims=[128, 64])
    model.load_state_dict(torch.load(os.path.join(models_dir, "nn_model_decoupled.pt"), weights_only=True))
    model.eval()
    scores_nn_cal = compute_scores_context(model, xi_cal, u_cal)
    rho_nn = conformal_calibrate(scores_nn_cal, tau)
    scores_nn_test = compute_scores_context(model, xi_test, u_test)
    indicators_nn = (scores_nn_test <= rho_nn).astype(int)
    methods_info["NN_L"] = {"indicators": indicators_nn, "coverage": float(indicators_nn.mean())}

    # --- Compute CIs at each block length ---
    results = {"n_bootstrap": n_bootstrap, "block_lengths": block_lengths}

    for name, info in methods_info.items():
        indicators = info["indicators"]
        cov = info["coverage"]
        wilson_lo, wilson_hi = wilson_ci(cov, len(u_test))

        method_result = {
            "test_coverage": cov,
            "wilson_ci": [float(wilson_lo), float(wilson_hi)],
        }

        for bl in block_lengths:
            block_lo, block_hi = block_bootstrap_ci(indicators, bl, n_bootstrap)
            method_result[f"block_ci_{bl}h"] = [float(block_lo), float(block_hi)]

        results[name] = method_result

    # --- Print summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nBootstrap replicates: {n_bootstrap}")

    for bl in block_lengths:
        print(f"\n--- Block length: {bl}h ---")
        print(f"{'Method':<16} {'Coverage':<10} {'Wilson CI':<24} {'Block CI':<24}")
        print("-" * 74)
        for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
            r = results[name]
            w = r["wilson_ci"]
            b = r[f"block_ci_{bl}h"]
            print(f"{name:<16} {r['test_coverage']:.4f}    "
                  f"[{w[0]:.4f}, {w[1]:.4f}]    [{b[0]:.4f}, {b[1]:.4f}]")

    # Save
    output_path = os.path.join(DATA_DIR, "block_bootstrap_ci.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
