"""
Coupled SCED LP solver with inter-zone transfer limits.

Extends the decoupled SCED (sced.py) by adding robust transfer constraints:
  |Export_z| + ρ ||L^T A[z,:]||₂ ≤ T_z^max

The transfer margin σ_z = ρ ||L^T A[z,:]||₂ = R_z^min (same support function
as zonal reserves), so the combined envelope gradient uses (μ_z + λ_z) with
the SAME exposure vectors A[z,:]. No new gradient function is needed.
"""

import numpy as np
from scipy.optimize import linprog


def solve_coupled_sced(R_z_min, T_z_max, gen_data, zone_loads, zone_gens):
    """Solve SCED LP with zonal reserves + inter-zone transfer limits.

    LP decision variables: x = [g_1,...,g_n, r_1,...,r_n]

    Constraints:
      Power balance:   Σ g_i = total_demand                        [1 eq]
      Capacity:        g_i + r_i ≤ max_p_i                         [n_gen ineq]
      Zonal reserve:   -Σ_{i∈G_z} r_i ≤ -R_z^min                  [10 ineq]
      Upper transfer:  Σ_{i∈G_z} g_i ≤ D_z + (T_z^max - R_z^min)  [10 ineq]
      Lower transfer: -Σ_{i∈G_z} g_i ≤ -D_z + (T_z^max - R_z^min) [10 ineq]

    The transfer constraint enforces:
      |Σ_{i∈G_z} g_i - D_z| + R_z^min ≤ T_z^max

    Note: R_z^min serves double duty as both the zonal reserve requirement
    AND the robust transfer margin (σ_z = ρ||L^T A[z,:]||₂ = R_z^min).

    Args:
        R_z_min: (10,) reserve requirements per zone in MW
        T_z_max: (10,) transfer capacity limits per zone in MW
        gen_data: DataFrame with columns: min_p_mw, max_p_mw, cost_c1, reserve_cost, zone
        zone_loads: dict, zone_id (1..10) -> load_mw
        zone_gens: dict, zone_id (1..10) -> list of gen indices

    Returns:
        dict with keys:
            cost: total cost
            g: (n_gen,) optimal dispatch
            r: (n_gen,) optimal reserves
            mu_z: (10,) dual multipliers on zonal reserve constraints
            lambda_z: (10,) combined transfer duals (upper + lower)
            feasible: bool
    """
    n_gen = len(gen_data)
    n_zones = 10
    n_var = 2 * n_gen

    # Objective: min c^T x
    c = np.zeros(n_var)
    c[:n_gen] = gen_data['cost_c1'].values
    c[n_gen:] = gen_data['reserve_cost'].values

    # Total demand
    if isinstance(zone_loads, dict):
        total_demand = sum(zone_loads.values())
    else:
        total_demand = sum(zone_loads)

    # Equality: Σ g_i = total_demand
    A_eq = np.zeros((1, n_var))
    A_eq[0, :n_gen] = 1.0
    b_eq = np.array([total_demand])

    # Inequality constraints (A_ub x <= b_ub):
    # Block 1: Capacity         g_i + r_i <= max_p_i           [n_gen rows]
    # Block 2: Zonal reserve    -Σ_{G_z} r_i <= -R_z^min      [n_zones rows]
    # Block 3: Upper transfer   Σ_{G_z} g_i <= D_z + T_z - R_z [n_zones rows]
    # Block 4: Lower transfer  -Σ_{G_z} g_i <= -D_z + T_z - R_z [n_zones rows]
    n_ub = n_gen + 3 * n_zones
    A_ub = np.zeros((n_ub, n_var))
    b_ub = np.zeros(n_ub)

    # Block 1: Capacity
    for i in range(n_gen):
        A_ub[i, i] = 1.0
        A_ub[i, n_gen + i] = 1.0
        b_ub[i] = gen_data.iloc[i]['max_p_mw']

    # Block 2: Zonal reserve (negated for ≤ form)
    for z_idx in range(n_zones):
        z_id = z_idx + 1
        row = n_gen + z_idx
        if z_id in zone_gens:
            for gen_idx in zone_gens[z_id]:
                A_ub[row, n_gen + gen_idx] = -1.0
        b_ub[row] = -R_z_min[z_idx]

    # Block 3: Upper transfer
    for z_idx in range(n_zones):
        z_id = z_idx + 1
        row = n_gen + n_zones + z_idx
        D_z = zone_loads[z_id] if isinstance(zone_loads, dict) else zone_loads[z_idx]
        if z_id in zone_gens:
            for gen_idx in zone_gens[z_id]:
                A_ub[row, gen_idx] = 1.0
        b_ub[row] = D_z + T_z_max[z_idx] - R_z_min[z_idx]

    # Block 4: Lower transfer
    for z_idx in range(n_zones):
        z_id = z_idx + 1
        row = n_gen + 2 * n_zones + z_idx
        D_z = zone_loads[z_id] if isinstance(zone_loads, dict) else zone_loads[z_idx]
        if z_id in zone_gens:
            for gen_idx in zone_gens[z_id]:
                A_ub[row, gen_idx] = -1.0
        b_ub[row] = -D_z + T_z_max[z_idx] - R_z_min[z_idx]

    # Bounds
    bounds = []
    for i in range(n_gen):
        bounds.append((gen_data.iloc[i]['min_p_mw'], None))
    for i in range(n_gen):
        bounds.append((0.0, None))

    # Solve
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=bounds, method='highs')

    if not res.success:
        return {
            'cost': np.inf,
            'g': np.zeros(n_gen),
            'r': np.zeros(n_gen),
            'mu_z': np.zeros(n_zones),
            'lambda_z': np.zeros(n_zones),
            'feasible': False,
        }

    g_opt = res.x[:n_gen]
    r_opt = res.x[n_gen:]

    # Cost decomposition
    energy_cost = float(np.dot(gen_data['cost_c1'].values, g_opt))
    reserve_cost = float(np.dot(gen_data['reserve_cost'].values, r_opt))

    # Extract duals from HiGHS (ineqlin.marginals, non-positive for ≤)
    mu_z = np.zeros(n_zones)
    lambda_z = np.zeros(n_zones)

    if hasattr(res, 'ineqlin') and res.ineqlin is not None:
        ub_duals = res.ineqlin.marginals
        # Block 2: reserve duals (rows n_gen to n_gen + n_zones)
        mu_z = -ub_duals[n_gen:n_gen + n_zones]
        # Block 3: upper transfer duals
        lambda_upper = -ub_duals[n_gen + n_zones:n_gen + 2 * n_zones]
        # Block 4: lower transfer duals
        lambda_lower = -ub_duals[n_gen + 2 * n_zones:n_gen + 3 * n_zones]
        # Combined transfer dual
        lambda_z = lambda_upper + lambda_lower

    return {
        'cost': res.fun,
        'energy_cost': energy_cost,
        'reserve_cost': reserve_cost,
        'g': g_opt,
        'r': r_opt,
        'mu_z': mu_z,
        'lambda_z': lambda_z,
        'feasible': True,
    }
