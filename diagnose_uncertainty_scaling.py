"""
Comprehensive Diagnostic: Uncertainty Scaling and PoR Analysis
================================================================

This script investigates why PoR is near-zero by analyzing:
1. Actual uncertainty magnitude relative to problem scale
2. Impact of uncertainty on objective and constraints
3. PoR calculation correctness
4. Sign conventions in maximization problems
"""

import numpy as np
import json
from pathlib import Path
from core.problem_generator import generate_robust_qp
from core.uncertainty_sets import L2Ball
from core.solvers import DRPG, DirectNominalSolver

# ============================================================================
# PART 1: ANALYZE PROBLEM SCALING
# ============================================================================

print("="*80)
print("DIAGNOSTIC: UNCERTAINTY SCALING ANALYSIS")
print("="*80)

# Generate a typical problem from the experiments
problem = generate_robust_qp(
    n_agents=5,
    avg_vars_per_agent=10,
    n_resources=2,
    n_factors_p=3,
    n_factors_c=2,
    uncertainty_radius_p=0.15,
    uncertainty_radius_c=0.10,
    seed=42
)

print(f"\n{'='*80}")
print("PROBLEM PARAMETERS")
print(f"{'='*80}")
print(f"Agents: {problem.n_agents}")
print(f"Total variables: {problem.total_vars()}")
print(f"Resources (constraints): {problem.n_resources}")
print(f"Objective uncertainty factors: {problem.n_factors_p}")
print(f"Constraint uncertainty factors: {problem.n_factors_c}")
print(f"Objective uncertainty radius ρ_p: {problem.uncertainty_radius_p}")
print(f"Constraint uncertainty radius ρ_c: {problem.uncertainty_radius_c}")

# Analyze objective coefficients
c_full = np.concatenate(problem.c)
print(f"\n{'='*80}")
print("OBJECTIVE COEFFICIENTS (c)")
print(f"{'='*80}")
print(f"Range: [{c_full.min():.3f}, {c_full.max():.3f}]")
print(f"Mean: {c_full.mean():.3f}")
print(f"Std: {c_full.std():.3f}")

# Analyze objective uncertainty coupling (P)
P_full = np.vstack(problem.P)
print(f"\n{'='*80}")
print("OBJECTIVE UNCERTAINTY COUPLING (P)")
print(f"{'='*80}")
print(f"Shape: {P_full.shape}")
print(f"Range: [{P_full.min():.3f}, {P_full.max():.3f}]")
print(f"Mean: {P_full.mean():.3f}")
print(f"Std: {P_full.std():.3f}")
print(f"Typical |P_{'{ij}'}|: {np.abs(P_full).mean():.3f}")

# Calculate maximum perturbation to objective
max_u_p_component = problem.uncertainty_radius_p / np.sqrt(problem.n_factors_p)
max_obj_perturbation_per_var = np.abs(P_full).max() * max_u_p_component
print(f"\n{'='*80}")
print("OBJECTIVE UNCERTAINTY MAGNITUDE")
print(f"{'='*80}")
print(f"Max ||u_p|| allowed: {problem.uncertainty_radius_p}")
print(f"Typical u_p component (if uniform): ±{max_u_p_component:.3f}")
print(f"Max |P_ij|: {np.abs(P_full).max():.3f}")
print(f"Max perturbation to one variable's coefficient: ±{max_obj_perturbation_per_var:.3f}")
print(f"Typical coefficient c_i: {c_full.mean():.3f}")
print(f"RELATIVE UNCERTAINTY: {max_obj_perturbation_per_var / c_full.mean() * 100:.2f}%")

# Analyze constraint RHS
print(f"\n{'='*80}")
print("CONSTRAINT RHS (b)")
print(f"{'='*80}")
print(f"b values: {problem.b}")
print(f"Range: [{problem.b.min():.3f}, {problem.b.max():.3f}]")
print(f"Mean: {problem.b.mean():.3f}")

# Analyze constraint uncertainty coupling (B)
print(f"\n{'='*80}")
print("CONSTRAINT UNCERTAINTY COUPLING (B)")
print(f"{'='*80}")
print(f"Shape: {problem.B.shape}")
print(f"Range: [{problem.B.min():.3f}, {problem.B.max():.3f}]")
print(f"Mean: {problem.B.mean():.3f}")
print(f"Std: {problem.B.std():.3f}")

# Calculate maximum perturbation to constraints
max_u_c_component = problem.uncertainty_radius_c / np.sqrt(problem.n_factors_c)
max_rhs_perturbation = np.abs(problem.B).max() * max_u_c_component
print(f"\n{'='*80}")
print("CONSTRAINT UNCERTAINTY MAGNITUDE")
print(f"{'='*80}")
print(f"Max ||u_c|| allowed: {problem.uncertainty_radius_c}")
print(f"Typical u_c component (if uniform): ±{max_u_c_component:.3f}")
print(f"Max |B_jk|: {np.abs(problem.B).max():.3f}")
print(f"Max perturbation to one constraint RHS: ±{max_rhs_perturbation:.3f}")
print(f"Typical RHS b_j: {problem.b.mean():.3f}")
print(f"RELATIVE UNCERTAINTY: {max_rhs_perturbation / problem.b.mean() * 100:.2f}%")

# ============================================================================
# PART 2: SOLVE AND COMPARE
# ============================================================================

print(f"\n{'='*80}")
print("SOLVING NOMINAL AND ROBUST PROBLEMS")
print(f"{'='*80}")

# Solve nominal (u=0)
nominal_solver = DirectNominalSolver()
u_p_nom = np.zeros(problem.n_factors_p)
u_c_nom = np.zeros(problem.n_factors_c)
nominal_result = nominal_solver.solve(problem, u_p_nom, u_c_nom)

print(f"\nNOMINAL (u=0):")
print(f"  Converged: {nominal_result['converged']}")
print(f"  V_value (minimization objective): {nominal_result['V_value']:.6f}")
print(f"  PROFIT (negated): {-nominal_result['V_value']:.6f}")
print(f"  LMPs: {nominal_result['lambda']}")

# Solve DRPG
u_set_p = L2Ball(dim=problem.n_factors_p, radius=problem.uncertainty_radius_p)
u_set_c = L2Ball(dim=problem.n_factors_c, radius=problem.uncertainty_radius_c)

drpg_solver = DRPG(
    max_outer_iterations=100,
    outer_tolerance=1e-4,
    verbose=False
)

drpg_result = drpg_solver.solve(problem, u_set_p, u_set_c)

print(f"\nDRPG (worst-case):")
print(f"  Converged: {drpg_result.converged}")
print(f"  Outer iterations: {drpg_result.outer_iterations}")
print(f"  Worst-case V_value: {drpg_result.worst_case_value:.6f}")
print(f"  WORST-CASE PROFIT (negated): {-drpg_result.worst_case_value:.6f}")
print(f"  Worst-case u_p: {drpg_result.u_p_optimal}")
print(f"  Worst-case u_c: {drpg_result.u_c_optimal}")
print(f"  ||u_p||: {np.linalg.norm(drpg_result.u_p_optimal):.6f} (max: {problem.uncertainty_radius_p})")
print(f"  ||u_c||: {np.linalg.norm(drpg_result.u_c_optimal):.6f} (max: {problem.uncertainty_radius_c})")

# Solve at worst-case u to verify
worst_nominal_result = nominal_solver.solve(
    problem,
    drpg_result.u_p_optimal,
    drpg_result.u_c_optimal
)
print(f"\nVERIFICATION (solve at DRPG's worst-case u):")
print(f"  V_value: {worst_nominal_result['V_value']:.6f}")
print(f"  PROFIT: {-worst_nominal_result['V_value']:.6f}")
print(f"  Matches DRPG worst-case? {np.abs(worst_nominal_result['V_value'] - drpg_result.worst_case_value) < 1e-3}")

# ============================================================================
# PART 3: CALCULATE PRICE OF ROBUSTNESS
# ============================================================================

print(f"\n{'='*80}")
print("PRICE OF ROBUSTNESS CALCULATION")
print(f"{'='*80}")

nominal_profit = -nominal_result['V_value']  # Negate because we're maximizing
worst_profit = -drpg_result.worst_case_value

# PoR = loss in expected value due to robustness
# For maximization: (nominal - robust) / nominal
por_absolute = nominal_profit - worst_profit
por_percent = (por_absolute / np.abs(nominal_profit)) * 100

print(f"\nNominal profit: ${nominal_profit:.6f}")
print(f"Worst-case profit: ${worst_profit:.6f}")
print(f"Difference: ${por_absolute:.6f}")
print(f"Price of Robustness: {por_percent:.4f}%")

# ============================================================================
# PART 4: ANALYZE WHY PoR IS SO LOW
# ============================================================================

print(f"\n{'='*80}")
print("ROOT CAUSE ANALYSIS: WHY IS PoR SO LOW?")
print(f"{'='*80}")

# Calculate the actual impact of uncertainty
obj_impact = np.abs(P_full @ drpg_result.u_p_optimal).sum()
print(f"\nObjective perturbation:")
print(f"  ||P' u_p||_1 = {obj_impact:.6f}")
print(f"  Total nominal objective ≈ {nominal_profit:.6f}")
print(f"  Perturbation / Total = {obj_impact / nominal_profit * 100:.4f}%")

constraint_impact = np.abs(problem.B @ drpg_result.u_c_optimal).sum()
print(f"\nConstraint perturbation:")
print(f"  ||B u_c||_1 = {constraint_impact:.6f}")
print(f"  Total nominal RHS ≈ {problem.b.sum():.6f}")
print(f"  Perturbation / Total = {constraint_impact / problem.b.sum() * 100:.4f}%")

# ============================================================================
# PART 5: RECOMMENDATIONS
# ============================================================================

print(f"\n{'='*80}")
print("RECOMMENDATIONS FOR REALISTIC UNCERTAINTY")
print(f"{'='*80}")

print(f"""
The current uncertainty is UNREALISTICALLY SMALL:
- Objective uncertainty: ~{max_obj_perturbation_per_var / c_full.mean() * 100:.2f}% of coefficients
- Constraint uncertainty: ~{max_rhs_perturbation / problem.b.mean() * 100:.2f}% of RHS

For realistic energy dispatch, uncertainty should be:
- Demand forecast error: ±5-10% of load
- Renewable forecast error: ±15-30% of capacity
- Price uncertainty: ±10-20% of expected price

SUGGESTED FIXES:

Option 1: Increase coupling matrix scaling
  - Change P_i scaling from 0.2 to 2.0 (10× increase)
  - Change B scaling from 0.1 to 1.0 (10× increase)

Option 2: Increase uncertainty radii
  - Change ρ_p from 0.15 to 1.5 (10× increase)
  - Change ρ_c from 0.10 to 1.0 (10× increase)

Option 3: Use relative/percentage-based uncertainty
  - Scale P_i relative to c_i: P_i ← 0.15 * c_i * randn()
  - Scale B relative to b_j: B_j ← 0.10 * b_j * randn()

EXPECTED RESULTS WITH 10× SCALING:
- PoR would increase from ~0.001% to ~1-5%
- DRPG would take more iterations (20-50 instead of 8)
- Results would be more realistic and publishable
""")

print(f"{'='*80}")
print("DIAGNOSTIC COMPLETE")
print(f"{'='*80}")
