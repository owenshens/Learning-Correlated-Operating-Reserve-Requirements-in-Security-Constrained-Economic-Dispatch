"""
Coupled training loops and evaluation for the inter-zone transfer limit experiment.

Same 4 methods as methods.py, but Methods 3 & 4 train with the coupled SCED
(solve_coupled_sced) and use combined duals (μ_z + λ_z) for the profiled gradient.
Methods 1 & 2 are unchanged (no training); only evaluation uses the coupled SCED.
"""

import numpy as np
import torch
from scipy.stats import norm as sp_norm

from sced import (
    compute_reserve_requirements, gauge_scores_batch,
    smoothed_quantile, quantile_sensitivity,
    compute_profiled_gradient, project_cholesky,
    conformal_calibrate, gauge_gradient
)
from sced_coupled import solve_coupled_sced
from methods import ContextNN


def sp_norm_pdf_np(x):
    """Standard normal PDF (numpy)."""
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)


# =============================================================================
# Method 3: Static L trained with coupled SCED
# =============================================================================

def train_static_L_coupled(L_init, u_tune, A, T_z_max,
                           gen_data, zone_loads, zone_gens,
                           tau=0.95, eps=0.5, n_iters=200, lr=1e-2,
                           verbose=True):
    """Train a static L via profiled gradient using the coupled SCED.

    Same structure as train_static_L (methods.py) but:
    1. Calls solve_coupled_sced (with transfer constraints)
    2. Uses combined duals (mu_z + lambda_z) for the profiled gradient
    3. Passes combined duals to compute_profiled_gradient (reused unchanged)

    Args:
        L_init: (d, d) initial Cholesky factor
        u_tune: (n_tune, d) tune set uncertainty vectors
        A: (n_zones, d) allocation matrix
        T_z_max: (n_zones,) transfer capacity limits
        gen_data: DataFrame with generator data
        zone_loads: dict, zone_id -> load_mw
        zone_gens: dict, zone_id -> list of gen indices
        tau: coverage level
        eps: smoothing bandwidth
        n_iters: number of training iterations
        lr: learning rate
        verbose: print progress

    Returns:
        L: (d, d) trained Cholesky factor
        history: list of dicts with training history
    """
    L = L_init.copy()
    d = L.shape[0]
    history = []
    best_cost = np.inf
    best_L = L.copy()
    max_grad_norm = 10.0

    for k in range(n_iters):
        L_prev = L.copy()

        # Step A: Tuning — scores and smoothed quantile
        scores = gauge_scores_batch(L, u_tune)
        rho_hat = smoothed_quantile(scores, tau, eps)

        # Quantile sensitivity
        grad_rho = quantile_sensitivity(L, scores, u_tune, rho_hat, eps)

        # Step B: Coupled robust solve
        R_z_min = compute_reserve_requirements(L, rho_hat, A)
        sced_result = solve_coupled_sced(R_z_min, T_z_max, gen_data,
                                         zone_loads, zone_gens)

        if not sced_result['feasible']:
            L = L_prev
            lr *= 0.5
            if verbose and k % 20 == 0:
                print(f"  Iter {k:4d}: Coupled SCED infeasible, lr→{lr:.6f}")
            continue

        # Combined duals: reserve + transfer
        combined_mu = sced_result['mu_z'] + sced_result['lambda_z']
        cost = sced_result['cost']

        # Track best
        if cost < best_cost:
            best_cost = cost
            best_L = L.copy()

        # Step C: Profiled gradient (reuse existing function with combined duals)
        grad = compute_profiled_gradient(L, rho_hat, A, combined_mu, grad_rho)

        # Only update lower triangle
        grad_lower = np.tril(grad)

        # Gradient clipping
        grad_norm = np.linalg.norm(grad_lower)
        if grad_norm > max_grad_norm:
            grad_lower = grad_lower * (max_grad_norm / grad_norm)
            grad_norm = max_grad_norm

        # Gradient step
        L = L - lr * grad_lower

        # Project
        L = project_cholesky(L)

        history.append({
            'iter': k,
            'cost': cost,
            'rho_hat': rho_hat,
            'reserve_total': R_z_min.sum(),
            'grad_norm': grad_norm,
            'lambda_z_sum': sced_result['lambda_z'].sum(),
        })

        if verbose and k % 20 == 0:
            n_binding = np.sum(sced_result['lambda_z'] > 1e-6)
            print(f"  Iter {k:4d}: cost={cost:.1f}, ρ̂={rho_hat:.3f}, "
                  f"reserve={R_z_min.sum():.1f} MW, |∇|={grad_norm:.4f}, "
                  f"binding_transfers={n_binding}")

    return best_L, history


# =============================================================================
# Method 4: Context-dependent NN trained with coupled SCED
# =============================================================================

def train_context_nn_coupled(model, xi_tune, u_tune, A, T_z_max,
                              gen_data, zone_loads, zone_gens,
                              tau=0.95, eps=0.5, n_iters=1500, lr=3e-4,
                              batch_size=8, verbose=True):
    """Train context-dependent NN via profiled gradient + coupled SCED.

    Same structure as train_context_nn (methods.py) but uses solve_coupled_sced
    and combined duals for gradient computation.

    Args:
        model: ContextNN instance
        xi_tune: (n_tune, d_ctx) numpy
        u_tune: (n_tune, d) numpy
        A: (n_zones, d) allocation matrix
        T_z_max: (n_zones,) transfer capacity limits
        gen_data, zone_loads, zone_gens: SCED parameters
        tau, eps, n_iters, lr, batch_size: hyperparameters

    Returns:
        model: trained model
        history: list of dicts
    """
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    xi_tune_t = torch.tensor(xi_tune, dtype=torch.float32)
    u_tune_np = u_tune
    n_tune = len(u_tune)
    d = u_tune.shape[1]
    n_zones = A.shape[0]

    history = []
    rng = np.random.default_rng(42)
    best_cost = np.inf
    best_state = None
    patience = 400
    no_improve = 0

    for k in range(n_iters):
        model.eval()

        # Step 1: Compute gauge scores on tune set
        with torch.no_grad():
            L_tune = model(xi_tune_t)
            L_tune_np = L_tune.numpy()

        scores = np.zeros(n_tune)
        for i in range(n_tune):
            v = np.linalg.solve(L_tune_np[i], u_tune_np[i])
            scores[i] = np.linalg.norm(v)

        # Step 2: Smoothed quantile
        rho_hat = smoothed_quantile(scores, tau, eps)

        # Step 3: Sample batch
        batch_idx = rng.choice(n_tune, size=min(batch_size, n_tune), replace=False)
        xi_batch = xi_tune_t[batch_idx]

        model.train()
        optimizer.zero_grad()

        L_batch = model(xi_batch)  # (B, d, d)
        L_batch_np = L_batch.detach().numpy()
        B = len(batch_idx)

        # Step 4: Per-sample coupled SCED
        mu_z_batch = []
        lambda_z_batch = []
        costs_batch = []
        R_z_batch = []
        for b in range(B):
            R_z = compute_reserve_requirements(L_batch_np[b], rho_hat, A)
            R_z_batch.append(R_z)
            sced_result = solve_coupled_sced(R_z, T_z_max, gen_data,
                                             zone_loads, zone_gens)
            if sced_result['feasible']:
                mu_z_batch.append(sced_result['mu_z'])
                lambda_z_batch.append(sced_result['lambda_z'])
                costs_batch.append(sced_result['cost'])
            else:
                mu_z_batch.append(None)
                lambda_z_batch.append(None)
                costs_batch.append(None)

        n_feas = sum(1 for c in costs_batch if c is not None)
        if n_feas == 0:
            if verbose and k % 20 == 0:
                print(f"  Iter {k}: all coupled SCED infeasible")
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
                    print(f"  Early stopping at iter {k} (best cost={best_cost:.1f})")
                break

        # Step 5: Quantile sensitivity
        weights_qs = sp_norm_pdf_np((rho_hat - scores) / eps)
        total_w = weights_qs.sum()

        grad_rho_accum = np.zeros((d, d))
        if total_w > 1e-12:
            for i in range(n_tune):
                if weights_qs[i] > 1e-15:
                    grad_rho_accum += weights_qs[i] * gauge_gradient(L_tune_np[i], u_tune_np[i])
            grad_rho_accum /= total_w

        # Step 6: Profiled gradient per sample with combined duals
        grad_L_batch = torch.zeros_like(L_batch)

        for b in range(B):
            if mu_z_batch[b] is None:
                continue
            L_b = L_batch_np[b]
            # Combined duals
            combined_mu = mu_z_batch[b] + lambda_z_batch[b]

            g_shape = np.zeros((d, d))
            g_size = 0.0
            for z in range(n_zones):
                w_z = A[z, :]
                Lt_w = L_b.T @ w_z
                norm_Lt_w = np.linalg.norm(Lt_w)
                if norm_Lt_w < 1e-12 or combined_mu[z] < 1e-12:
                    continue
                g_shape += combined_mu[z] * rho_hat * np.outer(w_z, w_z) @ L_b / norm_Lt_w
                g_size += combined_mu[z] * norm_Lt_w

            profiled_grad = g_shape + g_size * grad_rho_accum
            pnorm = np.linalg.norm(profiled_grad)
            if pnorm > 100:
                profiled_grad = profiled_grad * (100 / pnorm)
            grad_L_batch[b] = torch.tensor(profiled_grad, dtype=torch.float32)

        # Backprop
        L_batch.backward(grad_L_batch / B)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        history.append({
            'iter': k,
            'cost': cost,
            'rho_hat': rho_hat,
            'reserve_total': avg_reserve,
        })

        if verbose and k % 20 == 0:
            print(f"  Iter {k:4d}: cost={cost:.1f}, ρ̂={rho_hat:.3f}, "
                  f"reserve={avg_reserve:.1f} MW")

    # Restore best
    if best_state is not None:
        model.load_state_dict(best_state)

    return model, history


# =============================================================================
# Evaluation helpers (coupled)
# =============================================================================

def evaluate_method_static_coupled(L, rho, A, T_z_max,
                                    gen_data, zone_loads, zone_gens):
    """Evaluate a static method with coupled SCED.

    Returns:
        dict with cost, R_z_min, reserve_total, feasible, mu_z, lambda_z
    """
    R_z_min = compute_reserve_requirements(L, rho, A)
    result = solve_coupled_sced(R_z_min, T_z_max, gen_data, zone_loads, zone_gens)
    return {
        'cost': result['cost'],
        'energy_cost': result.get('energy_cost', 0),
        'reserve_cost': result.get('reserve_cost', 0),
        'R_z_min': R_z_min,
        'reserve_total': R_z_min.sum(),
        'feasible': result['feasible'],
        'g': result['g'],
        'r': result['r'],
        'mu_z': result['mu_z'],
        'lambda_z': result['lambda_z'],
    }


def evaluate_method_context_coupled(model, xi, rho, A, T_z_max,
                                     gen_data, zone_loads, zone_gens):
    """Evaluate context-dependent method with coupled SCED (per-context).

    Returns:
        dict with cost (avg), R_z_min (avg), reserve_total (avg), feasible,
        lambda_z (avg)
    """
    model.eval()
    n = len(xi)
    n_zones = A.shape[0]
    xi_t = torch.tensor(xi, dtype=torch.float32)

    with torch.no_grad():
        L_all = model(xi_t).numpy()

    total_cost = 0.0
    total_energy_cost = 0.0
    total_reserve_cost = 0.0
    avg_R_z = np.zeros(n_zones)
    avg_lambda_z = np.zeros(n_zones)
    n_feasible = 0
    for i in range(n):
        R_z = compute_reserve_requirements(L_all[i], rho, A)
        avg_R_z += R_z
        result = solve_coupled_sced(R_z, T_z_max, gen_data, zone_loads, zone_gens)
        if result['feasible']:
            total_cost += result['cost']
            total_energy_cost += result.get('energy_cost', 0)
            total_reserve_cost += result.get('reserve_cost', 0)
            avg_lambda_z += result['lambda_z']
            n_feasible += 1
    avg_R_z /= n
    avg_lambda_z /= max(n_feasible, 1)

    return {
        'cost': total_cost / max(n_feasible, 1),
        'energy_cost': total_energy_cost / max(n_feasible, 1),
        'reserve_cost': total_reserve_cost / max(n_feasible, 1),
        'R_z_min': avg_R_z,
        'reserve_total': avg_R_z.sum(),
        'feasible': n_feasible == n,
        'lambda_z': avg_lambda_z,
    }
