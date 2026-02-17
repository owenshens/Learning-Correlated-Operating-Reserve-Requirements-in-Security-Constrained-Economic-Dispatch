"""
Four methods for constructing ellipsoidal uncertainty sets:
1. Box (diagonal L)
2. Sample Covariance (full L from data)
3. Static L (task-aware, profiled gradient)
4. Context-dependent NN L(ξ) (task-aware, profiled gradient + neural network)
"""

import numpy as np
import torch
import torch.nn as nn
from sced import (
    gauge_scores_batch, compute_reserve_requirements, solve_sced,
    smoothed_quantile, quantile_sensitivity, compute_profiled_gradient,
    project_cholesky, conformal_calibrate, gauge_gradient
)


# =============================================================================
# Method 1: Box (axis-aligned ellipsoid)
# =============================================================================

def box_method(u_train):
    """Construct L = diag(σ̂_1, ..., σ̂_d) from training data marginal stds.

    Args:
        u_train: (n, d) training uncertainty vectors
    Returns:
        L: (d, d) diagonal Cholesky factor
    """
    d = u_train.shape[1]
    sigmas = u_train.std(axis=0)
    sigmas = np.maximum(sigmas, 1e-8)  # avoid zero
    L = np.diag(sigmas)
    return L


# =============================================================================
# Method 2: Sample Covariance
# =============================================================================

def sample_cov_method(u_train):
    """Construct L = chol(Σ̂) from training data sample covariance.

    Args:
        u_train: (n, d) training uncertainty vectors
    Returns:
        L: (d, d) lower triangular Cholesky factor
    """
    Sigma = np.cov(u_train.T)  # (d, d)
    # Ensure PSD
    eigvals = np.linalg.eigvalsh(Sigma)
    if eigvals.min() < 1e-10:
        Sigma += (1e-8 - eigvals.min()) * np.eye(Sigma.shape[0])
    L = np.linalg.cholesky(Sigma)
    return L


# =============================================================================
# Method 3: Static L (profiled gradient training)
# =============================================================================

def train_static_L(L_init, u_tune, A, gen_data, zone_loads, zone_gens,
                   tau=0.95, eps=0.5, n_iters=200, lr=1e-2,
                   verbose=True):
    """Train a static L via profiled gradient (Algorithm 1).

    Args:
        L_init: (d, d) initial Cholesky factor (e.g., from sample_cov_method)
        u_tune: (n_tune, d) tune set uncertainty vectors
        A: (n_zones, d) allocation matrix
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
    max_grad_norm = 10.0  # gradient clipping threshold

    for k in range(n_iters):
        L_prev = L.copy()

        # Step A: Tuning — compute scores and smoothed quantile
        scores = gauge_scores_batch(L, u_tune)
        rho_hat = smoothed_quantile(scores, tau, eps)

        # Quantile sensitivity
        grad_rho = quantile_sensitivity(L, scores, u_tune, rho_hat, eps)

        # Step B: Robust solve
        R_z_min = compute_reserve_requirements(L, rho_hat, A)
        sced_result = solve_sced(R_z_min, gen_data, zone_loads, zone_gens)

        if not sced_result['feasible']:
            # Revert to previous L and reduce step size
            L = L_prev
            lr *= 0.5
            if verbose and k % 20 == 0:
                print(f"  Iter {k:4d}: SCED infeasible, lr→{lr:.6f}")
            continue

        mu_z = sced_result['mu_z']
        cost = sced_result['cost']

        # Track best
        if cost < best_cost:
            best_cost = cost
            best_L = L.copy()

        # Step C: Profiled gradient
        grad = compute_profiled_gradient(L, rho_hat, A, mu_z, grad_rho)

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
        })

        if verbose and k % 20 == 0:
            print(f"  Iter {k:4d}: cost={cost:.1f}, ρ̂={rho_hat:.3f}, "
                  f"reserve={R_z_min.sum():.1f} MW, |∇|={grad_norm:.4f}, lr={lr:.5f}")

    return best_L, history


# =============================================================================
# Method 4: Context-dependent NN L(ξ)
# =============================================================================

class ContextNN(nn.Module):
    """Neural network mapping context ξ → Cholesky factor L.

    Paper-exact architecture (Section III.C):
    1. MLP: ξ → h ∈ R^{d(d+1)/2}
    2. Fill lower triangle with h, exp() on diagonal for positivity
    3. Trace normalize: L ← L / sqrt(tr(LL^T) / d)
    """

    def __init__(self, d_context=7, d_uncertainty=15, hidden=64, hidden_dims=None):
        super().__init__()
        self.d = d_uncertainty
        self.n_lower = d_uncertainty * (d_uncertainty + 1) // 2  # 120 for d=15

        if hidden_dims is None:
            hidden_dims = [hidden]

        layers = []
        in_dim = d_context
        for h in hidden_dims:
            layers.append(nn.Linear(in_dim, h))
            layers.append(nn.ReLU())
            in_dim = h
        layers.append(nn.Linear(in_dim, self.n_lower))
        self.net = nn.Sequential(*layers)

        self.tril_indices = torch.tril_indices(d_uncertainty, d_uncertainty)
        self.diag_indices = torch.arange(d_uncertainty)

    def initialize_from_L(self, L_static):
        """Initialize so that NN(ξ) ≈ trace-normalized L_static for all ξ."""
        d = self.d
        # Trace-normalize input L for consistent initialization
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


def train_context_nn(model, xi_tune, u_tune, A, gen_data, zone_loads, zone_gens,
                     tau=0.95, eps=0.5, n_iters=1500, lr=3e-4, batch_size=8,
                     verbose=True):
    """Train context-dependent NN via profiled gradient + autograd.

    At each iteration:
    1. Compute gauge scores on tune set (using NN forward pass)
    2. Compute smoothed quantile ρ̂
    3. Sample a batch of training contexts, compute L(ξ_t)
    4. Per-sample: compute R_z(ξ_t) → solve SCED → get context-specific μ*(ξ_t)
    5. Compute profiled gradient ∂J/∂L per sample with its own duals
    6. Backprop through NN

    Args:
        model: ContextNN instance
        xi_tune: (n_tune, d_ctx) tune context features (numpy)
        u_tune: (n_tune, d) tune uncertainty vectors (numpy)
        A: (n_zones, d) allocation matrix (numpy)
        gen_data: DataFrame
        zone_loads, zone_gens: SCED parameters
        tau, eps, n_iters, lr, batch_size: hyperparameters

    Returns:
        model: trained model
        history: list of dicts
    """
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    A_torch = torch.tensor(A, dtype=torch.float32)
    xi_tune_t = torch.tensor(xi_tune, dtype=torch.float32)
    u_tune_np = u_tune
    n_tune = len(u_tune)
    d = u_tune.shape[1]
    n_zones = A.shape[0]

    history = []
    rng = np.random.default_rng(42)
    best_cost = np.inf
    best_state = None
    patience = 400  # early stopping patience
    no_improve = 0

    for k in range(n_iters):
        model.eval()

        # Step 1: Compute gauge scores on tune set
        with torch.no_grad():
            L_tune = model(xi_tune_t)  # (n_tune, d, d)
            L_tune_np = L_tune.numpy()

        scores = np.zeros(n_tune)
        for i in range(n_tune):
            v = np.linalg.solve(L_tune_np[i], u_tune_np[i])
            scores[i] = np.linalg.norm(v)

        # Step 2: Smoothed quantile
        rho_hat = smoothed_quantile(scores, tau, eps)

        # Step 3: Sample a batch of contexts from tune set
        batch_idx = rng.choice(n_tune, size=min(batch_size, n_tune), replace=False)
        xi_batch = xi_tune_t[batch_idx]  # (B, d_ctx)

        model.train()
        optimizer.zero_grad()

        # Forward pass for batch
        L_batch = model(xi_batch)  # (B, d, d) — requires grad

        # Step 4: Per-sample SCED for context-specific duals
        L_batch_np = L_batch.detach().numpy()
        B = len(batch_idx)

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
            if verbose and k % 20 == 0:
                print(f"  Iter {k}: all SCED infeasible")
            continue

        cost = sum(c for c in costs_batch if c is not None) / n_feas
        avg_reserve = np.mean([R.sum() for R in R_z_batch])

        # Track best model (early stopping)
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

        # Step 5: Compute quantile sensitivity (average over near-boundary tune samples)
        weights_qs = sp_norm_pdf_np((rho_hat - scores) / eps)
        total_w = weights_qs.sum()

        grad_rho_accum = np.zeros((d, d))
        if total_w > 1e-12:
            for i in range(n_tune):
                if weights_qs[i] > 1e-15:
                    grad_rho_accum += weights_qs[i] * gauge_gradient(L_tune_np[i], u_tune_np[i])
            grad_rho_accum /= total_w

        # Step 6: Compute profiled gradient per sample with its own duals
        grad_L_batch = torch.zeros_like(L_batch)

        for b in range(B):
            if mu_z_batch[b] is None:
                continue
            L_b = L_batch_np[b]
            mu_z = mu_z_batch[b]
            # Envelope shape + size
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
            # Gradient clipping per sample
            pnorm = np.linalg.norm(profiled_grad)
            if pnorm > 100:
                profiled_grad = profiled_grad * (100 / pnorm)
            grad_L_batch[b] = torch.tensor(profiled_grad, dtype=torch.float32)

        # Backprop: set custom gradient on L_batch
        L_batch.backward(grad_L_batch / B)

        # Gradient clipping on NN parameters
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        # Step 7: Optimizer step
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

    # Restore best model
    if best_state is not None:
        model.load_state_dict(best_state)

    return model, history


def sp_norm_pdf_np(x):
    """Standard normal PDF (numpy)."""
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)


# =============================================================================
# Evaluation helpers
# =============================================================================

def compute_scores_static(L, U):
    """Compute gauge scores for static L."""
    return gauge_scores_batch(L, U)


def compute_scores_context(model, xi, U):
    """Compute gauge scores for context-dependent L(ξ).

    Args:
        model: ContextNN
        xi: (n, d_ctx) numpy
        U: (n, d) numpy
    Returns:
        scores: (n,) numpy
    """
    model.eval()
    n = len(U)
    d = U.shape[1]
    xi_t = torch.tensor(xi, dtype=torch.float32)

    with torch.no_grad():
        L_all = model(xi_t).numpy()  # (n, d, d)

    scores = np.zeros(n)
    for i in range(n):
        v = np.linalg.solve(L_all[i], U[i])
        scores[i] = np.linalg.norm(v)

    return scores


def evaluate_method_static(L, rho, A, gen_data, zone_loads, zone_gens):
    """Evaluate a static method: compute cost and reserves.

    Returns:
        dict with cost, R_z_min, reserve_total, feasible
    """
    R_z_min = compute_reserve_requirements(L, rho, A)
    result = solve_sced(R_z_min, gen_data, zone_loads, zone_gens)
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
    }


def evaluate_method_context(model, xi, rho, A, gen_data, zone_loads, zone_gens):
    """Evaluate context-dependent method: per-context SCED, average cost.

    For each context ξ_t: compute L(ξ_t) → R_z(ξ_t) → solve SCED → cost_t.
    Report average cost over all contexts (the operational reality).

    Args:
        model: ContextNN
        xi: (n, d_ctx) numpy context features
        rho: calibrated radius
        A, gen_data, zone_loads, zone_gens: SCED parameters
    Returns:
        dict with cost (avg), R_z_min (avg), reserve_total (avg), feasible
    """
    model.eval()
    n = len(xi)
    n_zones = A.shape[0]
    xi_t = torch.tensor(xi, dtype=torch.float32)

    with torch.no_grad():
        L_all = model(xi_t).numpy()  # (n, d, d)

    # Per-context SCED evaluation
    total_cost = 0.0
    total_energy_cost = 0.0
    total_reserve_cost = 0.0
    avg_R_z = np.zeros(n_zones)
    n_feasible = 0
    for i in range(n):
        R_z = compute_reserve_requirements(L_all[i], rho, A)
        avg_R_z += R_z
        result = solve_sced(R_z, gen_data, zone_loads, zone_gens)
        if result['feasible']:
            total_cost += result['cost']
            total_energy_cost += result.get('energy_cost', 0)
            total_reserve_cost += result.get('reserve_cost', 0)
            n_feasible += 1
    avg_R_z /= n

    return {
        'cost': total_cost / max(n_feasible, 1),
        'energy_cost': total_energy_cost / max(n_feasible, 1),
        'reserve_cost': total_reserve_cost / max(n_feasible, 1),
        'R_z_min': avg_R_z,
        'reserve_total': avg_R_z.sum(),
        'feasible': n_feasible == n,
    }
