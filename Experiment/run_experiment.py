"""
Main experiment script: run all 4 methods and compare results.

Usage:
    python run_experiment.py
"""

import sys
import os
import json
import numpy as np
import torch

# Add Experiment directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from sced import conformal_calibrate
from methods import (
    box_method, sample_cov_method, train_static_L, ContextNN,
    train_context_nn, compute_scores_static, compute_scores_context,
    evaluate_method_static, evaluate_method_context
)
from utils import load_data, split_data, compute_frob_error

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")


def wilson_ci(p_hat, n, z=1.96):
    """Wilson confidence interval for a proportion."""
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) / denom
    return center - margin, center + margin


def main():
    # Set seeds for reproducibility
    np.random.seed(42)
    torch.manual_seed(42)

    # Load and split data
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
    L_true_cal = splits["L_true_cal"]

    tau = 0.95
    d = 15
    n_zones = 10

    # Average ground-truth L for Frobenius comparison
    L_true_avg = L_true_cal.mean(axis=0)

    print(f"\n  Train: {u_train.shape[0]} samples")
    print(f"  Tune:  {u_tune.shape[0]} samples")
    print(f"  Cal:   {u_cal.shape[0]} samples")
    print(f"  Test:  {u_test.shape[0]} samples")

    results = {}

    # ==================================================================
    # Method 1: Box
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 1: Box (axis-aligned ellipsoid)")
    print("=" * 60)

    L_box = box_method(u_train)
    scores_box_cal = compute_scores_static(L_box, u_cal)
    rho_box = conformal_calibrate(scores_box_cal, tau)
    coverage_box = np.mean(scores_box_cal <= rho_box)

    eval_box = evaluate_method_static(L_box, rho_box, A, gen_data, zone_loads, zone_gens)
    frob_box = compute_frob_error(L_box, L_true_avg)

    # Test coverage
    scores_box_test = compute_scores_static(L_box, u_test)
    coverage_box_test = np.mean(scores_box_test <= rho_box)
    ci_lo, ci_hi = wilson_ci(coverage_box_test, len(u_test))

    print(f"  ρ = {rho_box:.4f}")
    print(f"  Cal Coverage = {coverage_box:.4f}")
    print(f"  Test Coverage = {coverage_box_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_box['cost']:.2f} (energy: ${eval_box.get('energy_cost', 0):.2f}, reserve: ${eval_box.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_box['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_box['R_z_min'], 1)}")
    print(f"  Frobenius error = {frob_box:.2f}")

    results["Box"] = {
        "cost": eval_box["cost"],
        "energy_cost": eval_box.get("energy_cost", 0),
        "reserve_cost": eval_box.get("reserve_cost", 0),
        "coverage": coverage_box,
        "test_coverage": coverage_box_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_box["reserve_total"],
        "R_z_min": eval_box["R_z_min"],
        "rho": rho_box,
        "frob_error": frob_box,
        "feasible": eval_box["feasible"],
    }

    # ==================================================================
    # Method 2: Sample Covariance
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 2: Sample Covariance")
    print("=" * 60)

    L_cov = sample_cov_method(u_train)
    scores_cov_cal = compute_scores_static(L_cov, u_cal)
    rho_cov = conformal_calibrate(scores_cov_cal, tau)
    coverage_cov = np.mean(scores_cov_cal <= rho_cov)

    eval_cov = evaluate_method_static(L_cov, rho_cov, A, gen_data, zone_loads, zone_gens)
    frob_cov = compute_frob_error(L_cov, L_true_avg)

    # Test coverage
    scores_cov_test = compute_scores_static(L_cov, u_test)
    coverage_cov_test = np.mean(scores_cov_test <= rho_cov)
    ci_lo, ci_hi = wilson_ci(coverage_cov_test, len(u_test))

    print(f"  ρ = {rho_cov:.4f}")
    print(f"  Cal Coverage = {coverage_cov:.4f}")
    print(f"  Test Coverage = {coverage_cov_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_cov['cost']:.2f} (energy: ${eval_cov.get('energy_cost', 0):.2f}, reserve: ${eval_cov.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_cov['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_cov['R_z_min'], 1)}")
    print(f"  Frobenius error = {frob_cov:.2f}")

    results["SampleCov"] = {
        "cost": eval_cov["cost"],
        "energy_cost": eval_cov.get("energy_cost", 0),
        "reserve_cost": eval_cov.get("reserve_cost", 0),
        "coverage": coverage_cov,
        "test_coverage": coverage_cov_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_cov["reserve_total"],
        "R_z_min": eval_cov["R_z_min"],
        "rho": rho_cov,
        "frob_error": frob_cov,
        "feasible": eval_cov["feasible"],
    }

    # ==================================================================
    # Method 3: Static L (profiled gradient)
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 3: Static L (profiled gradient training)")
    print("=" * 60)

    L_static, hist_static = train_static_L(
        L_init=L_cov.copy(),
        u_tune=u_tune,
        A=A,
        gen_data=gen_data,
        zone_loads=zone_loads,
        zone_gens=zone_gens,
        tau=tau,
        eps=0.5,
        n_iters=200,
        lr=1e-2,
        verbose=True,
    )

    scores_static_cal = compute_scores_static(L_static, u_cal)
    rho_static = conformal_calibrate(scores_static_cal, tau)
    coverage_static = np.mean(scores_static_cal <= rho_static)

    eval_static = evaluate_method_static(L_static, rho_static, A, gen_data, zone_loads, zone_gens)
    frob_static = compute_frob_error(L_static, L_true_avg)

    # Test coverage
    scores_static_test = compute_scores_static(L_static, u_test)
    coverage_static_test = np.mean(scores_static_test <= rho_static)
    ci_lo, ci_hi = wilson_ci(coverage_static_test, len(u_test))

    print(f"\n  Final ρ = {rho_static:.4f}")
    print(f"  Cal Coverage = {coverage_static:.4f}")
    print(f"  Test Coverage = {coverage_static_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_static['cost']:.2f} (energy: ${eval_static.get('energy_cost', 0):.2f}, reserve: ${eval_static.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_static['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_static['R_z_min'], 1)}")
    print(f"  Frobenius error = {frob_static:.2f}")

    results["StaticL"] = {
        "cost": eval_static["cost"],
        "energy_cost": eval_static.get("energy_cost", 0),
        "reserve_cost": eval_static.get("reserve_cost", 0),
        "coverage": coverage_static,
        "test_coverage": coverage_static_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_static["reserve_total"],
        "R_z_min": eval_static["R_z_min"],
        "rho": rho_static,
        "frob_error": frob_static,
        "feasible": eval_static["feasible"],
    }

    # Save trained L_static for reuse by downstream scripts
    models_dir = os.path.join(DATA_DIR, "models")
    os.makedirs(models_dir, exist_ok=True)
    np.save(os.path.join(models_dir, "L_static_decoupled.npy"), L_static)
    print(f"  Saved L_static to {models_dir}/L_static_decoupled.npy")

    # ==================================================================
    # Method 4: Context-dependent NN L(ξ)
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 4: Context-dependent NN L(ξ)")
    print("=" * 60)

    model = ContextNN(d_context=7, d_uncertainty=d, hidden_dims=[128, 64])
    model.initialize_from_L(L_static)  # Initialize from task-optimized StaticL, not L_cov

    model, hist_nn = train_context_nn(
        model=model,
        xi_tune=xi_tune,
        u_tune=u_tune,
        A=A,
        gen_data=gen_data,
        zone_loads=zone_loads,
        zone_gens=zone_gens,
        tau=tau,
        eps=0.5,
        n_iters=1500,
        lr=3e-4,
        batch_size=8,
        verbose=True,
    )

    scores_nn_cal = compute_scores_context(model, xi_cal, u_cal)
    rho_nn = conformal_calibrate(scores_nn_cal, tau)
    coverage_nn = np.mean(scores_nn_cal <= rho_nn)

    eval_nn = evaluate_method_context(model, xi_test, rho_nn, A, gen_data, zone_loads, zone_gens)

    # Frobenius error: average over calibration set
    model.eval()
    xi_cal_t = torch.tensor(xi_cal, dtype=torch.float32)
    with torch.no_grad():
        L_nn_all = model(xi_cal_t).numpy()
    frob_nn = 0.0
    for i in range(len(u_cal)):
        frob_nn += compute_frob_error(L_nn_all[i], L_true_cal[i])
    frob_nn /= len(u_cal)

    # Test coverage
    scores_nn_test = compute_scores_context(model, xi_test, u_test)
    coverage_nn_test = np.mean(scores_nn_test <= rho_nn)
    ci_lo, ci_hi = wilson_ci(coverage_nn_test, len(u_test))

    print(f"\n  Final ρ = {rho_nn:.4f}")
    print(f"  Cal Coverage = {coverage_nn:.4f}")
    print(f"  Test Coverage = {coverage_nn_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_nn['cost']:.2f} (energy: ${eval_nn.get('energy_cost', 0):.2f}, reserve: ${eval_nn.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_nn['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_nn['R_z_min'], 1)}")
    print(f"  Avg Frobenius error = {frob_nn:.2f}")

    results["NN_L"] = {
        "cost": eval_nn["cost"],
        "energy_cost": eval_nn.get("energy_cost", 0),
        "reserve_cost": eval_nn.get("reserve_cost", 0),
        "coverage": coverage_nn,
        "test_coverage": coverage_nn_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_nn["reserve_total"],
        "R_z_min": eval_nn["R_z_min"],
        "rho": rho_nn,
        "frob_error": frob_nn,
        "feasible": eval_nn["feasible"],
    }

    # Save trained NN model for reuse by downstream scripts
    torch.save(model.state_dict(), os.path.join(models_dir, "nn_model_decoupled.pt"))
    print(f"  Saved NN model to {models_dir}/nn_model_decoupled.pt")

    # ==================================================================
    # Summary Table
    # ==================================================================
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    print(f"\n{'Method':<16} {'Cost ($)':<12} {'Energy ($)':<12} {'Reserve ($)':<12} {'Test Cov':<16} {'Rsv (MW)':<10} {'ρ':<8} {'||Σ-Σ*||_F':<10}")
    print("-" * 96)
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        feas = "✓" if r["feasible"] else "✗"
        ci = r.get("test_ci", [0, 0])
        tc = r.get("test_coverage", 0)
        print(f"{name:<16} {r['cost']:>10.2f}  {r.get('energy_cost',0):>10.2f}  {r.get('reserve_cost',0):>10.2f}  "
              f"{tc:>.4f} [{ci[0]:.3f},{ci[1]:.3f}]  {r['reserve_total']:>8.1f}  {r['rho']:>6.4f}  {r['frob_error']:>8.2f}  {feas}")

    print(f"\nPer-zone reserves (MW):")
    print(f"{'Method':<20}", end="")
    for z in range(1, 11):
        print(f"{'Z'+str(z):>8}", end="")
    print()
    print("-" * (20 + 8 * 10))
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        print(f"{name:<20}", end="")
        for z in range(10):
            print(f"{r['R_z_min'][z]:>8.1f}", end="")
        print()

    # Save results
    output_path = os.path.join(DATA_DIR, "experiment_results.json")
    save_results = {}
    for name, r in results.items():
        save_results[name] = {
            "cost": float(r["cost"]),
            "energy_cost": float(r.get("energy_cost", 0)),
            "reserve_cost": float(r.get("reserve_cost", 0)),
            "coverage": float(r["coverage"]),
            "test_coverage": float(r.get("test_coverage", 0)),
            "test_ci": [float(x) for x in r.get("test_ci", [0, 0])],
            "reserve_total": float(r["reserve_total"]),
            "rho": float(r["rho"]),
            "frob_error": float(r["frob_error"]),
            "feasible": bool(r["feasible"]),
            "R_z_min": r["R_z_min"].tolist(),
        }
    with open(output_path, "w") as f:
        json.dump(save_results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
