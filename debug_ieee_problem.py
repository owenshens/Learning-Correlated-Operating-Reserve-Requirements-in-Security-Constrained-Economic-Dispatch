"""
Debug IEEE Problem Structure
=============================

Diagnose why nominal solver fails on IEEE problems.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ieee_problem_generator import generate_ieee_calibrated_qp

def debug_problem_structure(case_name='case30'):
    """Analyze problem structure to find rank issues."""
    print(f"\n{'='*70}")
    print(f"Debugging {case_name}")
    print('='*70)

    # Generate problem
    problem = generate_ieee_calibrated_qp(
        ieee_case=case_name,
        n_factors_p=3,
        n_factors_c=2,
    )

    print(f"\nProblem dimensions:")
    print(f"  Agents: {problem.n_agents}")
    print(f"  Variables per agent: {problem.n_vars}")
    print(f"  Total variables: {sum(problem.n_vars)}")
    print(f"  Constraints: {problem.n_resources}")

    # Assemble full A matrix
    n_total = sum(problem.n_vars)
    A_full = np.zeros((problem.n_resources, n_total))
    offset = 0
    for i in range(problem.n_agents):
        n_i = problem.n_vars[i]
        A_full[:, offset:offset+n_i] = problem.A[i]
        offset += n_i

    print(f"\nA matrix analysis:")
    print(f"  Shape: {A_full.shape}")
    print(f"  Rank: {np.linalg.matrix_rank(A_full)}")
    print(f"  Expected rank: {min(A_full.shape)}")

    if np.linalg.matrix_rank(A_full) < problem.n_resources:
        print(f"  ⚠️ WARNING: A matrix is rank deficient!")
        print(f"  Missing {problem.n_resources - np.linalg.matrix_rank(A_full)} independent rows")

    # Check b vector
    print(f"\nb vector:")
    print(f"  Shape: {problem.b.shape}")
    print(f"  Min: {problem.b.min():.2f}")
    print(f"  Max: {problem.b.max():.2f}")
    print(f"  Mean: {problem.b.mean():.2f}")
    print(f"  Zeros: {np.sum(problem.b == 0)}")

    # Check if there are all-zero rows in A
    row_norms = np.linalg.norm(A_full, axis=1)
    zero_rows = np.where(row_norms < 1e-10)[0]
    if len(zero_rows) > 0:
        print(f"\n⚠️ WARNING: {len(zero_rows)} all-zero rows in A!")
        print(f"  Row indices: {zero_rows}")

    # Check bounds
    print(f"\nBounds:")
    x_lower_full = np.concatenate(problem.x_lower)
    x_upper_full = np.concatenate(problem.x_upper)
    print(f"  x_lower range: [{x_lower_full.min():.2f}, {x_lower_full.max():.2f}]")
    print(f"  x_upper range: [{x_upper_full.min():.2f}, {x_upper_full.max():.2f}]")

    # Try to find a feasible point manually
    print(f"\nFeasibility check:")
    # Set all generators to their minimum
    x_test = x_lower_full.copy()
    Ax_test = A_full @ x_test
    print(f"  At x=x_lower: Ax - b = {np.linalg.norm(Ax_test - problem.b):.2e}")
    print(f"  Component-wise gap: [{(Ax_test - problem.b).min():.2e}, {(Ax_test - problem.b).max():.2e}]")

    # Try maximum
    x_test = x_upper_full.copy()
    Ax_test = A_full @ x_test
    print(f"  At x=x_upper: Ax - b = {np.linalg.norm(Ax_test - problem.b):.2e}")
    print(f"  Component-wise gap: [{(Ax_test - problem.b).min():.2e}, {(Ax_test - problem.b).max():.2e}]")

    # Try midpoint
    x_test = 0.5 * (x_lower_full + x_upper_full)
    Ax_test = A_full @ x_test
    print(f"  At x=midpoint: Ax - b = {np.linalg.norm(Ax_test - problem.b):.2e}")
    print(f"  Component-wise gap: [{(Ax_test - problem.b).min():.2e}, {(Ax_test - problem.b).max():.2e}]")

    # Print actual values for first few constraints
    print(f"\nFirst 5 constraints:")
    for j in range(min(5, problem.n_resources)):
        row_j = A_full[j, :]
        nonzero_idx = np.where(np.abs(row_j) > 1e-10)[0]
        print(f"  Row {j}: {len(nonzero_idx)} nonzeros, b[{j}] = {problem.b[j]:.2f}")
        if len(nonzero_idx) > 0:
            print(f"    Nonzero coefficients: {row_j[nonzero_idx]}")

if __name__ == '__main__':
    for case in ['case30']:  # Start with case30
        debug_problem_structure(case)
