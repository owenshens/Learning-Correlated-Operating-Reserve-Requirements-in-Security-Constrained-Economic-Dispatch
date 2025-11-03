"""
Run Detailed DRPG with Full Trajectory Logging
===============================================

Generate ONE representative problem with full iteration history
for pricing attack visualization and convergence plots.
"""

import numpy as np
import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.problem_generator import generate_robust_qp
from core.uncertainty_sets import L2Ball
from core.solvers import DRPG, DirectNominalSolver

# Configuration
np.random.seed(42)

# Problem size (representative)
N_AGENTS = 5
N_RESOURCES = 2
N_FACTORS_P = 3
N_FACTORS_C = 2

# Uncertainty (industry-calibrated)
RHO_P = 0.15  # 3× typical 5% forecast error
RHO_C = 0.10  # NERC N-1 contingency level

print("="*70)
print("DETAILED DRPG EXECUTION FOR VISUALIZATION")
print("="*70)

# Generate problem
print("\n1. Generating problem...")
problem = generate_robust_qp(
    n_agents=N_AGENTS,
    avg_vars_per_agent=10,
    n_resources=N_RESOURCES,
    n_factors_p=N_FACTORS_P,
    n_factors_c=N_FACTORS_C,
    uncertainty_radius_p=RHO_P,
    uncertainty_radius_c=RHO_C,
    seed=42
)
print(f"   ✓ Problem: {N_AGENTS} agents, {problem.total_vars()} variables")

# Create uncertainty sets (separate for u_p and u_c)
print("\n2. Creating uncertainty sets...")
u_set_p = L2Ball(dim=N_FACTORS_P, radius=RHO_P)
u_set_c = L2Ball(dim=N_FACTORS_C, radius=RHO_C)
print(f"   ✓ L2Ball: ρ_p={RHO_P}, ρ_c={RHO_C}")

# Solve nominal (u=0)
print("\n3. Solving nominal (u=0)...")
nominal_solver = DirectNominalSolver()
u_p_nom = np.zeros(N_FACTORS_P)
u_c_nom = np.zeros(N_FACTORS_C)
nominal_result = nominal_solver.solve(problem, u_p_nom, u_c_nom)
print(f"   ✓ Nominal cost: ${-nominal_result['V_value']:.2f}")
print(f"   ✓ LMP range: ${nominal_result['lambda'].min():.2f} - ${nominal_result['lambda'].max():.2f}")

# Solve DRPG with detailed tracking
print("\n4. Solving DRPG (stress search)...")
drpg_solver = DRPG(
    max_outer_iterations=100,
    outer_tolerance=1e-4,
    inner_tolerance=1e-3,
    verbose=True
)

drpg_result = drpg_solver.solve(problem, u_set_p, u_set_c)

print(f"\n   ✓ Converged: {drpg_result.converged}")
print(f"   ✓ Worst-case cost: ${drpg_result.worst_case_value:.2f}")
print(f"   ✓ Outer iterations: {drpg_result.outer_iterations}")
print(f"   ✓ Total inner iterations: {drpg_result.total_inner_iterations}")

# Extract and save detailed history
print("\n5. Extracting trajectory data...")
history = drpg_result.history

trajectory_data = {
    'problem_config': {
        'n_agents': N_AGENTS,
        'n_resources': N_RESOURCES,
        'n_factors_p': N_FACTORS_P,
        'n_factors_c': N_FACTORS_C,
        'rho_p': RHO_P,
        'rho_c': RHO_C
    },
    'nominal': {
        'objective': float(-nominal_result['V_value']),  # Negate because we're maximizing
        'lmps': nominal_result['lambda'].tolist(),
        'u_p': u_p_nom.tolist(),
        'u_c': u_c_nom.tolist()
    },
    'drpg': {
        'converged': drpg_result.converged,
        'worst_case_value': float(drpg_result.worst_case_value),
        'outer_iterations': drpg_result.outer_iterations,
        'total_inner_iterations': drpg_result.total_inner_iterations,
        'final_u_p': drpg_result.u_p_optimal.tolist(),
        'final_u_c': drpg_result.u_c_optimal.tolist(),
        'final_lmps': drpg_result.lambda_optimal.tolist()
    },
    'trajectory': {
        'V_values': [float(v) for v in history['V_values']],
        'gradient_norms_p': [float(g) for g in history['gradient_norms_p']],
        'gradient_norms_c': [float(g) for g in history['gradient_norms_c']],
        'u_p_trajectory': [up.tolist() for up in history['u_p_trajectory']],
        'u_c_trajectory': [uc.tolist() for uc in history['u_c_trajectory']],
        'lambda_trajectory': [lam.tolist() for lam in history['lambda_trajectory']]
    }
}

# Compute derived metrics
V_traj = np.array(history['V_values'])
lambda_traj = [np.array(lam) for lam in history['lambda_trajectory']]
price_spreads = [float(lam.max() - lam.min()) for lam in lambda_traj]
price_means = [float(lam.mean()) for lam in lambda_traj]

trajectory_data['trajectory']['price_spread'] = price_spreads
trajectory_data['trajectory']['price_mean'] = price_means

# Compute envelope gradients (P^T λ)
envelope_norms = []
for lam in lambda_traj:
    # In this simplified case, envelope grad ≈ lam projected onto uncertainty space
    # For full implementation, would need P matrix
    grad_norm = np.linalg.norm(lam)
    envelope_norms.append(float(grad_norm))

trajectory_data['trajectory']['envelope_gradient_norms'] = envelope_norms

# Save
output_file = Path(__file__).parent / "drpg_detailed_trajectory.json"
with open(output_file, 'w') as f:
    json.dump(trajectory_data, f, indent=2)

print(f"\n   ✓ Saved trajectory to: {output_file.name}")
print(f"   ✓ Trajectory length: {len(history['V_values'])} iterations")
print(f"   ✓ Final price spread: ${price_spreads[-1]:.2f}/MWh")
print(f"   ✓ Initial → Final cost: ${V_traj[0]:.2f} → ${V_traj[-1]:.2f}")
print(f"   ✓ Cost increase: {((V_traj[-1] - V_traj[0]) / V_traj[0] * 100):.3f}%")

print("\n" + "="*70)
print("DETAILED TRAJECTORY SAVED SUCCESSFULLY")
print("="*70)
print("\n📊 Use this data for:")
print("  - Figure 1: Pricing attack visualization")
print("  - Figure 6: Convergence trajectories")
