"""
SCED (Security-Constrained Economic Dispatch) LP solver and gradient functions
for the differentiable robust optimization framework.

Regime 1: Zonal reserve (line limits non-binding).
All gradients are closed-form — no differentiation through the solver.
"""

import numpy as np
from scipy.optimize import linprog
from scipy.stats import norm as sp_norm


# =============================================================================
# Support and gauge functions
# =============================================================================

def support_function(L, rho, w):
    """σ_{U_{L,ρ}}(w) = ρ ||L^T w||_2

    Args:
        L: (d, d) lower triangular Cholesky factor
        rho: scalar radius
        w: (d,) exposure vector
    Returns:
        scalar support function value
    """
    Lt_w = L.T @ w
    return rho * np.linalg.norm(Lt_w)


def gauge_score(L, u):
    """s_L(u) = ||L^{-1} u||_2

    Args:
        L: (d, d) lower triangular Cholesky factor
        u: (d,) uncertainty vector
    Returns:
        scalar gauge score
    """
    v = np.linalg.solve(L, u)  # L^{-1} u via forward substitution
    return np.linalg.norm(v)


def gauge_scores_batch(L, U):
    """Compute gauge scores for a batch of uncertainty vectors.

    Args:
        L: (d, d) lower triangular Cholesky factor
        U: (n, d) uncertainty vectors
    Returns:
        scores: (n,) gauge scores
    """
    # Solve L V^T = U^T for V, then compute row norms
    V = np.linalg.solve(L, U.T).T  # (n, d)
    return np.linalg.norm(V, axis=1)


# =============================================================================
# Gradient functions
# =============================================================================

def support_gradient(L, rho, w):
    """∇_L σ_{U_{L,ρ}}(w) = ρ w w^T L / ||L^T w||_2

    Args:
        L: (d, d) lower triangular Cholesky factor
        rho: scalar radius
        w: (d,) exposure vector
    Returns:
        grad: (d, d) matrix gradient
    """
    Lt_w = L.T @ w  # (d,)
    norm_Lt_w = np.linalg.norm(Lt_w)
    if norm_Lt_w < 1e-12:
        return np.zeros_like(L)
    # w w^T L = outer(w, w) @ L
    grad = rho * np.outer(w, w) @ L / norm_Lt_w
    return grad


def gauge_gradient(L, u):
    """∇_L s_L(u) = -L^{-T} (L^{-1}u)(L^{-1}u)^T / ||L^{-1}u||_2

    Args:
        L: (d, d) lower triangular Cholesky factor
        u: (d,) uncertainty vector
    Returns:
        grad: (d, d) matrix gradient
    """
    v = np.linalg.solve(L, u)  # L^{-1} u, (d,)
    norm_v = np.linalg.norm(v)
    if norm_v < 1e-12:
        return np.zeros_like(L)
    L_inv_T = np.linalg.inv(L).T  # L^{-T}
    grad = -L_inv_T @ np.outer(v, v) / norm_v
    return grad


# =============================================================================
# Reserve requirements
# =============================================================================

def compute_reserve_requirements(L, rho, A):
    """Compute R_z^min = ρ ||L^T w_z||_2 for each zone.

    Args:
        L: (d, d) lower triangular Cholesky factor, d=15
        rho: scalar radius
        A: (n_zones, d) allocation matrix, n_zones=10, d=15
    Returns:
        R_z_min: (n_zones,) reserve requirements in MW
    """
    n_zones = A.shape[0]
    R_z_min = np.zeros(n_zones)
    for z in range(n_zones):
        w_z = A[z, :]  # exposure vector for zone z (= A^T e_z)
        R_z_min[z] = support_function(L, rho, w_z)
    return R_z_min


# =============================================================================
# SCED LP solver
# =============================================================================

def build_zone_gen_map(gen_data):
    """Build mapping from zone to generator indices.

    Args:
        gen_data: DataFrame with 'zone' column (1-indexed zones)
    Returns:
        zone_gens: dict mapping zone_id (1..10) -> list of gen indices (0-indexed)
    """
    zone_gens = {}
    for idx, row in gen_data.iterrows():
        z = int(row['zone'])
        if z not in zone_gens:
            zone_gens[z] = []
        zone_gens[z].append(idx)
    return zone_gens


def solve_sced(R_z_min, gen_data, zone_loads, zone_gens):
    """Solve the SCED LP given zonal reserve requirements.

    LP:
        min  Σ c1_i g_i + cr_i r_i
        s.t. Σ g_i = Σ D_z                   (power balance)
             g_i + r_i ≤ max_p_i              (capacity)
             g_i ≥ min_p_i                    (bounds)
             r_i ≥ 0                          (bounds)
             Σ_{i∈G_z} r_i ≥ R_z^min         (zonal reserve)

    Args:
        R_z_min: (10,) reserve requirements per zone in MW
        gen_data: DataFrame with columns: min_p_mw, max_p_mw, cost_c1, reserve_cost, zone
        zone_loads: dict or array, zone_id (1..10) -> load_mw
        zone_gens: dict, zone_id (1..10) -> list of gen indices

    Returns:
        result: dict with keys:
            cost: total cost
            g: (n_gen,) optimal dispatch
            r: (n_gen,) optimal reserves
            mu_z: (10,) dual multipliers on zonal reserve constraints
            feasible: bool
    """
    n_gen = len(gen_data)
    n_zones = 10

    # Decision variables: x = [g_1,...,g_n, r_1,...,r_n]  (2*n_gen)
    n_var = 2 * n_gen

    # Objective: min c^T x
    c = np.zeros(n_var)
    c[:n_gen] = gen_data['cost_c1'].values       # generation cost
    c[n_gen:] = gen_data['reserve_cost'].values   # reserve cost

    # Total demand
    if isinstance(zone_loads, dict):
        total_demand = sum(zone_loads.values())
    else:
        total_demand = sum(zone_loads)

    # Equality constraint: Σ g_i = total_demand
    A_eq = np.zeros((1, n_var))
    A_eq[0, :n_gen] = 1.0
    b_eq = np.array([total_demand])

    # Inequality constraints (A_ub x <= b_ub):
    # 1. Capacity: g_i + r_i <= max_p_i  (n_gen rows)
    # 2. Zonal reserve: -Σ_{i∈G_z} r_i <= -R_z^min  (n_zones rows)
    n_ub = n_gen + n_zones
    A_ub = np.zeros((n_ub, n_var))
    b_ub = np.zeros(n_ub)

    # Capacity constraints
    for i in range(n_gen):
        A_ub[i, i] = 1.0           # g_i
        A_ub[i, n_gen + i] = 1.0   # r_i
        b_ub[i] = gen_data.iloc[i]['max_p_mw']

    # Zonal reserve constraints (negated for <= form)
    for z_idx in range(n_zones):
        z_id = z_idx + 1  # 1-indexed
        row = n_gen + z_idx
        if z_id in zone_gens:
            for gen_idx in zone_gens[z_id]:
                A_ub[row, n_gen + gen_idx] = -1.0
        b_ub[row] = -R_z_min[z_idx]

    # Bounds
    bounds = []
    for i in range(n_gen):
        bounds.append((gen_data.iloc[i]['min_p_mw'], None))  # g_i >= min_p
    for i in range(n_gen):
        bounds.append((0.0, None))  # r_i >= 0

    # Solve
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method='highs')

    if not res.success:
        return {
            'cost': np.inf,
            'g': np.zeros(n_gen),
            'r': np.zeros(n_gen),
            'mu_z': np.zeros(n_zones),
            'feasible': False,
        }

    g_opt = res.x[:n_gen]
    r_opt = res.x[n_gen:]

    # Cost decomposition
    energy_cost = float(np.dot(gen_data['cost_c1'].values, g_opt))
    reserve_cost = float(np.dot(gen_data['reserve_cost'].values, r_opt))

    # Extract dual multipliers for zonal reserve constraints
    # In HiGHS, ineqlin.marginals gives dual values for A_ub constraints
    # Sign convention: for constraint a^T x <= b with dual y >= 0,
    # the LP dual is y. For our negated reserve constraint -Σ r_i <= -R_z,
    # the dual y_z corresponds to μ_z (shadow price of reserve requirement).
    if hasattr(res, 'ineqlin') and res.ineqlin is not None:
        ub_duals = res.ineqlin.marginals
        # Duals for zonal reserve are rows n_gen to n_gen+n_zones
        # HiGHS returns non-positive duals for <= constraints
        mu_z = -ub_duals[n_gen:n_gen + n_zones]
    else:
        # Fallback: try to get duals from the result
        mu_z = np.zeros(n_zones)

    return {
        'cost': res.fun,
        'energy_cost': energy_cost,
        'reserve_cost': reserve_cost,
        'g': g_opt,
        'r': r_opt,
        'mu_z': mu_z,
        'feasible': True,
    }


# =============================================================================
# Smoothed quantile and quantile sensitivity
# =============================================================================

def smoothed_quantile(scores, tau, eps):
    """Compute smoothed τ-quantile of scores via bisection.

    F̂(r) = (1/n) Σ_i Φ((r - S_i) / ε) ≥ τ

    Args:
        scores: (n,) gauge scores
        tau: target quantile (e.g. 0.95)
        eps: smoothing bandwidth
    Returns:
        rho_hat: smoothed quantile
    """
    lo, hi = scores.min() - 3 * eps, scores.max() + 3 * eps
    for _ in range(100):  # bisection iterations
        mid = (lo + hi) / 2
        F_mid = np.mean(sp_norm.cdf((mid - scores) / eps))
        if F_mid < tau:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def quantile_sensitivity(L, scores, U_tune, rho_hat, eps):
    """Compute the quantile sensitivity estimator ∇_L ρ̂_ε.

    ∇_L ρ̂_ε = Σ_i ω_i ∇_L s_L(u_i) / Σ_i ω_i
    where ω_i = φ((ρ̂ - S_i) / ε)

    Args:
        L: (d, d) Cholesky factor
        scores: (n,) gauge scores S_i = s_L(u_i)
        U_tune: (n, d) tune set uncertainty vectors
        rho_hat: smoothed quantile
        eps: bandwidth
    Returns:
        grad_rho: (d, d) quantile sensitivity matrix
    """
    d = L.shape[0]
    weights = sp_norm.pdf((rho_hat - scores) / eps)  # (n,)
    total_weight = weights.sum()

    if total_weight < 1e-12:
        return np.zeros((d, d))

    grad_rho = np.zeros((d, d))
    for i in range(len(scores)):
        if weights[i] > 1e-15:
            grad_rho += weights[i] * gauge_gradient(L, U_tune[i])

    grad_rho /= total_weight
    return grad_rho


# =============================================================================
# Profiled gradient
# =============================================================================

def compute_profiled_gradient(L, rho_hat, A, mu_z, grad_rho):
    """Compute the full profiled gradient ĝ = g_shape + g_size · ∇_L ρ̂.

    g_shape = Σ_z μ_z * ∇_L σ(w_z) = Σ_z μ_z * ρ̂ w_z w_z^T L / ||L^T w_z||_2
    g_size = Σ_z μ_z * ||L^T w_z||_2

    Args:
        L: (d, d) Cholesky factor
        rho_hat: smoothed quantile radius
        A: (n_zones, d) allocation matrix
        mu_z: (n_zones,) dual multipliers
        grad_rho: (d, d) quantile sensitivity
    Returns:
        grad: (d, d) profiled gradient
    """
    n_zones = A.shape[0]
    d = L.shape[0]

    g_shape = np.zeros((d, d))
    g_size = 0.0

    for z in range(n_zones):
        w_z = A[z, :]
        Lt_w = L.T @ w_z
        norm_Lt_w = np.linalg.norm(Lt_w)

        if norm_Lt_w < 1e-12 or mu_z[z] < 1e-12:
            continue

        # Envelope shape: μ_z * ρ̂ * w_z w_z^T L / ||L^T w_z||
        g_shape += mu_z[z] * support_gradient(L, rho_hat, w_z)

        # Envelope size: μ_z * ||L^T w_z||
        g_size += mu_z[z] * norm_Lt_w

    # Full profiled gradient
    grad = g_shape + g_size * grad_rho

    return grad


# =============================================================================
# Projection
# =============================================================================

def project_cholesky(L):
    """Project L to be lower triangular with positive diagonal and trace-normalized.

    1. Zero out upper triangle
    2. Clamp diagonal to be positive
    3. Trace normalize: L ← L / sqrt(tr(LL^T) / d)

    Args:
        L: (d, d) matrix
    Returns:
        L_proj: (d, d) valid Cholesky factor
    """
    d = L.shape[0]
    L_proj = np.tril(L)  # zero upper triangle
    diag = np.diag(L_proj)
    diag_clamped = np.maximum(diag, 1e-6)
    np.fill_diagonal(L_proj, diag_clamped)

    # Trace normalize
    trace_LLt = np.sum(L_proj ** 2)
    scale = np.sqrt(trace_LLt / d)
    if scale > 1e-12:
        L_proj = L_proj / scale

    return L_proj


# =============================================================================
# Conformal calibration
# =============================================================================

def conformal_calibrate(scores, tau):
    """Conformal calibration: find ρ such that coverage ≥ τ.

    Args:
        scores: (n,) gauge scores on calibration set
        tau: target coverage level
    Returns:
        rho: calibrated radius
    """
    n = len(scores)
    k = int(np.ceil((n + 1) * tau))
    k = min(k, n)  # cap at n
    sorted_scores = np.sort(scores)
    return sorted_scores[k - 1]  # 0-indexed
