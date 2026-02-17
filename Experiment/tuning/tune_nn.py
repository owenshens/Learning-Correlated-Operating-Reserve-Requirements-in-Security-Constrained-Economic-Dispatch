"""
Hyperparameter tuning for the context-dependent NN L(ξ) method.

Sweeps over learning rate, architecture, and other key hyperparameters.
Reports the best configuration by dispatch cost after conformal calibration.

Usage:
    python tune_nn.py
"""

import sys
import os
import json
import time
import itertools
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sced import (
    gauge_scores_batch, compute_reserve_requirements, solve_sced,
    smoothed_quantile, gauge_gradient, conformal_calibrate, build_zone_gen_map
)
from methods import sample_cov_method, compute_scores_context, evaluate_method_context

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UNCERT_DIR = os.path.join(DATA_DIR, "uncertainty")


# =============================================================================
# Flexible NN architecture (supports variable depth/width)
# =============================================================================

class FlexContextNN(nn.Module):
    """Neural network mapping context ξ → Cholesky factor L.

    Paper-exact architecture (Section III.C):
    1. MLP: ξ → h ∈ R^{d(d+1)/2}
    2. Fill lower triangle with h, exp() on diagonal for positivity
    3. Trace normalize: L ← L / sqrt(tr(LL^T) / d)

    Supports variable architecture via hidden_dims list.
    """

    def __init__(self, d_context=7, d_uncertainty=15, hidden_dims=None, dropout=0.0):
        super().__init__()
        self.d = d_uncertainty
        self.n_lower = d_uncertainty * (d_uncertainty + 1) // 2  # 120 for d=15

        if hidden_dims is None:
            hidden_dims = [64]

        layers = []
        in_dim = d_context
        for h in hidden_dims:
            layers.append(nn.Linear(in_dim, h))
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            in_dim = h
        layers.append(nn.Linear(in_dim, self.n_lower))
        self.net = nn.Sequential(*layers)

        self.tril_indices = torch.tril_indices(d_uncertainty, d_uncertainty)
        self.diag_indices = torch.arange(d_uncertainty)

    def initialize_from_L(self, L_static):
        """Initialize so that NN(ξ) ≈ trace-normalized L_static for all ξ."""
        d = self.d
        frob = np.sqrt(np.sum(L_static ** 2) / d)
        L_normed = L_static / frob if frob > 1e-12 else L_static

        target = np.zeros(self.n_lower)
        idx = 0
        for i in range(d):
            for j in range(i + 1):
                if i == j:
                    target[idx] = np.log(max(L_normed[i, j], 1e-6))
                else:
                    target[idx] = L_normed[i, j]
                idx += 1

        with torch.no_grad():
            last_layer = self.net[-1]
            last_layer.bias.copy_(torch.tensor(target, dtype=torch.float32))
            last_layer.weight.data *= 0.01
            for m in self.net:
                if isinstance(m, nn.Linear) and m is not last_layer:
                    m.weight.data *= 0.1

    def forward(self, xi):
        batch = xi.shape[0]
        d = self.d
        h = self.net(xi)

        L = torch.zeros(batch, d, d, device=xi.device, dtype=xi.dtype)
        L[:, self.tril_indices[0], self.tril_indices[1]] = h
        diag_vals = L[:, self.diag_indices, self.diag_indices]
        L[:, self.diag_indices, self.diag_indices] = torch.exp(diag_vals)

        # Trace normalization: tr(LL^T) = d
        trace = (L ** 2).sum(dim=(1, 2))
        scale = torch.sqrt(trace / d).unsqueeze(-1).unsqueeze(-1)
        scale = torch.clamp(scale, min=1e-8)
        L = L / scale

        return L


def sp_norm_pdf_np(x):
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)


# =============================================================================
# Training function with configurable hyperparameters
# =============================================================================

def train_nn_config(model, xi_tune, u_tune, A, gen_data, zone_loads, zone_gens,
                    tau=0.95, eps=0.5, n_iters=300, lr=1e-3, batch_size=256,
                    weight_decay=0.0, lr_schedule="none", patience=80,
                    grad_clip_nn=1.0, grad_clip_sample=100.0,
                    verbose=False):
    """Train context-dependent NN with configurable hyperparameters.

    Returns: model, history, best_cost
    """
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    # LR scheduler
    scheduler = None
    if lr_schedule == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_iters, eta_min=lr * 0.01)
    elif lr_schedule == "step":
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=n_iters // 3, gamma=0.3)

    xi_tune_t = torch.tensor(xi_tune, dtype=torch.float32)
    u_tune_np = u_tune
    n_tune = len(u_tune)
    d = u_tune.shape[1]
    n_zones = A.shape[0]

    history = []
    rng = np.random.default_rng(42)
    best_cost = np.inf
    best_state = None
    no_improve = 0

    for k in range(n_iters):
        model.eval()

        # Gauge scores on tune set
        with torch.no_grad():
            L_tune = model(xi_tune_t)
            L_tune_np = L_tune.numpy()

        scores = np.zeros(n_tune)
        for i in range(n_tune):
            v = np.linalg.solve(L_tune_np[i], u_tune_np[i])
            scores[i] = np.linalg.norm(v)

        rho_hat = smoothed_quantile(scores, tau, eps)

        # Batch
        batch_idx = rng.choice(n_tune, size=min(batch_size, n_tune), replace=False)
        xi_batch = xi_tune_t[batch_idx]

        model.train()
        optimizer.zero_grad()
        L_batch = model(xi_batch)
        L_batch_np = L_batch.detach().numpy()
        B = len(batch_idx)

        # Per-sample SCED for context-specific duals
        mu_z_batch = []
        costs_batch = []
        R_z_batch = []
        for b in range(B):
            R_z = compute_reserve_requirements(L_batch_np[b], rho_hat, A)
            R_z_batch.append(R_z)
            sced_result = solve_sced(R_z, gen_data, zone_loads, zone_gens)
            if sced_result['feasible']:
                mu_z_batch.append(sced_result['mu_z'])
                costs_batch.append(sced_result['cost'])
            else:
                mu_z_batch.append(None)
                costs_batch.append(None)

        n_feas = sum(1 for c in costs_batch if c is not None)
        if n_feas == 0:
            if scheduler:
                scheduler.step()
            continue

        cost = sum(c for c in costs_batch if c is not None) / n_feas
        avg_reserve = np.mean([R.sum() for R in R_z_batch])

        # Track best
        if cost < best_cost:
            best_cost = cost
            best_state = {kk: v.clone() for kk, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                if verbose:
                    print(f"  Early stop at iter {k} (best={best_cost:.1f})")
                break

        # Quantile sensitivity (averaged gauge gradient near boundary)
        weights_qs = sp_norm_pdf_np((rho_hat - scores) / eps)
        total_w = weights_qs.sum()

        grad_rho_accum = np.zeros((d, d))
        if total_w > 1e-12:
            for i in range(n_tune):
                if weights_qs[i] > 1e-15:
                    grad_rho_accum += weights_qs[i] * gauge_gradient(L_tune_np[i], u_tune_np[i])
            grad_rho_accum /= total_w

        # Profiled gradient per sample with its own context-specific duals
        grad_L_batch = torch.zeros_like(L_batch)

        for b in range(B):
            if mu_z_batch[b] is None:
                continue
            L_b = L_batch_np[b]
            mu_z = mu_z_batch[b]
            g_shape = np.zeros((d, d))
            g_size = 0.0
            for z in range(n_zones):
                w_z = A[z, :]
                Lt_w = L_b.T @ w_z
                norm_Lt_w = np.linalg.norm(Lt_w)
                if norm_Lt_w < 1e-12 or mu_z[z] < 1e-12:
                    continue
                g_shape += mu_z[z] * rho_hat * np.outer(w_z, w_z) @ L_b / norm_Lt_w
                g_size += mu_z[z] * norm_Lt_w

            profiled_grad = g_shape + g_size * grad_rho_accum
            pnorm = np.linalg.norm(profiled_grad)
            if pnorm > grad_clip_sample:
                profiled_grad = profiled_grad * (grad_clip_sample / pnorm)
            grad_L_batch[b] = torch.tensor(profiled_grad, dtype=torch.float32)

        L_batch.backward(grad_L_batch / B)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip_nn)
        optimizer.step()
        if scheduler:
            scheduler.step()

        history.append({'iter': k, 'cost': cost, 'rho_hat': rho_hat,
                        'reserve_total': avg_reserve})

        if verbose and k % 50 == 0:
            cur_lr = optimizer.param_groups[0]['lr']
            print(f"  Iter {k:4d}: cost={cost:.1f}, ρ̂={rho_hat:.3f}, "
                  f"reserve={avg_reserve:.1f} MW, lr={cur_lr:.6f}")

    if best_state is not None:
        model.load_state_dict(best_state)

    return model, history, best_cost


# =============================================================================
# Data loading (reused from run_experiment.py)
# =============================================================================

def load_data():
    print("Loading data...")
    u_df = pd.read_parquet(os.path.join(UNCERT_DIR, "uncertainty_15d.parquet"))
    U = u_df.values
    ctx_df = pd.read_parquet(os.path.join(UNCERT_DIR, "context_7d.parquet"))
    Xi = ctx_df.values
    L_true_t = np.load(os.path.join(UNCERT_DIR, "L_true_t.npy"))
    A = np.load(os.path.join(UNCERT_DIR, "allocation_matrix.npy"))
    with open(os.path.join(UNCERT_DIR, "metadata.json")) as f:
        metadata = json.load(f)
    gen_data = pd.read_csv(os.path.join(DATA_DIR, "generator_data.csv"))
    zone_df = pd.read_csv(os.path.join(DATA_DIR, "zone_summary.csv"))
    zone_loads = {int(row['zone']): float(row['load_mw']) for _, row in zone_df.iterrows()}
    zone_gens = build_zone_gen_map(gen_data)

    split = metadata["split_indices"]
    t_tune = split["tune"]
    t_cal = split["calibrate"]

    return {
        "u_tune": U[t_tune[0]:t_tune[1]],
        "xi_tune": Xi[t_tune[0]:t_tune[1]],
        "u_cal": U[t_cal[0]:t_cal[1]],
        "xi_cal": Xi[t_cal[0]:t_cal[1]],
        "u_train": U[split["train"][0]:split["train"][1]],
        "L_true_cal": L_true_t[t_cal[0]:t_cal[1]],
        "A": A,
        "gen_data": gen_data,
        "zone_loads": zone_loads,
        "zone_gens": zone_gens,
    }


def compute_scores_flex(model, xi, U):
    """Compute gauge scores for flexible NN."""
    model.eval()
    n = len(U)
    xi_t = torch.tensor(xi, dtype=torch.float32)
    with torch.no_grad():
        L_all = model(xi_t).numpy()
    scores = np.zeros(n)
    for i in range(n):
        v = np.linalg.solve(L_all[i], U[i])
        scores[i] = np.linalg.norm(v)
    return scores


def evaluate_flex(model, xi_cal, u_cal, rho, A, gen_data, zone_loads, zone_gens):
    """Evaluate flexible NN model: per-context SCED, average cost."""
    model.eval()
    n = len(xi_cal)
    n_zones = A.shape[0]
    xi_t = torch.tensor(xi_cal, dtype=torch.float32)
    with torch.no_grad():
        L_all = model(xi_t).numpy()
    total_cost = 0.0
    avg_R_z = np.zeros(n_zones)
    n_feasible = 0
    for i in range(n):
        R_z = compute_reserve_requirements(L_all[i], rho, A)
        avg_R_z += R_z
        result = solve_sced(R_z, gen_data, zone_loads, zone_gens)
        if result['feasible']:
            total_cost += result['cost']
            n_feasible += 1
    avg_R_z /= n
    return {
        'cost': total_cost / max(n_feasible, 1),
        'R_z_min': avg_R_z,
        'reserve_total': avg_R_z.sum(),
        'feasible': n_feasible == n,
    }


# =============================================================================
# Main tuning loop
# =============================================================================

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

    # Get L_cov, then train StaticL for task-aware initialization
    L_cov = sample_cov_method(u_train)
    from methods import train_static_L
    print("Training StaticL for NN initialization...")
    L_static, _ = train_static_L(
        L_init=L_cov.copy(),
        u_tune=u_tune, A=A,
        gen_data=gen_data, zone_loads=zone_loads, zone_gens=zone_gens,
        tau=0.95, eps=0.5, n_iters=200, lr=1e-2, verbose=False,
    )
    L_init = L_static

    # ======================================================================
    # Hyperparameter grid
    # ======================================================================
    configs = []

    # Sweep learning rate × architecture × LR schedule
    for lr in [3e-4, 1e-3, 3e-3, 1e-2]:
        for hidden_dims in [[64], [128], [64, 64], [128, 64]]:
            for lr_schedule in ["none", "cosine"]:
                configs.append({
                    "lr": lr,
                    "hidden_dims": hidden_dims,
                    "lr_schedule": lr_schedule,
                    "batch_size": 512,
                    "weight_decay": 0.0,
                    "n_iters": 300,
                    "patience": 100,
                    "eps": 0.5,
                    "grad_clip_nn": 1.0,
                    "grad_clip_sample": 100.0,
                })

    # Add some configs with weight decay
    for lr in [1e-3, 3e-3]:
        for hidden_dims in [[128], [64, 64]]:
            configs.append({
                "lr": lr,
                "hidden_dims": hidden_dims,
                "lr_schedule": "cosine",
                "batch_size": 512,
                "weight_decay": 1e-4,
                "n_iters": 300,
                "patience": 100,
                "eps": 0.5,
                "grad_clip_nn": 1.0,
                "grad_clip_sample": 100.0,
            })

    # Add configs with larger batch size
    for lr in [1e-3, 3e-3]:
        for hidden_dims in [[128], [64, 64]]:
            configs.append({
                "lr": lr,
                "hidden_dims": hidden_dims,
                "lr_schedule": "cosine",
                "batch_size": 1024,
                "weight_decay": 0.0,
                "n_iters": 300,
                "patience": 100,
                "eps": 0.5,
                "grad_clip_nn": 1.0,
                "grad_clip_sample": 100.0,
            })

    # Add configs with higher NN gradient clip
    for lr in [3e-3, 1e-2]:
        for hidden_dims in [[128], [64, 64]]:
            configs.append({
                "lr": lr,
                "hidden_dims": hidden_dims,
                "lr_schedule": "cosine",
                "batch_size": 512,
                "weight_decay": 0.0,
                "n_iters": 300,
                "patience": 100,
                "eps": 0.5,
                "grad_clip_nn": 5.0,
                "grad_clip_sample": 100.0,
            })

    n_configs = len(configs)
    print(f"\n{'='*70}")
    print(f"HYPERPARAMETER SWEEP: {n_configs} configurations")
    print(f"{'='*70}")

    results = []

    for idx, cfg in enumerate(configs):
        t0 = time.time()
        tag = (f"lr={cfg['lr']}, hidden={cfg['hidden_dims']}, "
               f"sched={cfg['lr_schedule']}, bs={cfg['batch_size']}, "
               f"wd={cfg['weight_decay']}, clip_nn={cfg['grad_clip_nn']}")
        print(f"\n[{idx+1}/{n_configs}] {tag}")

        # Build model
        model = FlexContextNN(d_context=7, d_uncertainty=d, hidden_dims=cfg["hidden_dims"])
        model.initialize_from_L(L_init)

        # Train
        model, hist, best_train_cost = train_nn_config(
            model=model,
            xi_tune=xi_tune,
            u_tune=u_tune,
            A=A,
            gen_data=gen_data,
            zone_loads=zone_loads,
            zone_gens=zone_gens,
            tau=tau,
            eps=cfg["eps"],
            n_iters=cfg["n_iters"],
            lr=cfg["lr"],
            batch_size=cfg["batch_size"],
            weight_decay=cfg["weight_decay"],
            lr_schedule=cfg["lr_schedule"],
            patience=cfg["patience"],
            grad_clip_nn=cfg["grad_clip_nn"],
            grad_clip_sample=cfg["grad_clip_sample"],
            verbose=False,
        )

        # Evaluate: conformal calibrate on cal set
        scores_cal = compute_scores_flex(model, xi_cal, u_cal)
        rho = conformal_calibrate(scores_cal, tau)
        coverage = np.mean(scores_cal <= rho)
        eval_result = evaluate_flex(model, xi_cal, u_cal, rho, A, gen_data, zone_loads, zone_gens)

        elapsed = time.time() - t0
        iters_done = len(hist)

        result = {
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

    # ======================================================================
    # Summary
    # ======================================================================
    print(f"\n{'='*70}")
    print("RESULTS SUMMARY (sorted by eval cost)")
    print(f"{'='*70}")

    # Sort by eval cost
    results.sort(key=lambda r: r["eval_cost"] if r["feasible"] else 1e9)

    print(f"\n{'Rank':<5} {'Cost ($)':<12} {'Reserve':<10} {'ρ':<10} {'Iters':<7} "
          f"{'LR':<8} {'Hidden':<14} {'Sched':<8} {'BS':<6} {'WD':<8} {'ClipNN':<8} {'Time':<8}")
    print("-" * 115)

    for rank, r in enumerate(results):
        feas = "" if r["feasible"] else " (INFEAS)"
        print(f"{rank+1:<5} {r['eval_cost']:>10.2f}  {r['reserve_total']:>8.1f}  "
              f"{r['rho']:>8.2f}  {r['iters_done']:>5}  "
              f"{r['lr']:<8.0e} {str(r['hidden_dims']):<14} {r['lr_schedule']:<8} "
              f"{r['batch_size']:<6} {r['weight_decay']:<8.0e} {r['grad_clip_nn']:<8.1f} "
              f"{r['elapsed_s']:>6.1f}s{feas}")

    # Save results
    output_path = os.path.join(DATA_DIR, "nn_tuning_results.json")
    for r in results:
        r["hidden_dims"] = list(r["hidden_dims"])
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Print best config
    best = results[0]
    print(f"\n{'='*70}")
    print(f"BEST CONFIGURATION:")
    print(f"{'='*70}")
    print(f"  Cost: ${best['eval_cost']:.2f}")
    print(f"  Reserve: {best['reserve_total']:.1f} MW")
    print(f"  Coverage: {best['coverage']:.4f}")
    print(f"  ρ: {best['rho']:.4f}")
    print(f"  LR: {best['lr']}")
    print(f"  Hidden dims: {best['hidden_dims']}")
    print(f"  LR schedule: {best['lr_schedule']}")
    print(f"  Batch size: {best['batch_size']}")
    print(f"  Weight decay: {best['weight_decay']}")
    print(f"  Grad clip (NN): {best['grad_clip_nn']}")
    print(f"  Iterations: {best['iters_done']}")

    # Reference: StaticL cost was $95,071, Box was $98,527
    print(f"\n  Reference costs:")
    print(f"    StaticL: $95,071")
    print(f"    Box:     $98,527")
    print(f"    Gap to StaticL: ${best['eval_cost'] - 95071:.2f}")


if __name__ == "__main__":
    main()
