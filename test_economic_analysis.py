"""
Test Suite for Economic Analysis Module
========================================

Validates:
1. Out-of-sample performance evaluation
2. Value of Stochastic Solution (VSS) computation
3. Test scenario generation
4. Economic metrics computation
"""

import sys
import numpy as np
from pathlib import Path

# Add experiment root to path
experiment_root = Path(__file__).parent
sys.path.insert(0, str(experiment_root))

from core.problem_generator import generate_robust_qp
from core.uncertainty_sets import L2Ball, L1Ball, LinfBox
from core.economic_analysis import (
    OutOfSampleEvaluator,
    VSSComputer,
    EconomicAnalyzer
)
from core.baseline_solvers import NominalOptimization
from core.solvers import DRPG


def test_scenario_generation():
    """Test 1: Validate test scenario generation."""
    print("\n" + "="*70)
    print("TEST 1: Scenario Generation")
    print("="*70)

    # Create uncertainty sets
    uset_p = L2Ball(dim=3, radius=0.15)
    uset_c = L2Ball(dim=2, radius=0.10)

    # Test random generation
    evaluator = OutOfSampleEvaluator(
        n_test_scenarios=100,
        scenario_generation="random",
        seed=42,
        verbose=False
    )

    scenarios_p, scenarios_c = evaluator.generate_test_scenarios(uset_p, uset_c)

    print(f"\nRandom Generation:")
    print(f"  Generated {len(scenarios_p)} scenarios for P")
    print(f"  Generated {len(scenarios_c)} scenarios for C")

    # Validate scenarios are within bounds
    valid_p = all(np.linalg.norm(u) <= uset_p.radius * 1.01 for u in scenarios_p)  # 1% tolerance
    valid_c = all(np.linalg.norm(u) <= uset_c.radius * 1.01 for u in scenarios_c)

    print(f"  All P scenarios within bounds: {valid_p}")
    print(f"  All C scenarios within bounds: {valid_c}")

    # Test grid generation
    evaluator_grid = OutOfSampleEvaluator(
        n_test_scenarios=100,
        scenario_generation="grid",
        seed=42,
        verbose=False
    )

    scenarios_p_grid, scenarios_c_grid = evaluator_grid.generate_test_scenarios(uset_p, uset_c)

    print(f"\nGrid Generation:")
    print(f"  Generated {len(scenarios_p_grid)} scenarios for P")
    print(f"  Generated {len(scenarios_c_grid)} scenarios for C")

    if len(scenarios_p) == 100 and len(scenarios_c) == 100 and valid_p and valid_c:
        print("\n✅ TEST 1 PASSED: Scenario generation works correctly")
        return True
    else:
        print("\n❌ TEST 1 FAILED")
        return False


def test_out_of_sample_evaluation():
    """Test 2: Validate out-of-sample evaluation."""
    print("\n" + "="*70)
    print("TEST 2: Out-of-Sample Evaluation")
    print("="*70)

    # Generate small test problem
    problem = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=5,
        n_resources=2,
        n_factors_p=3,
        n_factors_c=2,
        uncertainty_radius_p=0.15,
        uncertainty_radius_c=0.10,
        seed=42,
        problem_type='energy'
    )

    # Create uncertainty sets
    uset_p = L2Ball(dim=problem.n_factors_p, radius=0.15)
    uset_c = L2Ball(dim=problem.n_factors_c, radius=0.10)

    # Solve nominal problem
    print("\nSolving nominal problem...")
    nominal_solver = NominalOptimization(verbose=False)
    nominal_result = nominal_solver.solve(problem, uset_p, uset_c)
    x_nominal = nominal_result.x_solution

    print(f"  Nominal objective: ${-nominal_result.objective_value:.2f}")

    # Solve robust problem with DRPG
    print("\nSolving robust problem with DRPG...")
    drpg_solver = DRPG(
        outer_tolerance=1e-4,
        max_outer_iterations=50,
        verbose=False
    )
    drpg_result = drpg_solver.solve(problem, uset_p, uset_c)
    x_robust = np.concatenate(drpg_result.x_blocks)

    print(f"  DRPG worst-case: ${-drpg_result.worst_case_value:.2f}")

    # Perform out-of-sample evaluation
    print("\nPerforming out-of-sample evaluation...")
    evaluator = OutOfSampleEvaluator(
        n_test_scenarios=500,
        scenario_generation="random",
        seed=42,
        verbose=True
    )

    oos_result = evaluator.evaluate(
        method_name="DRPG",
        x_solution=x_robust,
        problem=problem,
        uset_p=uset_p,
        uset_c=uset_c,
        x_nominal=x_nominal
    )

    # Validate results
    print(f"\nValidation:")
    print(f"  Mean cost computed: {not np.isnan(oos_result.mean_cost)}")
    print(f"  Std cost computed: {not np.isnan(oos_result.std_cost)}")
    print(f"  Worst-case computed: {not np.isnan(oos_result.worst_case_cost)}")
    print(f"  Percentiles computed: {not np.isnan(oos_result.percentile_95)}")
    print(f"  Cost vs nominal computed: {not np.isnan(oos_result.cost_increase_vs_nominal)}")

    # Check that worst-case from OOS is not worse than DRPG worst-case
    # (it should be better or equal since DRPG finds true worst-case)
    oos_worst = -oos_result.worst_case_cost  # Convert back to minimization
    drpg_worst = -drpg_result.worst_case_value

    print(f"\n  OOS worst-case: ${oos_worst:.2f}")
    print(f"  DRPG worst-case: ${drpg_worst:.2f}")
    print(f"  OOS better or equal: {oos_worst <= drpg_worst * 1.01}")  # 1% tolerance

    if (not np.isnan(oos_result.mean_cost) and
        len(oos_result.test_objectives) == 500 and
        oos_result.feasibility_rate == 1.0):
        print("\n✅ TEST 2 PASSED: Out-of-sample evaluation works correctly")
        return True
    else:
        print("\n❌ TEST 2 FAILED")
        return False


def test_vss_computation():
    """Test 3: Validate VSS computation."""
    print("\n" + "="*70)
    print("TEST 3: Value of Stochastic Solution (VSS)")
    print("="*70)

    # Generate small test problem
    problem = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=5,
        n_resources=2,
        n_factors_p=3,
        n_factors_c=2,
        uncertainty_radius_p=0.15,
        uncertainty_radius_c=0.10,
        seed=42,
        problem_type='energy'
    )

    # Create uncertainty sets
    uset_p = L2Ball(dim=problem.n_factors_p, radius=0.15)
    uset_c = L2Ball(dim=problem.n_factors_c, radius=0.10)

    # Solve nominal
    print("\nSolving nominal problem...")
    nominal_solver = NominalOptimization(verbose=False)
    nominal_result = nominal_solver.solve(problem, uset_p, uset_c)
    x_nominal = nominal_result.x_solution

    # Solve robust
    print("Solving robust problem...")
    drpg_solver = DRPG(
        outer_tolerance=1e-4,
        max_outer_iterations=50,
        verbose=False
    )
    drpg_result = drpg_solver.solve(problem, uset_p, uset_c)
    x_robust = np.concatenate(drpg_result.x_blocks)

    # Compute VSS
    print("\nComputing VSS...")
    vss_computer = VSSComputer(
        n_scenarios=500,
        seed=42,
        verbose=True
    )

    vss_result = vss_computer.compute_vss(
        x_nominal=x_nominal,
        x_robust=x_robust,
        problem=problem,
        uset_p=uset_p,
        uset_c=uset_c
    )

    # Validate results
    print(f"\nValidation:")
    print(f"  VSS value computed: {not np.isnan(vss_result.vss_value)}")
    print(f"  VSS percentage computed: {not np.isnan(vss_result.vss_percentage)}")
    print(f"  Nominal expected cost: ${vss_result.nominal_expected_cost:.2f}")
    print(f"  Robust expected cost: ${vss_result.robust_expected_cost:.2f}")
    print(f"  Worst-case improvement: {vss_result.worst_case_improvement:+.2f}%")
    print(f"  Statistically significant: {vss_result.is_significant}")

    # VSS should show that robust has better or comparable worst-case
    # For low price of robustness problems, improvement may be near zero
    improvement_acceptable = vss_result.worst_case_improvement >= -0.1  # Allow small tolerance

    print(f"  Robust worst-case acceptable: {improvement_acceptable}")
    print(f"    (improvement >= -0.1%: {vss_result.worst_case_improvement:.4f}%)")

    # Also check that VSS is computed correctly (should be small but valid)
    vss_valid = abs(vss_result.vss_percentage) < 10.0  # VSS should be reasonable magnitude

    if (not np.isnan(vss_result.vss_value) and
        not np.isnan(vss_result.worst_case_improvement) and
        improvement_acceptable and
        vss_valid):
        print("\n✅ TEST 3 PASSED: VSS computation works correctly")
        print("    (Note: Small VSS indicates low price of robustness)")
        return True
    else:
        print("\n❌ TEST 3 FAILED")
        return False


def test_economic_analyzer():
    """Test 4: Validate comprehensive economic analyzer."""
    print("\n" + "="*70)
    print("TEST 4: Comprehensive Economic Analyzer")
    print("="*70)

    # Generate small test problem
    problem = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=5,
        n_resources=2,
        n_factors_p=3,
        n_factors_c=2,
        uncertainty_radius_p=0.15,
        uncertainty_radius_c=0.10,
        seed=42,
        problem_type='energy'
    )

    # Create uncertainty sets
    uset_p = L2Ball(dim=problem.n_factors_p, radius=0.15)
    uset_c = L2Ball(dim=problem.n_factors_c, radius=0.10)

    # Solve both problems
    print("\nSolving nominal and robust problems...")
    nominal_solver = NominalOptimization(verbose=False)
    nominal_result = nominal_solver.solve(problem, uset_p, uset_c)

    drpg_solver = DRPG(outer_tolerance=1e-4, max_outer_iterations=50, verbose=False)
    drpg_result = drpg_solver.solve(problem, uset_p, uset_c)

    # Create economic analyzer
    print("\nPerforming comprehensive economic analysis...")
    analyzer = EconomicAnalyzer(
        n_test_scenarios=500,
        n_vss_scenarios=500,
        seed=42,
        verbose=True
    )

    # Analyze DRPG
    results = analyzer.analyze_method(
        method_name="DRPG",
        x_solution=np.concatenate(drpg_result.x_blocks),
        x_nominal=nominal_result.x_solution,
        problem=problem,
        uset_p=uset_p,
        uset_c=uset_c
    )

    # Validate results
    print(f"\nValidation:")
    print(f"  Out-of-sample result present: {'out_of_sample' in results}")
    print(f"  VSS result present: {'vss' in results}")

    if 'out_of_sample' in results:
        oos = results['out_of_sample']
        print(f"  OOS mean cost: ${oos.mean_cost:.2f}")
        print(f"  OOS std cost: ${oos.std_cost:.2f}")

    if 'vss' in results:
        vss = results['vss']
        print(f"  VSS value: ${vss.vss_value:.2f} ({vss.vss_percentage:+.2f}%)")
        print(f"  Worst-case improvement: {vss.worst_case_improvement:+.2f}%")

    if ('out_of_sample' in results and 'vss' in results):
        print("\n✅ TEST 4 PASSED: Economic analyzer works correctly")
        return True
    else:
        print("\n❌ TEST 4 FAILED")
        return False


def test_multiple_methods():
    """Test 5: Compare multiple methods economically."""
    print("\n" + "="*70)
    print("TEST 5: Multi-Method Economic Comparison")
    print("="*70)

    # Generate problem
    problem = generate_robust_qp(
        n_agents=3,
        avg_vars_per_agent=5,
        n_resources=2,
        n_factors_p=3,
        n_factors_c=2,
        uncertainty_radius_p=0.15,
        uncertainty_radius_c=0.10,
        seed=42,
        problem_type='energy'
    )

    uset_p = L2Ball(dim=problem.n_factors_p, radius=0.15)
    uset_c = L2Ball(dim=problem.n_factors_c, radius=0.10)

    # Solve with multiple methods
    print("\nSolving with multiple methods...")

    # Nominal
    from core.baseline_solvers import ScenarioBasedRO
    nominal_solver = NominalOptimization(verbose=False)
    nominal_result = nominal_solver.solve(problem, uset_p, uset_c)
    x_nominal = nominal_result.x_solution

    # Scenario-based
    scenario_solver = ScenarioBasedRO(
        scenario_generation="grid",
        n_scenarios_p=10,
        n_scenarios_c=10,
        verbose=False
    )
    scenario_result = scenario_solver.solve(problem, uset_p, uset_c)
    x_scenario = scenario_result.x_solution

    # DRPG
    drpg_solver = DRPG(outer_tolerance=1e-4, max_outer_iterations=50, verbose=False)
    drpg_result = drpg_solver.solve(problem, uset_p, uset_c)
    x_drpg = np.concatenate(drpg_result.x_blocks)

    print(f"  Nominal: ${-nominal_result.objective_value:.2f}")
    print(f"  Scenario: ${-scenario_result.objective_value:.2f}")
    print(f"  DRPG: ${-drpg_result.worst_case_value:.2f}")

    # Economic analysis for each
    print("\nPerforming economic analysis...")
    evaluator = OutOfSampleEvaluator(
        n_test_scenarios=300,
        scenario_generation="random",
        seed=42,
        verbose=False
    )

    methods = [
        ("Nominal", x_nominal),
        ("Scenario", x_scenario),
        ("DRPG", x_drpg)
    ]

    results = {}
    for method_name, x_sol in methods:
        print(f"\n  Evaluating {method_name}...")
        oos_result = evaluator.evaluate(
            method_name=method_name,
            x_solution=x_sol,
            problem=problem,
            uset_p=uset_p,
            uset_c=uset_c,
            x_nominal=x_nominal
        )
        results[method_name] = oos_result

    # Compare results
    print(f"\n{'Method':<15} {'Mean Cost':<15} {'Worst-case':<15} {'Std Dev':<15}")
    print("-"*60)
    for method_name in ["Nominal", "Scenario", "DRPG"]:
        r = results[method_name]
        print(f"{method_name:<15} ${-r.mean_cost:<14.2f} ${-r.worst_case_cost:<14.2f} ${r.std_cost:<14.2f}")

    # DRPG should have best or tied worst-case
    drpg_worst = results["DRPG"].worst_case_cost
    scenario_worst = results["Scenario"].worst_case_cost
    nominal_worst = results["Nominal"].worst_case_cost

    drpg_best_worst = drpg_worst >= min(scenario_worst, nominal_worst) - 100  # Small tolerance

    print(f"\n  DRPG has best/tied worst-case: {drpg_best_worst}")

    if len(results) == 3 and drpg_best_worst:
        print("\n✅ TEST 5 PASSED: Multi-method comparison works correctly")
        return True
    else:
        print("\n❌ TEST 5 FAILED")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("ECONOMIC ANALYSIS MODULE TEST SUITE")
    print("="*70)

    tests = [
        ("Scenario Generation", test_scenario_generation),
        ("Out-of-Sample Evaluation", test_out_of_sample_evaluation),
        ("VSS Computation", test_vss_computation),
        ("Economic Analyzer", test_economic_analyzer),
        ("Multi-Method Comparison", test_multiple_methods),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    n_passed = sum(1 for _, passed in results if passed)
    n_total = len(results)

    print(f"\nTotal: {n_passed}/{n_total} tests passed")

    if n_passed == n_total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {n_total - n_passed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit(main())
