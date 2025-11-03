"""
Test IEEE Problem Generator
============================

Quick validation script to test the IEEE-calibrated problem generator.
"""

import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.ieee_problem_generator import (
    generate_ieee_calibrated_qp,
    extract_ieee_generator_data,
    compare_ieee_vs_synthetic_statistics
)
from core.solvers import DirectNominalSolver, DRPG
from core.uncertainty_sets import L2Ball

def test_ieee_data_extraction():
    """Test that we can extract IEEE data successfully."""
    print("\n" + "="*70)
    print("TEST 1: IEEE Data Extraction")
    print("="*70)

    for case_name in ['case30', 'case57', 'case118']:
        print(f"\nExtracting {case_name}...")
        try:
            gen_data = extract_ieee_generator_data(case_name)
            print(f"  ✓ {case_name}: {gen_data['n_generators']} generators")
            print(f"    Capacity: {gen_data['p_max'].sum():.1f} MW")
            print(f"    Cost range: ${gen_data['cost_linear'].min():.1f}-${gen_data['cost_linear'].max():.1f}/MWh")
        except Exception as e:
            print(f"  ✗ {case_name} failed: {e}")
            return False

    return True

def test_ieee_problem_generation():
    """Test that we can generate IEEE-calibrated QP problems."""
    print("\n" + "="*70)
    print("TEST 2: IEEE Problem Generation")
    print("="*70)

    test_cases = [
        ('case30', 3, 2),
        ('case57', 4, 3),
        ('case118', 5, 3)
    ]

    problems = {}

    for case_name, n_factors_p, n_factors_c in test_cases:
        print(f"\nGenerating {case_name} with P={n_factors_p}, C={n_factors_c} factors...")
        try:
            problem = generate_ieee_calibrated_qp(
                ieee_case=case_name,
                n_factors_p=n_factors_p,
                n_factors_c=n_factors_c,
                uncertainty_radius_p=0.15,
                uncertainty_radius_c=0.10
            )

            # Validate problem structure
            n_agents = problem.n_agents
            total_vars = sum(problem.n_vars)

            print(f"  ✓ Problem created successfully")
            print(f"    Agents: {n_agents}")
            print(f"    Total variables: {total_vars}")
            print(f"    Uncertainty: P ∈ R^{problem.n_factors_p}, C ∈ R^{problem.n_factors_c}")

            # Check matrix dimensions
            assert problem.Q[0].shape[0] == problem.n_vars[0], "Q matrix dimension mismatch"
            assert problem.P[0].shape == (problem.n_vars[0], problem.n_factors_p), "P matrix dimension mismatch"

            # A is a list of matrices, check each one
            assert len(problem.A) == n_agents, "A list length mismatch"
            for i in range(n_agents):
                expected_shape = (problem.n_resources, problem.n_vars[i])
                actual_shape = problem.A[i].shape
                assert actual_shape == expected_shape, f"A[{i}] shape {actual_shape} != {expected_shape}"

            assert problem.B.shape == (problem.n_resources, problem.n_factors_c), "B matrix dimension mismatch"

            print(f"    All matrix dimensions validated ✓")

            # Store for later tests
            problems[case_name] = problem

        except Exception as e:
            print(f"  ✗ {case_name} generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False, None

    return True, problems

def test_nominal_solve(problems):
    """Test that nominal problems are feasible."""
    print("\n" + "="*70)
    print("TEST 3: Nominal Feasibility")
    print("="*70)

    solver = DirectNominalSolver()

    for case_name, problem in problems.items():
        print(f"\nSolving {case_name} at nominal uncertainty (u=0)...")
        try:
            # Zero uncertainty
            u_p = np.zeros(problem.n_factors_p)
            u_c = np.zeros(problem.n_factors_c)

            result = solver.solve(problem, u_p, u_c)

            if result['status'] == 'optimal':
                print(f"  ✓ Converged successfully")
                # DirectNominalSolver returns 'V_value' and 'x_full'
                obj_value = result.get('V_value', result.get('value', 'N/A'))
                if obj_value != 'N/A':
                    print(f"    Objective: ${-obj_value:.2f}")  # Negate for maximization
                x = result.get('x_full', result.get('x', None))
                if x is not None:
                    print(f"    Solution norm: {np.linalg.norm(x):.2f}")
                else:
                    print(f"    ⚠️ No solution found in result!")
                    return False

                # Check constraint satisfaction
                # A is a list of matrices, need to manually compute Ax
                Ax = np.zeros(problem.n_resources)
                offset = 0
                for i in range(problem.n_agents):
                    n_i = problem.n_vars[i]
                    x_i = x[offset:offset+n_i]
                    Ax += problem.A[i] @ x_i
                    offset += n_i
                residual = np.linalg.norm(Ax - problem.b)
                print(f"    Constraint residual: {residual:.2e}")

                if residual > 1e-3:
                    print(f"    ⚠️ Warning: Large constraint violation!")
            else:
                print(f"  ✗ Solver failed with status: {result['status']}")
                return False

        except Exception as e:
            print(f"  ✗ {case_name} solve failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    return True

def test_drpg_solve(problems):
    """Test DRPG on IEEE problems."""
    print("\n" + "="*70)
    print("TEST 4: DRPG Robust Optimization")
    print("="*70)

    # Test on case30 only (fastest)
    case_name = 'case30'
    problem = problems[case_name]

    print(f"\nRunning DRPG on {case_name}...")
    print(f"  Problem: {problem.n_agents} agents, {sum(problem.n_vars)} variables")
    print(f"  Uncertainty: L2Ball, radius_p=0.15, radius_c=0.10")

    try:
        # Create uncertainty sets
        uset_p = L2Ball(dim=problem.n_factors_p, radius=0.15)
        uset_c = L2Ball(dim=problem.n_factors_c, radius=0.10)

        # Initialize DRPG
        solver = DRPG(
            max_outer_iterations=100,
            outer_tolerance=1e-4,
            verbose=True
        )

        # Solve
        import time
        start = time.time()
        result = solver.solve(problem, uset_p, uset_c)
        elapsed = time.time() - start

        # DRPGResult is a dataclass, use attribute access
        if result.converged:
            print(f"\n  ✓ DRPG converged successfully")
            print(f"    Iterations: {result.outer_iterations}")
            print(f"    Runtime: {elapsed:.2f} seconds")
            print(f"    Robust value: ${-result.worst_case_value:.2f}")  # Negate for maximization
        else:
            print(f"\n  ✗ DRPG failed to converge")
            return False

    except Exception as e:
        print(f"\n  ✗ DRPG solve failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("IEEE PROBLEM GENERATOR VALIDATION")
    print("="*70)

    # Test 1: Data extraction
    if not test_ieee_data_extraction():
        print("\n❌ Data extraction test FAILED")
        return

    # Test 2: Problem generation
    success, problems = test_ieee_problem_generation()
    if not success:
        print("\n❌ Problem generation test FAILED")
        return

    # Test 3: Nominal solve
    if not test_nominal_solve(problems):
        print("\n❌ Nominal solve test FAILED")
        return

    # Test 4: DRPG solve
    if not test_drpg_solve(problems):
        print("\n❌ DRPG solve test FAILED")
        return

    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70)
    print("\nIEEE problem generator is working correctly!")
    print("Ready to proceed with comprehensive experiments.")

if __name__ == '__main__':
    main()
