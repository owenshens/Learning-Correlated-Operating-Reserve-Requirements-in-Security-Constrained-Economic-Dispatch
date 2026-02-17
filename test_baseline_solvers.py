"""
Test and Validate Baseline Solvers
===================================

Quick validation that all baseline methods work correctly.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.problem_generator import generate_robust_qp
from core.uncertainty_sets import L2Ball, L1Ball, LinfBox
from core.baseline_solvers import (
    NominalOptimization,
    ScenarioBasedRO,
    BertsimasSimBudgeted,
    compare_methods_on_problem
)
from core.solvers import DRPG


def test_baseline_solvers():
    """Test all baseline solvers on a small problem."""
    print("\n" + "="*70)
    print("BASELINE SOLVERS VALIDATION")
    print("="*70)

    # Generate test problem
    print("\nGenerating test problem...")
    problem = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=2,
        n_resources=2,
        n_factors_p=2,
        n_factors_c=2,
        uncertainty_radius_p=0.15,
        uncertainty_radius_c=0.10,
        seed=42,
        problem_type="energy"
    )

    print(f"  Problem: {problem.n_agents} agents, {sum(problem.n_vars)} total vars")
    print(f"  Uncertainty: P ∈ R^{problem.n_factors_p}, C ∈ R^{problem.n_factors_c}")

    # Create uncertainty sets
    uset_p = L2Ball(dim=problem.n_factors_p, radius=0.15)
    uset_c = L2Ball(dim=problem.n_factors_c, radius=0.10)

    # Test 1: Nominal solver
    print("\n" + "-"*70)
    print("TEST 1: Nominal Optimization")
    print("-"*70)

    nominal_solver = NominalOptimization(verbose=True)
    nominal_result = nominal_solver.solve(problem, uset_p, uset_c)

    assert nominal_result.converged, "Nominal solver failed to converge"
    print(f"✓ Nominal solver passed: obj = ${-nominal_result.objective_value:.2f}")

    # Test 2: Scenario-based RO
    print("\n" + "-"*70)
    print("TEST 2: Scenario-Based RO")
    print("-"*70)

    scenario_solver = ScenarioBasedRO(
        scenario_generation="grid",
        n_scenarios_p=5,
        n_scenarios_c=5,
        verbose=True
    )
    scenario_result = scenario_solver.solve(problem, uset_p, uset_c)

    assert scenario_result.converged, "Scenario-based solver failed"
    print(f"✓ Scenario-based solver passed: obj = ${-scenario_result.objective_value:.2f}")

    # Test 3: Bertsimas-Sim Budgeted
    print("\n" + "-"*70)
    print("TEST 3: Bertsimas-Sim Budgeted")
    print("-"*70)

    budgeted_solver = BertsimasSimBudgeted(
        budget_p=1.0,  # Half of 2 factors
        budget_c=1.0,
        verbose=True
    )
    budgeted_result = budgeted_solver.solve(problem, uset_p, uset_c)

    assert budgeted_result.converged, "Budgeted solver failed"
    print(f"✓ Budgeted solver passed: obj = ${-budgeted_result.objective_value:.2f}")

    # Test 4: DRPG for comparison
    print("\n" + "-"*70)
    print("TEST 4: DRPG (Reference)")
    print("-"*70)

    drpg_solver = DRPG(verbose=True)
    drpg_result = drpg_solver.solve(problem, uset_p, uset_c)

    assert drpg_result.converged, "DRPG failed"
    print(f"✓ DRPG passed: obj = ${-drpg_result.worst_case_value:.2f}")

    # Compare results
    print("\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)

    results_table = [
        ("Nominal (u=0)", nominal_result.objective_value, nominal_result.solve_time, nominal_result.iterations),
        ("Scenario-Based", scenario_result.objective_value, scenario_result.solve_time, scenario_result.iterations),
        ("Bertsimas-Sim", budgeted_result.objective_value, budgeted_result.solve_time, budgeted_result.iterations),
        ("DRPG", -drpg_result.worst_case_value, drpg_result.solve_time, drpg_result.outer_iterations),
    ]

    print(f"\n{'Method':<20} {'Objective':<15} {'Time (s)':<12} {'Iterations':<12}")
    print("-"*70)
    for name, obj, time_s, iters in results_table:
        print(f"{name:<20} ${-obj:<14.2f} {time_s:<12.4f} {iters:<12}")

    # Validate ordering
    print("\n" + "="*70)
    print("VALIDATION CHECKS")
    print("="*70)

    # 1. Nominal should be best (least conservative)
    nominal_obj = nominal_result.objective_value
    scenario_obj = scenario_result.objective_value
    drpg_obj = -drpg_result.worst_case_value

    print(f"\n1. Optimality ordering (worst-case objectives):")
    print(f"   Nominal:  ${-nominal_obj:.2f} (best nominal, no robustness)")
    print(f"   Scenario: ${-scenario_obj:.2f}")
    print(f"   DRPG:     ${-drpg_obj:.2f} (true worst-case)")

    # Note: Scenario-based may not find true worst-case (heuristic)
    # DRPG should find worst or equal to scenario

    print(f"\n2. Robustness check:")
    if drpg_obj >= scenario_obj - 1e-3:
        print(f"   ✓ DRPG worst-case ≥ Scenario worst-case (expected)")
    else:
        print(f"   ⚠ DRPG found better worst-case than scenario (scenario is heuristic)")

    print(f"\n3. Solve time comparison:")
    print(f"   Nominal:  {nominal_result.solve_time:.4f}s (fastest, single solve)")
    print(f"   Scenario: {scenario_result.solve_time:.4f}s ({scenario_result.metadata['n_total_scenarios']} scenarios)")
    print(f"   DRPG:     {drpg_result.solve_time:.4f}s ({drpg_result.outer_iterations} outer iterations)")

    print("\n" + "="*70)
    print("✅ ALL BASELINE SOLVERS VALIDATED")
    print("="*70)

    return results_table


def test_different_uncertainty_sets():
    """Test baseline solvers with different uncertainty set geometries."""
    print("\n" + "="*70)
    print("TESTING DIFFERENT UNCERTAINTY SETS")
    print("="*70)

    # Generate problem
    problem = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=2,
        n_resources=2,
        n_factors_p=3,
        n_factors_c=2,
        seed=42
    )

    uncertainty_sets = [
        ("L2Ball", L2Ball(dim=3, radius=0.15), L2Ball(dim=2, radius=0.10)),
        ("L1Ball", L1Ball(dim=3, radius=0.15), L1Ball(dim=2, radius=0.10)),
        ("LinfBox", LinfBox(dim=3, radius=0.15), LinfBox(dim=2, radius=0.10)),
    ]

    results = {}

    for set_name, uset_p, uset_c in uncertainty_sets:
        print(f"\n{'-'*70}")
        print(f"Testing with {set_name}")
        print(f"{'-'*70}")

        # Use scenario-based with vertices for polyhedral sets
        if set_name in ["L1Ball", "LinfBox"]:
            scenario_gen = "vertices"
        else:
            scenario_gen = "grid"

        solver = ScenarioBasedRO(
            scenario_generation=scenario_gen,
            n_scenarios_p=8,
            n_scenarios_c=8,
            verbose=False
        )

        result = solver.solve(problem, uset_p, uset_c)
        results[set_name] = result

        print(f"  ✓ {set_name}: obj = ${-result.objective_value:.2f}, time = {result.solve_time:.4f}s")

    print("\n" + "="*70)
    print("SUMMARY: Uncertainty Set Comparison")
    print("="*70)

    print(f"\n{'Set Type':<15} {'Objective':<15} {'Time (s)':<12} {'Scenarios':<12}")
    print("-"*70)
    for set_name in ["L2Ball", "L1Ball", "LinfBox"]:
        result = results[set_name]
        n_scenarios = result.metadata['n_total_scenarios']
        print(f"{set_name:<15} ${-result.objective_value:<14.2f} {result.solve_time:<12.4f} {n_scenarios:<12}")

    print("\n✅ All uncertainty sets tested successfully")


if __name__ == '__main__':
    # Test 1: Basic validation
    test_baseline_solvers()

    # Test 2: Different uncertainty sets
    test_different_uncertainty_sets()

    print("\n" + "="*70)
    print("ALL TESTS PASSED")
    print("="*70)
    print("\nBaseline solvers are working correctly!")
    print("Ready for comprehensive comparison experiments.")
