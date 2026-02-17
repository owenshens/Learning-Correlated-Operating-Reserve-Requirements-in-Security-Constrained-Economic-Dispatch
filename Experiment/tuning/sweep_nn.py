"""
Comprehensive NN hyperparameter sweep on the strengthened DGP data.

Axes:
  - batch_size: {1, 4, 8, 16, 32}
  - lr: {1e-4, 3e-4, 1e-3, 3e-3}
  - architecture: {[64], [128, 64], [256, 128]}
  - eps (smoothing): {0.3, 0.5, 1.0}
  - lr_schedule: {none, cosine}
  - grad_clip_nn: {1.0, 3.0}

Strategy: Latin-hypercube-style targeted sweep (~40 configs) rather than full grid.

Usage:
    python sweep_nn.py
"""

import sys
import os
import json
import time
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sced import conformal_calibrate, build_zone_gen_map
from methods import sample_cov_method, train_static_L
from tune_nn import (
    FlexContextNN, train_nn_config, load_data, compute_scores_flex, evaluate_flex
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def run_one(cfg, L_init, data, tau=0.95):
    """Train and evaluate one configuration. Returns result dict."""
    d = 15
    model = FlexContextNN(
        d_context=7, d_uncertainty=d,
        hidden_dims=cfg["hidden_dims"],
        dropout=cfg.get("dropout", 0.0),
    )
    model.initialize_from_L(L_init)

    model, hist, best_train_cost = train_nn_config(
        model=model,
        xi_tune=data["xi_tune"],
        u_tune=data["u_tune"],
        A=data["A"],
        gen_data=data["gen_data"],
        zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        tau=tau,
        verbose=False,
        **{k: v for k, v in cfg.items() if k not in ("hidden_dims", "label", "dropout")},
    )

    scores_cal = compute_scores_flex(model, data["xi_cal"], data["u_cal"])
    rho = conformal_calibrate(scores_cal, tau)
    coverage = np.mean(scores_cal <= rho)
    eval_result = evaluate_flex(
        model, data["xi_cal"], data["u_cal"], rho,
        data["A"], data["gen_data"], data["zone_loads"], data["zone_gens"],
    )

    return {
        "eval_cost": eval_result["cost"],
        "coverage": coverage,
        "reserve_total": eval_result["reserve_total"],
        "rho": rho,
        "feasible": eval_result["feasible"],
        "best_train_cost": best_train_cost,
        "iters_done": len(hist),
    }


def main():
    data = load_data()
    L_cov = sample_cov_method(data["u_train"])
    tau = 0.95

    # Train StaticL first, then use it as NN initialization (task-aware warm start)
    print("Training StaticL for NN initialization...")
    L_static, _ = train_static_L(
        L_init=L_cov.copy(),
        u_tune=data["u_tune"], A=data["A"],
        gen_data=data["gen_data"], zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        tau=tau, eps=0.5, n_iters=200, lr=1e-2, verbose=False,
    )
    L_init = L_static  # Use task-optimized L as starting point

    configs = []

    # ── Group A: batch_size × lr sweep (fixed arch=[128,64], eps=0.5, no schedule) ──
    for bs in [1, 4, 8, 16, 32]:
        for lr in [1e-4, 3e-4, 1e-3, 3e-3]:
            configs.append({
                "label": f"A_bs{bs}_lr{lr:.0e}",
                "lr": lr,
                "hidden_dims": [128, 64],
                "lr_schedule": "none",
                "batch_size": bs,
                "weight_decay": 0.0,
                "n_iters": 2000,
                "patience": 500,
                "eps": 0.5,
                "grad_clip_nn": 1.0,
                "grad_clip_sample": 100.0,
            })

    # ── Group B: architecture sweep (fix bs=8, lr=3e-4) ──
    for arch in [[64], [128], [256], [64, 64], [256, 128], [128, 128]]:
        configs.append({
            "label": f"B_{arch}",
            "lr": 3e-4,
            "hidden_dims": arch,
            "lr_schedule": "none",
            "batch_size": 8,
            "weight_decay": 0.0,
            "n_iters": 2000,
            "patience": 500,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # ── Group C: eps sweep (fix bs=8, lr=3e-4, arch=[128,64]) ──
    for eps in [0.1, 0.3, 1.0, 2.0]:
        configs.append({
            "label": f"C_eps{eps}",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 8,
            "weight_decay": 0.0,
            "n_iters": 2000,
            "patience": 500,
            "eps": eps,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # ── Group D: cosine schedule combos ──
    for bs in [4, 8, 16]:
        for lr in [3e-4, 1e-3]:
            configs.append({
                "label": f"D_cos_bs{bs}_lr{lr:.0e}",
                "lr": lr,
                "hidden_dims": [128, 64],
                "lr_schedule": "cosine",
                "batch_size": bs,
                "weight_decay": 0.0,
                "n_iters": 2000,
                "patience": 500,
                "eps": 0.5,
                "grad_clip_nn": 1.0,
                "grad_clip_sample": 100.0,
            })

    # ── Group E: higher grad clip ──
    for clip_nn in [3.0, 5.0]:
        configs.append({
            "label": f"E_clip{clip_nn}",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 8,
            "weight_decay": 0.0,
            "n_iters": 2000,
            "patience": 500,
            "eps": 0.5,
            "grad_clip_nn": clip_nn,
            "grad_clip_sample": 100.0,
        })

    # ── Group F: weight decay ──
    for wd in [1e-4, 1e-3]:
        configs.append({
            "label": f"F_wd{wd:.0e}",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 8,
            "weight_decay": wd,
            "n_iters": 2000,
            "patience": 500,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": 100.0,
        })

    # ── Group G: lower sample grad clip (tighter control) ──
    for clip_s in [10.0, 50.0]:
        configs.append({
            "label": f"G_sclip{clip_s:.0f}",
            "lr": 3e-4,
            "hidden_dims": [128, 64],
            "lr_schedule": "none",
            "batch_size": 8,
            "weight_decay": 0.0,
            "n_iters": 2000,
            "patience": 500,
            "eps": 0.5,
            "grad_clip_nn": 1.0,
            "grad_clip_sample": clip_s,
        })

    n_configs = len(configs)
    print(f"\n{'='*70}")
    print(f"NN SWEEP: {n_configs} configurations (new DGP data)")
    print(f"{'='*70}")

    results = []

    for idx, cfg in enumerate(configs):
        t0 = time.time()
        label = cfg["label"]
        print(f"\n[{idx+1}/{n_configs}] {label}")

        try:
            res = run_one(cfg, L_init, data, tau)
            elapsed = time.time() - t0
            result = {"label": label, **cfg, **res, "elapsed_s": elapsed}
            results.append(result)
            print(f"  → cost=${res['eval_cost']:.2f}, reserve={res['reserve_total']:.1f} MW, "
                  f"ρ={res['rho']:.2f}, iters={res['iters_done']}, "
                  f"best_train=${res['best_train_cost']:.2f}, time={elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  → FAILED: {e} (time={elapsed:.1f}s)")
            results.append({"label": label, **cfg, "eval_cost": np.inf, "feasible": False,
                            "elapsed_s": elapsed, "error": str(e)})

    # ── Summary ──
    print(f"\n{'='*70}")
    print("RESULTS (sorted by eval cost)")
    print(f"{'='*70}")

    results.sort(key=lambda r: r.get("eval_cost", np.inf) if r.get("feasible", False) else 1e9)

    print(f"\n{'Rk':<4} {'Cost ($)':<12} {'Res(MW)':<10} {'ρ':<8} {'Iters':<7} "
          f"{'BestTr':<12} {'Time':<8} {'Label'}")
    print("-" * 100)

    for rank, r in enumerate(results):
        cost = r.get("eval_cost", np.inf)
        res_t = r.get("reserve_total", 0)
        rho = r.get("rho", 0)
        iters = r.get("iters_done", 0)
        bt = r.get("best_train_cost", np.inf)
        el = r.get("elapsed_s", 0)
        feas = "" if r.get("feasible", False) else " INFEAS"
        print(f"{rank+1:<4} {cost:>10.2f}  {res_t:>8.1f}  "
              f"{rho:>6.2f}  {iters:>5}  "
              f"{bt:>10.2f}  {el:>6.1f}s  {r['label']}{feas}")

    # Save
    output_path = os.path.join(DATA_DIR, "nn_sweep_results.json")
    save_results = []
    for r in results:
        sr = {}
        for k, v in r.items():
            if isinstance(v, (np.floating, np.integer)):
                sr[k] = float(v)
            elif isinstance(v, np.ndarray):
                sr[k] = v.tolist()
            elif isinstance(v, float) and np.isinf(v):
                sr[k] = None
            else:
                sr[k] = v
        save_results.append(sr)
    with open(output_path, "w") as f:
        json.dump(save_results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Best config
    best = results[0]
    print(f"\n{'='*70}")
    print(f"BEST: {best['label']}")
    print(f"  Cost: ${best.get('eval_cost', 'N/A')}")
    print(f"  Reserve: {best.get('reserve_total', 'N/A')} MW")
    print(f"  ρ: {best.get('rho', 'N/A')}")
    print(f"  Iters: {best.get('iters_done', 'N/A')}")
    print(f"  Best train cost: ${best.get('best_train_cost', 'N/A')}")
    print(f"\n  Reference: StaticL=$95,335, Box=$99,540")
    print(f"  Gap to StaticL: ${best.get('eval_cost', 0) - 95335:.2f}")


if __name__ == "__main__":
    main()
