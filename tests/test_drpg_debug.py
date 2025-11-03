"""
Debug DRPG test - verbose output to diagnose issue
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from core.uncertainty_sets import L2Ball
from core.problem_generator import generate_robust_qp
from core.solvers import DirectNominalSolver, DRPG

print("\n" + "="*60)
print("DRPG DEBUG TEST")
print("="*60)

# Generate very small problem
print("\n[1] Generating tiny problem...")
prob = generate_robust_qp(
    n_agents=2,
    avg_vars_per_agent=5,
    n_resources=2,
    n_factors_p=2,
    n_factors_c=2,
    uncertainty_radius_p=2.0,
    uncertainty_radius_c=1.0,
    seed=42
)
print(f"  Problem size: {prob.n_agents} agents, {prob.total_vars()} vars, {prob.n_resources} resources")
print(f"  Uncertainty: p={prob.n_factors_p}, c={prob.n_factors_c}")

# Test nominal solver first
print("\n[2] Testing nominal solver at u=0...")
solver = DirectNominalSolver()
u_p = np.zeros(prob.n_factors_p)
u_c = np.zeros(prob.n_factors_c)

result = solver.solve(prob, u_p, u_c)
print(f"  Converged: {result.get('converged', False)}")
print(f"  Status: {result.get('status', 'unknown')}")
if result.get('converged'):
    print(f"  V_value: {result['V_value']:.6f}")

# Create uncertainty sets
print("\n[3] Creating uncertainty sets...")
uset_p = L2Ball(radius=prob.uncertainty_radius_p, dim=prob.n_factors_p)
uset_c = L2Ball(radius=prob.uncertainty_radius_c, dim=prob.n_factors_c)
print(f"  U_p: L2Ball(r={prob.uncertainty_radius_p})")
print(f"  U_c: L2Ball(r={prob.uncertainty_radius_c})")

# Run DRPG with verbose=True
print("\n[4] Running DRPG (5 iters, VERBOSE)...")
drpg = DRPG(
    max_outer_iterations=5,
    outer_tolerance=1e-2,
    verbose=True  # Enable verbose output
)

result = drpg.solve(prob, uset_p, uset_c)

print("\n[5] DRPG Result:")
print(f"  Converged: {result.converged}")
print(f"  Iterations: {result.iterations}")
print(f"  Worst-case value: {result.worst_case_value}")
print(f"  ||u_p*||: {np.linalg.norm(result.u_p_optimal):.4f}")
print(f"  ||u_c*||: {np.linalg.norm(result.u_c_optimal):.4f}")

print("\n" + "="*60)
if result.converged or result.iterations >= 5:
    print("✅ DRPG ran successfully!")
else:
    print(f"❌ DRPG failed: only {result.iterations} iterations")
print("="*60)
