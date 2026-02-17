"""
Phase 3: Deep optimization around best settings from Phase 2.
Focus: batch_size in {1, 4, 8, 16}, longer training, combined with best hyperparams.

Usage:
    python tune_nn_phase3.py
"""

import sys
import os
import json
import time
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sced import (
    gauge_scores_batch, compute_reserve_requirements, solve_sced,
    smoothed_quantile, gauge_gradient, conformal_calibrate, build_zone_gen_map
)
from methods import sample_cov_method
from tune_nn import (
    FlexContextNN, train_nn_config, load_data, compute_scores_flex, evaluate_flex
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def main():
    data = load_data()
    A = data["A"]
    gen_data = data["gen_data"]
    zone_loads = data["zone_loads"]
    zone_gens = data["zone_gens"]
    u_tune = data["u_tune"]
    xi_tune = data["xi_tune"]
    u_cal = data["u_cal"]
    xi_cal = data["xi_cal"]
    u_train = data["u_train"]

    tau = 0.95
    d = 15
    L_cov = sample_cov_method(u_train)

    configs = []

    # A) Batch size sweep with [128, 64], lr=3e-4, 1500 iters
    for batch_size in [1, 2, 4, 8, 16]:
        configs.append({
            "label": f"bs{batch_size}_[128,64]_lr3e-4",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": batch_size,
            "weight_decay": 0.0,
            "n_iters": 1500,
            "patience": 400,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # B) Same with [64, 64]
    for batch_size in [1, 4, 8]:
        configs.append({
            "label": f"bs{batch_size}_[64,64]_lr3e-4",
            "lr": 3e-4,
            "hidden_dims": [64, 64],
            "lr_schedule": "none",
            "batch_size": batch_size,
            "weight_decay": 0.0,
            "n_iters": 1500,
            "patience": 400,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # C) Batch_size=8 with higher grad clip (phase 2 showed clip=3.0 helps for bs=512)
    for grad_clip_nn in [3.0, 5.0]:
        configs.append({
            "label": f"bs8_[128,64]_clip{grad_clip_nn}",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 8,
            "weight_decay": 0.0,
            "n_iters": 1500,
            "patience": 400,
            "eps": 0.5,
            "grad_clip_nn": grad_clip_nn,
            "grad_clip_sample": 100.0,
        })

    # D) Batch_size=8 with cosine schedule
    configs.append({
        "label": "bs8_[128,64]_cosine",
        "lr": 3e-4,
        "hidden_dims": [128, 64],
        "lr_schedule": "cosine",
        "batch_size": 8,
        "weight_decay": 0.0,
        "n_iters": 1500,
        "patience": 400,
        "eps": 0.5,
        "grad_clip_nn": 1.0,
        "grad_clip_sample": 100.0,
    })

    # E) Slightly higher lr with small batch
    for lr in [5e-4, 1e-3]:
        configs.append({
            "label": f"bs8_[128,64]_lr{lr}",
            "lr": lr,
            "hidden_dims": [128, 64],
            "lr_schedule": "cosine",
            "batch_size": 8,
            "weight_decay": 0.0,
            "n_iters": 1500,
            "patience": 400,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    n_configs = len(configs)
    print(f"\n{'='*70}")
    print(f"PHASE 3 TUNING: {n_configs} configurations")
    print(f"{'='*70}")

    results = []

    for idx, cfg in enumerate(configs):
        t0 = time.time()
        label = cfg.pop("label")
        print(f"\n[{idx+1}/{n_configs}] {label}")

        model = FlexContextNN(d_context=7, d_uncertainty=d, hidden_dims=cfg["hidden_dims"])
        model.initialize_from_L(L_cov)

        model, hist, best_train_cost = train_nn_config(
            model=model,
            xi_tune=xi_tune,
            u_tune=u_tune,
            A=A,
            gen_data=gen_data,
            zone_loads=zone_loads,
            zone_gens=zone_gens,
            tau=tau,
            verbose=False,
            **{k: v for k, v in cfg.items() if k != "hidden_dims"},
        )

        scores_cal = compute_scores_flex(model, xi_cal, u_cal)
        rho = conformal_calibrate(scores_cal, tau)
        coverage = np.mean(scores_cal <= rho)
        eval_result = evaluate_flex(model, xi_cal, u_cal, rho, A, gen_data, zone_loads, zone_gens)

        elapsed = time.time() - t0
        iters_done = len(hist)

        # Also track training cost history for analysis
        costs_hist = [h['cost'] for h in hist[-20:]] if hist else []

        result = {
            "label": label,
            **cfg,
            "eval_cost": eval_result["cost"],
            "coverage": coverage,
            "reserve_total": eval_result["reserve_total"],
            "rho": rho,
            "feasible": eval_result["feasible"],
            "best_train_cost": best_train_cost,
            "iters_done": iters_done,
            "elapsed_s": elapsed,
            "final_costs": costs_hist,
        }
        results.append(result)

        print(f"  → cost=${eval_result['cost']:.2f}, reserve={eval_result['reserve_total']:.1f} MW, "
              f"ρ={rho:.2f}, iters={iters_done}, best_train=${best_train_cost:.2f}, time={elapsed:.1f}s")

    # Summary
    print(f"\n{'='*70}")
    print("PHASE 3 RESULTS (sorted by eval cost)")
    print(f"{'='*70}")

    results.sort(key=lambda r: r["eval_cost"] if r["feasible"] else 1e9)

    print(f"\n{'Rank':<5} {'Cost ($)':<12} {'Reserve':<10} {'ρ':<10} {'Iters':<7} "
          f"{'BestTrain':<12} {'Label':<40} {'Time':<8}")
    print("-" * 110)

    for rank, r in enumerate(results):
        print(f"{rank+1:<5} {r['eval_cost']:>10.2f}  {r['reserve_total']:>8.1f}  "
              f"{r['rho']:>8.2f}  {r['iters_done']:>5}  "
              f"{r['best_train_cost']:>10.2f}  {r['label']:<40} {r['elapsed_s']:>6.1f}s")

    # Save
    output_path = os.path.join(DATA_DIR, "nn_tuning_phase3_results.json")
    for r in results:
        if "hidden_dims" in r:
            r["hidden_dims"] = list(r["hidden_dims"])
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    best = results[0]
    print(f"\n{'='*70}")
    print(f"BEST CONFIGURATION:")
    print(f"{'='*70}")
    print(f"  Cost: ${best['eval_cost']:.2f}")
    print(f"  Label: {best['label']}")
    print(f"  Reserve: {best['reserve_total']:.1f} MW")
    print(f"  ρ: {best['rho']:.4f}")
    print(f"  LR: {best.get('lr', 'N/A')}")
    print(f"  Hidden dims: {best.get('hidden_dims', 'N/A')}")
    print(f"  Batch size: {best.get('batch_size', 'N/A')}")
    print(f"  Grad clip NN: {best.get('grad_clip_nn', 'N/A')}")
    print(f"  Iterations used: {best['iters_done']} / {best.get('n_iters', 'N/A')}")
    print(f"  Best train cost: ${best['best_train_cost']:.2f}")
    print(f"\n  Phase 2 best:  $96,272")
    print(f"  StaticL:       $95,071")
    print(f"  Improvement over Phase 2: ${96272 - best['eval_cost']:.2f}")
    print(f"  Gap to StaticL: ${best['eval_cost'] - 95071:.2f}")


if __name__ == "__main__":
    main()
