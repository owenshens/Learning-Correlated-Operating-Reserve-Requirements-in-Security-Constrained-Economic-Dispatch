"""
Cost-coverage tradeoff experiment: sweep τ ∈ {0.90, 0.92, 0.95, 0.97, 0.99}.

For each method, the shape L is fixed (trained once at τ=0.95). Only the
conformal radius ρ changes with τ. This isolates the effect of the coverage
target on cost, holding the learned shape constant.

Usage:
    python run_tau_sweep.py
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
    compute_scores_static, compute_scores_context,
    evaluate_method_static, evaluate_method_context
)
from utils import load_data, split_data

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")

TAU_VALUES = [0.90, 0.92, 0.95, 0.97, 0.99]


def main():
    print("=" * 60)
    print("Cost-Coverage Tradeoff (τ sweep)")
    print("=" * 60)

    data = load_data()
    splits = split_data(data)
    A = data["A"]
    gen_data = data["gen_data"]
    zone_loads = data["zone_loads"]
    zone_gens = data["zone_gens"]

    u_train = splits["u_train"]
    u_tune = splits["u_tune"]
    u_cal = splits["u_cal"]
    u_test = splits["u_test"]
    xi_tune = splits["xi_tune"]
    xi_cal = splits["xi_cal"]
    xi_test = splits["xi_test"]

    d = 15
    tau_train = 0.95  # shape trained at this τ

    # ================================================================
    # Compute/train the 4 L matrices (once, at τ=0.95)
    # ================================================================

    # Method 1: Box
    print("\nComputing Box L...")
    L_box = box_method(u_train)
    scores_box_cal = compute_scores_static(L_box, u_cal)
    scores_box_test = compute_scores_static(L_box, u_test)

    # Method 2: Sample Covariance
    print("Computing Sample Covariance L...")
    L_cov = sample_cov_method(u_train)
    scores_cov_cal = compute_scores_static(L_cov, u_cal)
    scores_cov_test = compute_scores_static(L_cov, u_test)

    # Method 3: Static L (load saved model from run_experiment.py)
    models_dir = os.path.join(DATA_DIR, "models")
    L_static_path = os.path.join(models_dir, "L_static_decoupled.npy")
    print(f"Loading Static L from {L_static_path}...")
    L_static = np.load(L_static_path)
    scores_static_cal = compute_scores_static(L_static, u_cal)
    scores_static_test = compute_scores_static(L_static, u_test)

    # Method 4: NN (load saved model from run_experiment.py)
    nn_model_path = os.path.join(models_dir, "nn_model_decoupled.pt")
    print(f"Loading NN model from {nn_model_path}...")
    model = ContextNN(d_context=7, d_uncertainty=d, hidden_dims=[128, 64])
    model.load_state_dict(torch.load(nn_model_path, weights_only=True))
    model.eval()
    scores_nn_cal = compute_scores_context(model, xi_cal, u_cal)
    scores_nn_test = compute_scores_context(model, xi_test, u_test)

    # ================================================================
    # Sweep τ values
    # ================================================================
    methods = {
        "Box": {
            "L": L_box, "scores_cal": scores_box_cal,
            "scores_test": scores_box_test, "static": True,
        },
        "SampleCov": {
            "L": L_cov, "scores_cal": scores_cov_cal,
            "scores_test": scores_cov_test, "static": True,
        },
        "StaticL": {
            "L": L_static, "scores_cal": scores_static_cal,
            "scores_test": scores_static_test, "static": True,
        },
        "NN_L": {
            "model": model, "scores_cal": scores_nn_cal,
            "scores_test": scores_nn_test, "static": False,
        },
    }

    results = {"tau_values": TAU_VALUES}

    for name, m in methods.items():
        print(f"\n--- {name} ---")
        costs = []
        test_coverages = []
        reserves = []
        rhos = []

        for tau in TAU_VALUES:
            # Conformal calibrate at this τ
            rho = conformal_calibrate(m["scores_cal"], tau)

            # Test coverage
            test_cov = float(np.mean(m["scores_test"] <= rho))

            # Evaluate cost
            if m["static"]:
                ev = evaluate_method_static(m["L"], rho, A, gen_data,
                                            zone_loads, zone_gens)
            else:
                ev = evaluate_method_context(m["model"], xi_test, rho, A,
                                             gen_data, zone_loads, zone_gens)

            cost = ev["cost"] if ev["feasible"] else float("inf")
            rsv = ev["reserve_total"] if ev["feasible"] else float("inf")

            costs.append(float(cost))
            test_coverages.append(test_cov)
            reserves.append(float(rsv))
            rhos.append(float(rho))

            print(f"  τ={tau:.2f}: ρ={rho:.4f}, cost=${cost:,.0f}, "
                  f"rsv={rsv:.0f} MW, test_cov={test_cov:.4f}")

        results[name] = {
            "costs": costs,
            "test_coverages": test_coverages,
            "reserves": reserves,
            "rhos": rhos,
        }

    # ================================================================
    # Summary table
    # ================================================================
    print("\n" + "=" * 60)
    print("COST-COVERAGE TRADEOFF SUMMARY")
    print("=" * 60)

    # Cost table
    print(f"\n{'Method':<16}", end="")
    for tau in TAU_VALUES:
        print(f"  τ={tau:.2f}", end="")
    print()
    print("-" * (16 + 10 * len(TAU_VALUES)))
    print("Cost ($/hr):")
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        print(f"  {name:<14}", end="")
        for c in r["costs"]:
            print(f"  {c:>8,.0f}", end="")
        print()

    print("\nTest Coverage:")
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        print(f"  {name:<14}", end="")
        for tc in r["test_coverages"]:
            print(f"  {tc:>8.4f}", end="")
        print()

    print("\nReserve (MW):")
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        print(f"  {name:<14}", end="")
        for rv in r["reserves"]:
            print(f"  {rv:>8.0f}", end="")
        print()

    # Save
    output_path = os.path.join(DATA_DIR, "tau_sweep_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
