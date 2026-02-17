"""
Phase 2: Extended training for top NN configurations from Phase 1.
Also tests alternative batch sizes (smaller = per-sample SCED for better gradients).

Usage:
    python tune_nn_phase2.py
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

    # Phase 2 configs: top architectures with extended training + batch size variants
    configs = []

    # A) Extended training for top 3 architectures with lr=3e-4
    for hidden_dims in [[128, 64], [64, 64], [64]]:
        for lr_schedule in ["none", "cosine"]:
            configs.append({
                "label": f"extended_{hidden_dims}_lr3e-4_{lr_schedule}",
                "lr": 3e-4,
                "hidden_dims": hidden_dims,
                "lr_schedule": lr_schedule,
                "batch_size": 512,
                "weight_decay": 0.0,
                "n_iters": 800,
                "patience": 250,
                "eps": 0.5,
                "grad_clip_nn": 1.0,
                "grad_clip_sample": 100.0,
            })

    # B) Smaller batch sizes (per-sample SCED → context-specific μ_z)
    for batch_size in [8, 32, 128]:
        for hidden_dims in [[128, 64], [64, 64]]:
            configs.append({
                "label": f"smallbatch_{batch_size}_{hidden_dims}",
                "lr": 3e-4,
                "hidden_dims": hidden_dims,
                "lr_schedule": "none",
                "batch_size": batch_size,
                "weight_decay": 0.0,
                "n_iters": 800,
                "patience": 250,
                "eps": 0.5,
                "grad_clip_nn": 1.0,
                "grad_clip_sample": 100.0,
            })

    # C) lr=1e-3 with extended training (was competitive in phase 1)
    for hidden_dims in [[64, 64], [128, 64]]:
        configs.append({
            "label": f"extended_{hidden_dims}_lr1e-3",
            "lr": 1e-3,
            "hidden_dims": hidden_dims,
            "lr_schedule": "cosine",
            "batch_size": 512,
            "weight_decay": 0.0,
            "n_iters": 800,
            "patience": 250,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # D) Try even lower lr with many iterations
    for hidden_dims in [[128, 64], [64, 64]]:
        configs.append({
            "label": f"verylow_lr_{hidden_dims}",
            "lr": 1e-4,
            "hidden_dims": hidden_dims,
            "lr_schedule": "none",
            "batch_size": 512,
            "weight_decay": 0.0,
            "n_iters": 800,
            "patience": 300,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # E) Higher NN grad clip with low lr (allow larger NN updates)
    for grad_clip_nn in [3.0, 10.0]:
        configs.append({
            "label": f"highclip_{grad_clip_nn}_[128,64]",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 512,
            "weight_decay": 0.0,
            "n_iters": 800,
            "patience": 250,
            "eps": 0.5,
            "grad_clip_nn": grad_clip_nn,
            "grad_clip_sample": 100.0,
        })

    # F) Different smoothing bandwidths
    for eps in [0.2, 1.0]:
        configs.append({
            "label": f"eps_{eps}_[128,64]",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 512,
            "weight_decay": 0.0,
            "n_iters": 800,
            "patience": 250,
            "eps": eps,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    n_configs = len(configs)
    print(f"\n{'='*70}")
    print(f"PHASE 2 TUNING: {n_configs} configurations")
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
        }
        results.append(result)

        print(f"  → cost=${eval_result['cost']:.2f}, reserve={eval_result['reserve_total']:.1f} MW, "
              f"ρ={rho:.2f}, iters={iters_done}, time={elapsed:.1f}s")

    # Summary
    print(f"\n{'='*70}")
    print("PHASE 2 RESULTS (sorted by eval cost)")
    print(f"{'='*70}")

    results.sort(key=lambda r: r["eval_cost"] if r["feasible"] else 1e9)

    print(f"\n{'Rank':<5} {'Cost ($)':<12} {'Reserve':<10} {'ρ':<10} {'Iters':<7} {'Label':<45} {'Time':<8}")
    print("-" * 100)

    for rank, r in enumerate(results):
        print(f"{rank+1:<5} {r['eval_cost']:>10.2f}  {r['reserve_total']:>8.1f}  "
              f"{r['rho']:>8.2f}  {r['iters_done']:>5}  {r['label']:<45} {r['elapsed_s']:>6.1f}s")

    # Save
    output_path = os.path.join(DATA_DIR, "nn_tuning_phase2_results.json")
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
    print(f"  Iterations: {best['iters_done']}")
    print(f"\n  Phase 1 best: $96,627")
    print(f"  StaticL:      $95,071")
    print(f"  Improvement over Phase 1: ${96627 - best['eval_cost']:.2f}")
    print(f"  Gap to StaticL: ${best['eval_cost'] - 95071:.2f}")


if __name__ == "__main__":
    main()
