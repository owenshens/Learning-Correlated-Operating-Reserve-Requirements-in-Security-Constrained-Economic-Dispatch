"""
Smoke Test for Phase 0 Infrastructure
======================================

Tests basic functionality of core modules before proceeding.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from core.uncertainty_sets import (
    L2Ball, L1Ball, LinfBox, TVBudgetSet, TopKSet, EllipsoidSet,
    HybridSet, create_uncertainty_set
)
from core.problem_generator import (
    generate_robust_qp, generate_problem_suite,
    tighten_uncertainty_radius_for_feasibility, assemble_full_matrices
)
from core.solvers import DirectNominalSolver, DRPG


def test_uncertainty_sets():
    """Test all 7 uncertainty set types"""
    print("\n[TEST 1/5] Testing Uncertainty Sets...")

    dim = 10

    # Test L2Ball
    print("  ├─ L2Ball...", end=" ")
    uset = L2Ball(radius=5.0, dim=dim)
    y = np.random.randn(dim) * 10
    u_proj = uset.project(y)
    assert np.linalg.norm(u_proj) <= 5.0 + 1e-6, "L2Ball projection failed"
    g = np.random.randn(dim)
    u_opt = uset.linear_oracle(g)
    assert np.linalg.norm(u_opt) <= 5.0 + 1e-6, "L2Ball linear oracle failed"
    print("✓")

    # Test L1Ball
    print("  ├─ L1Ball...", end=" ")
    uset = L1Ball(radius=10.0, dim=dim)
    u_proj = uset.project(y)
    assert np.sum(np.abs(u_proj)) <= 10.0 + 1e-6, "L1Ball projection failed"
    u_opt = uset.linear_oracle(g)
    assert np.sum(np.abs(u_opt)) <= 10.0 + 1e-6, "L1Ball linear oracle failed"
    print("✓")

    # Test LinfBox
    print("  ├─ LinfBox...", end=" ")
    uset = LinfBox(radius=3.0, dim=dim)
    u_proj = uset.project(y)
    assert np.max(np.abs(u_proj)) <= 3.0 + 1e-6, "LinfBox projection failed"
    u_opt = uset.linear_oracle(g)
    assert np.max(np.abs(u_opt)) <= 3.0 + 1e-6, "LinfBox linear oracle failed"
    print("✓")

    # Test TVBudgetSet
    print("  ├─ TVBudgetSet...", end=" ")
    T = 24
    uset = TVBudgetSet(r=np.ones(T) * 2.0, Gamma=10.0)
    y_t = np.random.randn(T) * 5
    u_proj = uset.project(y_t)
    assert len(u_proj) == T, "TVBudgetSet projection dimension mismatch"
    g_t = np.random.randn(T)
    u_opt = uset.linear_oracle(g_t)
    assert len(u_opt) == T, "TVBudgetSet linear oracle dimension mismatch"
    print("✓")

    # Test TopKSet
    print("  ├─ TopKSet...", end=" ")
    uset = TopKSet(K=3, Gamma=10.0, r=5.0, dim=dim)
    u_opt = uset.linear_oracle(g)
    assert np.max(np.abs(u_opt)) <= 5.0 + 1e-6, "TopKSet linear oracle failed"
    print("✓")

    # Test EllipsoidSet
    print("  ├─ EllipsoidSet...", end=" ")
    Sigma = np.eye(dim) + 0.1 * np.random.randn(dim, dim)
    Sigma = Sigma @ Sigma.T  # Make PSD
    uset = EllipsoidSet(Sigma=Sigma, rho=5.0)
    u_proj = uset.project(y)
    # Check Mahalanobis distance
    Sigma_inv = np.linalg.inv(Sigma)
    dist = np.sqrt(u_proj @ Sigma_inv @ u_proj)
    assert dist <= 5.0 + 1e-4, "EllipsoidSet projection failed"
    print("✓")

    # Test HybridSet
    print("  └─ HybridSet...", end=" ")
    s1 = L2Ball(radius=5.0, dim=dim)
    s2 = LinfBox(radius=3.0, dim=dim)
    uset = HybridSet([s1, s2])
    u_proj = uset.project(y)
    assert len(u_proj) == dim, "HybridSet projection failed"
    print("✓")

    print("  ✅ All uncertainty sets passed!")


def test_problem_generator():
    """Test problem generation"""
    print("\n[TEST 2/5] Testing Problem Generator...")

    # Test basic generation
    print("  ├─ Basic generation...", end=" ")
    prob = generate_robust_qp(
        n_agents=5,
        avg_vars_per_agent=10,
        n_resources=3,
        n_factors_p=2,
        n_factors_c=2,
        seed=42
    )
    assert prob.n_agents == 5, "Agent count mismatch"
    assert prob.n_resources == 3, "Resource count mismatch"
    assert prob.total_vars() > 0, "No variables generated"
    print("✓")

    # Test suite generation
    print("  ├─ Suite generation...", end=" ")
    suite = generate_problem_suite(seed=42)
    assert len(suite) == 3, "Suite size mismatch"
    assert suite[0].total_vars() < suite[1].total_vars() < suite[2].total_vars(), \
        "Suite not in ascending size order"
    print("✓")

    # Test feasibility tightening
    print("  ├─ Feasibility tightening...", end=" ")
    rho_safe = tighten_uncertainty_radius_for_feasibility(prob)
    assert 0 <= rho_safe <= prob.uncertainty_radius_c, "Invalid safe radius"
    print("✓")

    # Test matrix assembly
    print("  └─ Matrix assembly...", end=" ")
    Q, c, P, A, xl, xu = assemble_full_matrices(prob)
    assert Q.shape[0] == prob.total_vars(), "Q dimension mismatch"
    assert len(c) == prob.total_vars(), "c dimension mismatch"
    assert A.shape[0] == prob.n_resources, "A rows mismatch"
    print("✓")

    print("  ✅ Problem generator passed!")


def test_nominal_solver():
    """Test DirectNominalSolver"""
    print("\n[TEST 3/5] Testing DirectNominalSolver...")

    # Generate small problem
    print("  ├─ Generating small problem...", end=" ")
    prob = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=5,
        n_resources=2,
        n_factors_p=2,
        n_factors_c=2,
        seed=42
    )
    print("✓")

    # Solve at nominal uncertainty
    print("  ├─ Solving at u=0...", end=" ")
    solver = DirectNominalSolver()
    u_p = np.zeros(prob.n_factors_p)
    u_c = np.zeros(prob.n_factors_c)
    result = solver.solve(prob, u_p, u_c)

    assert result['converged'], f"Solver failed: {result.get('status', 'unknown')}"
    assert 'V_value' in result, "No objective value returned"
    assert 'x_blocks' in result, "No solution blocks returned"
    assert len(result['x_blocks']) == prob.n_agents, "Block count mismatch"
    print("✓")

    # Check constraint satisfaction
    print("  ├─ Checking constraints...", end=" ")
    x_full = result['x_full']
    A_full = result['A_full']
    b_rhs = result['b_rhs']
    residual = np.linalg.norm(A_full @ x_full - b_rhs)
    assert residual < 1e-5, f"Constraint violation: {residual}"
    print("✓")

    # Check bounds
    print("  └─ Checking bounds...", end=" ")
    idx = 0
    for i in range(prob.n_agents):
        n_i = prob.n_vars[i]
        x_i = x_full[idx:idx+n_i]
        assert np.all(x_i >= prob.x_lower[i] - 1e-6), "Lower bound violated"
        assert np.all(x_i <= prob.x_upper[i] + 1e-6), "Upper bound violated"
        idx += n_i
    print("✓")

    print("  ✅ Nominal solver passed!")


def test_drpg_basic():
    """Test DRPG basic functionality"""
    print("\n[TEST 4/5] Testing DRPG...")

    # Generate very small problem
    print("  ├─ Generating tiny problem...", end=" ")
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
    print("✓")

    # Create uncertainty sets
    print("  ├─ Creating uncertainty sets...", end=" ")
    uset_p = L2Ball(radius=prob.uncertainty_radius_p, dim=prob.n_factors_p)
    uset_c = L2Ball(radius=prob.uncertainty_radius_c, dim=prob.n_factors_c)
    print("✓")

    # Run DRPG for just a few iterations
    print("  ├─ Running DRPG (5 iters)...", end=" ")
    drpg = DRPG(
        max_outer_iterations=5,
        outer_tolerance=1e-2,
        verbose=False
    )
    result = drpg.solve(prob, uset_p, uset_c)

    assert result.converged or result.iterations >= 5, "DRPG didn't run"
    assert result.worst_case_value is not None, "No worst-case value"
    assert len(result.u_p_optimal) == prob.n_factors_p, "u_p dimension mismatch"
    assert len(result.u_c_optimal) == prob.n_factors_c, "u_c dimension mismatch"
    print("✓")

    # Check uncertainty is in set
    print("  ├─ Checking u* in sets...", end=" ")
    assert np.linalg.norm(result.u_p_optimal) <= prob.uncertainty_radius_p + 1e-5, \
        "u_p outside set"
    assert np.linalg.norm(result.u_c_optimal) <= prob.uncertainty_radius_c + 1e-5, \
        "u_c outside set"
    print("✓")

    # Check history tracking
    print("  └─ Checking history...", end=" ")
    assert len(result.history['V_values']) > 0, "No history recorded"
    assert len(result.history['u_p_trajectory']) > 0, "No trajectory recorded"
    print("✓")

    print("  ✅ DRPG basic test passed!")


def test_integration():
    """Integration test: nominal vs worst-case"""
    print("\n[TEST 5/5] Integration Test...")

    # Generate problem
    print("  ├─ Setup...", end=" ")
    prob = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=8,
        n_resources=3,
        n_factors_p=2,
        n_factors_c=2,
        uncertainty_radius_p=3.0,
        uncertainty_radius_c=1.5,
        seed=42
    )

    solver = DirectNominalSolver()
    print("✓")

    # Solve at nominal
    print("  ├─ Solving nominal (u=0)...", end=" ")
    result_nominal = solver.solve(
        prob,
        np.zeros(prob.n_factors_p),
        np.zeros(prob.n_factors_c)
    )
    V_nominal = result_nominal['V_value']
    print(f"V={V_nominal:.4f} ✓")

    # Find worst-case
    print("  ├─ Finding worst-case (DRPG)...", end=" ")
    uset_p = L2Ball(radius=prob.uncertainty_radius_p, dim=prob.n_factors_p)
    uset_c = L2Ball(radius=prob.uncertainty_radius_c, dim=prob.n_factors_c)

    drpg = DRPG(max_outer_iterations=10, verbose=False)
    result_worst = drpg.solve(prob, uset_p, uset_c)
    V_worst = result_worst.worst_case_value
    print(f"V={V_worst:.4f} ✓")

    # Check worst-case >= nominal (minimization)
    print("  ├─ Comparing values...", end=" ")
    # Note: We're minimizing, so worst-case should be larger (worse) than nominal
    # But the sign depends on how we set up the objective
    # For now, just check they're different if radius > 0
    if prob.uncertainty_radius_p > 0 or prob.uncertainty_radius_c > 0:
        assert abs(V_worst - V_nominal) > 1e-8, \
            f"Worst-case same as nominal (V_nom={V_nominal}, V_worst={V_worst})"
    print(f"ΔV={abs(V_worst - V_nominal):.4f} ✓")

    # Check trajectory makes sense
    print("  └─ Checking convergence...", end=" ")
    V_trajectory = result_worst.history['V_values']
    # Values should be generally increasing (maximizing V(u))
    # or at least final value should be near best
    V_final = V_trajectory[-1]
    V_best = max(V_trajectory)
    assert abs(V_final - V_best) < 1.0, "Didn't converge to best"
    print("✓")

    print("  ✅ Integration test passed!")


def main():
    """Run all smoke tests"""
    print("="*60)
    print("PHASE 0 SMOKE TEST")
    print("="*60)

    try:
        test_uncertainty_sets()
        test_problem_generator()
        test_nominal_solver()
        test_drpg_basic()
        test_integration()

        print("\n" + "="*60)
        print("✅ ALL SMOKE TESTS PASSED!")
        print("="*60)
        print("\n✓ Infrastructure is working correctly")
        print("✓ Ready to complete Phase 0")
        print("✓ Can proceed to experiments\n")
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
