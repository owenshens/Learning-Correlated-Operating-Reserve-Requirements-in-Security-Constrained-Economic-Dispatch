"""
Coupled experiment: SCED with inter-zone transfer limits.

This script runs the same 4-method comparison as run_experiment.py, but with
a coupled SCED that includes robust inter-zone transfer constraints:

    |Export_z| + ρ ||L^T A[z,:]||₂ ≤ T_z^max

Transfer limits T_z^max are computed from the decoupled baseline (sample cov),
with the 3 highest-shadow-price zones tightened to create binding constraints.

Usage:
    python run_coupled_experiment.py
"""

import sys
import os
import json
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))

from sced import (
    gauge_scores_batch, compute_reserve_requirements, solve_sced,
    conformal_calibrate, smoothed_quantile
)
from sced_coupled import solve_coupled_sced
from methods import (
    box_method, sample_cov_method, ContextNN,
    compute_scores_static, compute_scores_context
)
from methods_coupled import (
    train_static_L_coupled, train_context_nn_coupled,
    evaluate_method_static_coupled, evaluate_method_context_coupled
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


def compute_transfer_limits(gen_data, zone_loads, zone_gens, A, L_cov, rho_cov,
                            rho_train=None,
                            alpha_tight=0.90, alpha_loose=1.5, n_tight=3):
    """Compute inter-zone transfer limits T_z^max from decoupled baseline.

    1. Run decoupled SCED with sample covariance → base dispatch
    2. Compute per-zone: needed_z = |Export_z| + R_z_train
       where R_z_train uses rho_train (tune-set smoothed quantile) to ensure
       training feasibility. rho_train >= rho_cov typically.
    3. Tighten top-n_tight zones by shadow price to alpha_tight * needed_z
    4. Set remaining zones to alpha_loose * needed_z

    Args:
        gen_data, zone_loads, zone_gens: SCED parameters
        A: (n_zones, d) allocation matrix
        L_cov: (d, d) sample covariance Cholesky factor
        rho_cov: calibrated radius for sample covariance (used for base dispatch)
        rho_train: radius used during training (tune-set smoothed quantile).
            If None, defaults to rho_cov. Should be >= rho_cov to ensure
            training feasibility.
        alpha_tight: tightening factor for congested zones (< 1.0)
        alpha_loose: headroom factor for uncongested zones (> 1.0)
        n_tight: number of zones to tighten

    Returns:
        T_z_max: (10,) transfer capacity limits
        tight_zones: list of 0-indexed zone indices that are tightened
        info: dict with per-zone details
    """
    if rho_train is None:
        rho_train = rho_cov

    n_zones = 10
    R_z = compute_reserve_requirements(L_cov, rho_cov, A)
    res = solve_sced(R_z, gen_data, zone_loads, zone_gens)

    if not res['feasible']:
        raise RuntimeError("Decoupled SCED infeasible — cannot compute transfer limits")

    g_base = res['g']
    mu_z = res['mu_z']

    # Compute R_z at training rho (may be larger than R_z at eval rho)
    R_z_train = compute_reserve_requirements(L_cov, rho_train, A)

    # Per-zone exports and needed capacity
    # Use R_z_train to ensure T_z_max is feasible during training
    exports = np.zeros(n_zones)
    needed = np.zeros(n_zones)
    for z_idx in range(n_zones):
        z_id = z_idx + 1
        gen_z = sum(g_base[i] for i in zone_gens[z_id])
        D_z = zone_loads[z_id] if isinstance(zone_loads, dict) else zone_loads[z_idx]
        exports[z_idx] = gen_z - D_z
        needed[z_idx] = abs(exports[z_idx]) + R_z_train[z_idx]

    # Tighten top-n zones by shadow price
    tight_zones = np.argsort(mu_z)[-n_tight:][::-1].tolist()

    T_z_max = np.zeros(n_zones)
    for z_idx in range(n_zones):
        if z_idx in tight_zones:
            T_z_max[z_idx] = alpha_tight * needed[z_idx]
        else:
            T_z_max[z_idx] = alpha_loose * needed[z_idx]

    info = {
        'exports': exports,
        'needed': needed,
        'R_z_baseline': R_z,
        'R_z_train': R_z_train,
        'rho_train': rho_train,
        'mu_z_baseline': mu_z,
        'tight_zones': tight_zones,
    }
    return T_z_max, tight_zones, info


def main():
    # Set seeds for reproducibility
    np.random.seed(42)
    torch.manual_seed(42)

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

    L_true_avg = L_true_cal.mean(axis=0)

    print(f"\n  Train: {u_train.shape[0]} samples")
    print(f"  Tune:  {u_tune.shape[0]} samples")
    print(f"  Cal:   {u_cal.shape[0]} samples")
    print(f"  Test:  {u_test.shape[0]} samples")

    # ==================================================================
    # Compute transfer limits from decoupled baseline
    # ==================================================================
    print("\n" + "=" * 60)
    print("Computing transfer limits from decoupled baseline...")
    print("=" * 60)

    # First get sample cov L and rho (needed for transfer limit computation)
    L_cov = sample_cov_method(u_train)
    scores_cov_cal = compute_scores_static(L_cov, u_cal)
    rho_cov = conformal_calibrate(scores_cov_cal, tau)

    # Compute tune-set smoothed quantile (what training actually sees)
    # T_z_max must be feasible at this rho, not just rho_cov
    scores_cov_tune = gauge_scores_batch(L_cov, u_tune)
    rho_tune = smoothed_quantile(scores_cov_tune, tau, eps=0.5)
    print(f"\n  rho_cov (conformal, cal set):       {rho_cov:.4f}")
    print(f"  rho_tune (smoothed quantile, tune): {rho_tune:.4f}")
    print(f"  Ratio tune/cal:                     {rho_tune/rho_cov:.4f}")

    T_z_max, tight_zones, tlim_info = compute_transfer_limits(
        gen_data, zone_loads, zone_gens, A, L_cov, rho_cov,
        rho_train=rho_tune,
    )

    print(f"\n  Transfer limits T_z^max:")
    for z_idx in range(n_zones):
        tight_str = " *** TIGHT" if z_idx in tight_zones else ""
        print(f"    Zone {z_idx+1}: T_max={T_z_max[z_idx]:.1f} MW, "
              f"needed={tlim_info['needed'][z_idx]:.1f}, "
              f"export={tlim_info['exports'][z_idx]:.1f}, "
              f"mu={tlim_info['mu_z_baseline'][z_idx]:.2f}{tight_str}")

    results = {}

    # ==================================================================
    # Method 1: Box (evaluate with coupled SCED)
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 1: Box (axis-aligned ellipsoid) — coupled evaluation")
    print("=" * 60)

    L_box = box_method(u_train)
    scores_box_cal = compute_scores_static(L_box, u_cal)
    rho_box = conformal_calibrate(scores_box_cal, tau)
    coverage_box = np.mean(scores_box_cal <= rho_box)

    eval_box = evaluate_method_static_coupled(L_box, rho_box, A, T_z_max,
                                               gen_data, zone_loads, zone_gens)
    frob_box = compute_frob_error(L_box, L_true_avg)

    # Test coverage
    scores_box_test = compute_scores_static(L_box, u_test)
    coverage_box_test = np.mean(scores_box_test <= rho_box)
    ci_lo, ci_hi = wilson_ci(coverage_box_test, len(u_test))

    n_binding_box = np.sum(eval_box['lambda_z'] > 1e-6)
    print(f"  ρ = {rho_box:.4f}")
    print(f"  Cal Coverage = {coverage_box:.4f}")
    print(f"  Test Coverage = {coverage_box_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_box['cost']:.2f} (energy: ${eval_box.get('energy_cost', 0):.2f}, reserve: ${eval_box.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_box['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_box['R_z_min'], 1)}")
    print(f"  Binding transfers: {n_binding_box} zones, λ_z = {np.round(eval_box['lambda_z'], 2)}")

    results["Box"] = {
        "cost": eval_box["cost"], "energy_cost": eval_box.get("energy_cost", 0),
        "reserve_cost": eval_box.get("reserve_cost", 0),
        "coverage": coverage_box, "test_coverage": coverage_box_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_box["reserve_total"], "R_z_min": eval_box["R_z_min"],
        "rho": rho_box, "frob_error": frob_box, "feasible": eval_box["feasible"],
        "lambda_z": eval_box["lambda_z"],
    }

    # ==================================================================
    # Method 2: Sample Covariance (evaluate with coupled SCED)
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 2: Sample Covariance — coupled evaluation")
    print("=" * 60)

    coverage_cov = np.mean(scores_cov_cal <= rho_cov)

    eval_cov = evaluate_method_static_coupled(L_cov, rho_cov, A, T_z_max,
                                               gen_data, zone_loads, zone_gens)
    frob_cov = compute_frob_error(L_cov, L_true_avg)

    # Test coverage
    scores_cov_test = compute_scores_static(L_cov, u_test)
    coverage_cov_test = np.mean(scores_cov_test <= rho_cov)
    ci_lo, ci_hi = wilson_ci(coverage_cov_test, len(u_test))

    n_binding_cov = np.sum(eval_cov['lambda_z'] > 1e-6)
    print(f"  ρ = {rho_cov:.4f}")
    print(f"  Cal Coverage = {coverage_cov:.4f}")
    print(f"  Test Coverage = {coverage_cov_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_cov['cost']:.2f} (energy: ${eval_cov.get('energy_cost', 0):.2f}, reserve: ${eval_cov.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_cov['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_cov['R_z_min'], 1)}")
    print(f"  Binding transfers: {n_binding_cov} zones, λ_z = {np.round(eval_cov['lambda_z'], 2)}")

    results["SampleCov"] = {
        "cost": eval_cov["cost"], "energy_cost": eval_cov.get("energy_cost", 0),
        "reserve_cost": eval_cov.get("reserve_cost", 0),
        "coverage": coverage_cov, "test_coverage": coverage_cov_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_cov["reserve_total"], "R_z_min": eval_cov["R_z_min"],
        "rho": rho_cov, "frob_error": frob_cov, "feasible": eval_cov["feasible"],
        "lambda_z": eval_cov["lambda_z"],
    }

    # ==================================================================
    # Method 3: Static L (trained with coupled SCED)
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 3: Static L (profiled gradient, coupled training)")
    print("=" * 60)

    L_static, hist_static = train_static_L_coupled(
        L_init=L_cov.copy(),
        u_tune=u_tune,
        A=A,
        T_z_max=T_z_max,
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

    eval_static = evaluate_method_static_coupled(L_static, rho_static, A, T_z_max,
                                                  gen_data, zone_loads, zone_gens)
    frob_static = compute_frob_error(L_static, L_true_avg)

    # Test coverage
    scores_static_test = compute_scores_static(L_static, u_test)
    coverage_static_test = np.mean(scores_static_test <= rho_static)
    ci_lo, ci_hi = wilson_ci(coverage_static_test, len(u_test))

    n_binding_static = np.sum(eval_static['lambda_z'] > 1e-6)
    print(f"\n  Final ρ = {rho_static:.4f}")
    print(f"  Cal Coverage = {coverage_static:.4f}")
    print(f"  Test Coverage = {coverage_static_test:.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  Cost = ${eval_static['cost']:.2f} (energy: ${eval_static.get('energy_cost', 0):.2f}, reserve: ${eval_static.get('reserve_cost', 0):.2f})")
    print(f"  Total reserve = {eval_static['reserve_total']:.1f} MW")
    print(f"  Per-zone: {np.round(eval_static['R_z_min'], 1)}")
    print(f"  Binding transfers: {n_binding_static} zones, λ_z = {np.round(eval_static['lambda_z'], 2)}")

    results["StaticL"] = {
        "cost": eval_static["cost"], "energy_cost": eval_static.get("energy_cost", 0),
        "reserve_cost": eval_static.get("reserve_cost", 0),
        "coverage": coverage_static, "test_coverage": coverage_static_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_static["reserve_total"], "R_z_min": eval_static["R_z_min"],
        "rho": rho_static, "frob_error": frob_static, "feasible": eval_static["feasible"],
        "lambda_z": eval_static["lambda_z"],
    }

    # Save trained coupled models for reuse
    models_dir = os.path.join(DATA_DIR, "models")
    os.makedirs(models_dir, exist_ok=True)
    np.save(os.path.join(models_dir, "L_static_coupled.npy"), L_static)
    print(f"  Saved L_static_coupled to {models_dir}/L_static_coupled.npy")

    # ==================================================================
    # Method 4: Context-dependent NN (trained with coupled SCED)
    # ==================================================================
    print("\n" + "=" * 60)
    print("Method 4: Context-dependent NN L(ξ) — coupled training")
    print("=" * 60)

    model = ContextNN(d_context=7, d_uncertainty=d, hidden_dims=[128, 64])
    model.initialize_from_L(L_static)

    model, hist_nn = train_context_nn_coupled(
        model=model,
        xi_tune=xi_tune,
        u_tune=u_tune,
        A=A,
        T_z_max=T_z_max,
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

    eval_nn = evaluate_method_context_coupled(model, xi_test, rho_nn, A, T_z_max,
                                               gen_data, zone_loads, zone_gens)

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

    results["NN_L"] = {
        "cost": eval_nn["cost"], "energy_cost": eval_nn.get("energy_cost", 0),
        "reserve_cost": eval_nn.get("reserve_cost", 0),
        "coverage": coverage_nn, "test_coverage": coverage_nn_test,
        "test_ci": [ci_lo, ci_hi],
        "reserve_total": eval_nn["reserve_total"], "R_z_min": eval_nn["R_z_min"],
        "rho": rho_nn, "frob_error": frob_nn, "feasible": eval_nn["feasible"],
        "lambda_z": eval_nn.get("lambda_z", np.zeros(n_zones)),
    }

    # Save trained coupled NN model for reuse
    torch.save(model.state_dict(), os.path.join(models_dir, "nn_model_coupled.pt"))
    print(f"  Saved NN coupled model to {models_dir}/nn_model_coupled.pt")

    # ==================================================================
    # Summary Table
    # ==================================================================
    print("\n" + "=" * 60)
    print("COUPLED EXPERIMENT RESULTS")
    print("=" * 60)

    print(f"\n{'Method':<16} {'Cost ($)':<12} {'Energy ($)':<12} {'Reserve ($)':<12} {'Test Cov':<16} {'Rsv (MW)':<10} {'Bind Xfer':<10}")
    print("-" * 88)
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        lz = r.get("lambda_z", np.zeros(n_zones))
        n_bind = int(np.sum(np.array(lz) > 1e-6)) if lz is not None else 0
        ci = r.get("test_ci", [0, 0])
        tc = r.get("test_coverage", 0)
        print(f"{name:<16} {r['cost']:>10.2f}  {r.get('energy_cost',0):>10.2f}  {r.get('reserve_cost',0):>10.2f}  "
              f"{tc:>.4f} [{ci[0]:.3f},{ci[1]:.3f}]  {r['reserve_total']:>8.1f}  {n_bind:>8d}")

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

    print(f"\nTransfer duals λ_z:")
    print(f"{'Method':<20}", end="")
    for z in range(1, 11):
        print(f"{'Z'+str(z):>8}", end="")
    print()
    print("-" * (20 + 8 * 10))
    for name in ["Box", "SampleCov", "StaticL", "NN_L"]:
        r = results[name]
        lz = r.get("lambda_z", np.zeros(n_zones))
        if lz is None:
            lz = np.zeros(n_zones)
        lz = np.array(lz)
        print(f"{name:<20}", end="")
        for z in range(10):
            print(f"{lz[z]:>8.2f}", end="")
        print()

    print(f"\nTransfer limits T_z^max (MW):")
    for z_idx in range(n_zones):
        tight_str = " *" if z_idx in tight_zones else ""
        print(f"  Zone {z_idx+1}: {T_z_max[z_idx]:.1f}{tight_str}")

    # Save results
    output_path = os.path.join(DATA_DIR, "coupled_experiment_results.json")
    save_results = {
        "T_z_max": T_z_max.tolist(),
        "tight_zones": [int(z) + 1 for z in tight_zones],
    }
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
            "R_z_min": [float(x) for x in r["R_z_min"]],
            "lambda_z": [float(x) for x in (r.get("lambda_z") if r.get("lambda_z") is not None else np.zeros(n_zones))],
        }
    with open(output_path, "w") as f:
        json.dump(save_results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
