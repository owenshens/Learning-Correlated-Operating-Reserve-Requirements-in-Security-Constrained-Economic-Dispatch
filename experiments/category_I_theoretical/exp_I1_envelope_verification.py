"""
Experiment I.1: Envelope Theorem Verification
==============================================

Objective:
    Verify that the envelope theorem holds for robust dispatch:
    ∇_u V(u) = -P^T x*(u)
    where x*(u) is the optimal solution at uncertainty u.

Methodology:
    1. Generate test problems (small, medium sizes)
    2. Sample random uncertainties u within uncertainty sets
    3. For each u:
       a. Solve nominal problem → x*(u), V(u)
       b. Compute numerical gradient ∇V via finite differences
       c. Compute envelope gradient -P^T x
       d. Measure relative error
    4. Test across multiple uncertainty set types
    5. Statistical analysis of error distributions

Expected Results:
    - Relative error < 10^-4 for smooth problems
    - Error decreases with finer finite difference step
    - Consistent across uncertainty set geometries

Outputs:
    - Figure: Error vs. problem size
    - Figure: Error vs. finite difference step
    - Figure: Error distribution by uncertainty set type
    - Table: Summary statistics
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple
import time

from core.problem_generator import generate_robust_qp, RobustQPProblem
from core.solvers import DirectNominalSolver
from core.uncertainty_sets import create_uncertainty_set
from core.metrics import compute_envelope_gradient_error
from utils.logging_utils import ExperimentLogger, format_number
from utils.result_storage import save_experiment_results
from utils.statistical_tests import summary_statistics, confidence_interval


def compute_numerical_gradient(
    solver: DirectNominalSolver,
    problem: RobustQPProblem,
    u_p: np.ndarray,
    u_c: np.ndarray,
    epsilon: float = 1e-5,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute numerical gradient of V(u) via central finite differences.

    Args:
        solver: Nominal solver
        problem: Robust QP problem
        u_p: Objective uncertainty
        u_c: Constraint uncertainty
        epsilon: Finite difference step size

    Returns:
        (grad_p, grad_c): Gradients w.r.t. u_p and u_c
    """
    n_p = len(u_p)
    n_c = len(u_c)

    grad_p = np.zeros(n_p)
    grad_c = np.zeros(n_c)

    # Gradient w.r.t. u_p
    for i in range(n_p):
        u_p_plus = u_p.copy()
        u_p_plus[i] += epsilon

        u_p_minus = u_p.copy()
        u_p_minus[i] -= epsilon

        result_plus = solver.solve(problem, u_p_plus, u_c)
        result_minus = solver.solve(problem, u_p_minus, u_c)

        if result_plus.get('converged') and result_minus.get('converged'):
            V_plus = result_plus['V_value']
            V_minus = result_minus['V_value']
            grad_p[i] = (V_plus - V_minus) / (2 * epsilon)
        else:
            grad_p[i] = np.nan

    # Gradient w.r.t. u_c
    for i in range(n_c):
        u_c_plus = u_c.copy()
        u_c_plus[i] += epsilon

        u_c_minus = u_c.copy()
        u_c_minus[i] -= epsilon

        result_plus = solver.solve(problem, u_p, u_c_plus)
        result_minus = solver.solve(problem, u_p, u_c_minus)

        if result_plus.get('converged') and result_minus.get('converged'):
            V_plus = result_plus['V_value']
            V_minus = result_minus['V_value']
            grad_c[i] = (V_plus - V_minus) / (2 * epsilon)
        else:
            grad_c[i] = np.nan

    return grad_p, grad_c


def compute_envelope_gradient(
    problem: RobustQPProblem,
    x_blocks: List[np.ndarray],
    lambda_dual: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute envelope theorem gradient: ∇_u V = -P^T x for u_p, -B^T λ for u_c.

    Args:
        problem: Robust QP problem
        x_blocks: Optimal solution blocks
        lambda_dual: Optimal dual prices

    Returns:
        (grad_p, grad_c): Envelope gradients
    """
    # ∇_{u_p} V = -sum_i P_i^T x_i
    grad_p = -sum(problem.P[i].T @ x_blocks[i] for i in range(problem.n_agents))

    # ∇_{u_c} V = -B^T λ
    grad_c = -(problem.B.T @ lambda_dual)

    return grad_p, grad_c


def test_single_sample(
    problem: RobustQPProblem,
    u_p: np.ndarray,
    u_c: np.ndarray,
    solver: DirectNominalSolver,
    epsilon: float = 1e-5,
) -> Dict:
    """
    Test envelope theorem on a single uncertainty sample.

    Returns:
        Dictionary with numerical grad, envelope grad, and error metrics
    """
    # Solve at u
    result = solver.solve(problem, u_p, u_c)

    if not result.get('converged'):
        return {
            'success': False,
            'error_message': 'Solver did not converge',
        }

    x_blocks = result['x_blocks']
    lambda_dual = result['lambda']
    V_value = result['V_value']

    # Compute numerical gradient
    grad_num_p, grad_num_c = compute_numerical_gradient(solver, problem, u_p, u_c, epsilon)

    # Check for NaN
    if np.any(np.isnan(grad_num_p)) or np.any(np.isnan(grad_num_c)):
        return {
            'success': False,
            'error_message': 'Numerical gradient contains NaN',
        }

    # Compute envelope gradient
    grad_env_p, grad_env_c = compute_envelope_gradient(problem, x_blocks, lambda_dual)

    # Compute errors
    error_p = np.linalg.norm(grad_num_p - grad_env_p)
    error_c = np.linalg.norm(grad_num_c - grad_env_c)

    # Relative errors
    denom_p = np.linalg.norm(grad_num_p)
    denom_c = np.linalg.norm(grad_num_c)

    rel_error_p = error_p / max(denom_p, 1e-12)
    rel_error_c = error_c / max(denom_c, 1e-12)

    return {
        'success': True,
        'V_value': V_value,
        'grad_numerical_p': grad_num_p,
        'grad_numerical_c': grad_num_c,
        'grad_envelope_p': grad_env_p,
        'grad_envelope_c': grad_env_c,
        'error_absolute_p': error_p,
        'error_absolute_c': error_c,
        'error_relative_p': rel_error_p,
        'error_relative_c': rel_error_c,
        'error_combined': np.sqrt(rel_error_p**2 + rel_error_c**2),
    }


def run_experiment(
    problem_sizes: List[Tuple[int, int, int]],
    n_samples_per_problem: int = 20,
    uncertainty_set_types: List[str] = ['L2Ball', 'L1Ball', 'LinfBox'],
    epsilon_values: List[float] = [1e-4, 1e-5, 1e-6],
    logger: ExperimentLogger = None,
) -> Dict:
    """
    Run envelope theorem verification experiment.

    Args:
        problem_sizes: List of (n_agents, avg_vars_per_agent, n_resources)
        n_samples_per_problem: Number of random u samples per problem
        uncertainty_set_types: Types of uncertainty sets to test
        epsilon_values: Finite difference step sizes
        logger: Experiment logger

    Returns:
        Results dictionary
    """
    if logger is None:
        logger = ExperimentLogger("I.1_envelope_verification", console_output=True)

    logger.info("Starting Envelope Theorem Verification")
    logger.info(f"Problem sizes: {problem_sizes}")
    logger.info(f"Samples per problem: {n_samples_per_problem}")
    logger.info(f"Uncertainty sets: {uncertainty_set_types}")
    logger.info(f"Epsilon values: {epsilon_values}")

    solver = DirectNominalSolver()
    results = {
        'problem_sizes': problem_sizes,
        'n_samples_per_problem': n_samples_per_problem,
        'uncertainty_set_types': uncertainty_set_types,
        'epsilon_values': epsilon_values,
        'tests': [],
    }

    total_tests = len(problem_sizes) * len(uncertainty_set_types) * len(epsilon_values)
    test_count = 0

    for prob_idx, (n_agents, avg_vars, n_resources) in enumerate(problem_sizes):
        logger.info(f"\n{'='*60}")
        logger.info(f"Problem {prob_idx+1}/{len(problem_sizes)}: "
                   f"N={n_agents}, vars={avg_vars}, m={n_resources}")

        # Generate problem
        problem = generate_robust_qp(
            n_agents=n_agents,
            avg_vars_per_agent=avg_vars,
            n_resources=n_resources,
            n_factors_p=3,
            n_factors_c=2,
            uncertainty_radius_p=3.0,
            uncertainty_radius_c=1.5,
            seed=42 + prob_idx,
        )

        for set_type in uncertainty_set_types:
            # Create uncertainty sets
            uset_p = create_uncertainty_set(set_type, dim=problem.n_factors_p,
                                           radius=problem.uncertainty_radius_p)
            uset_c = create_uncertainty_set(set_type, dim=problem.n_factors_c,
                                           radius=problem.uncertainty_radius_c)

            logger.info(f"\n  Testing {set_type}...")

            for epsilon in epsilon_values:
                test_count += 1
                logger.log_progress(test_count, total_tests,
                                  f"{set_type}, ε={epsilon:.1e}")

                test_results = {
                    'problem_size': (n_agents, avg_vars, n_resources),
                    'n_vars_total': problem.total_vars(),
                    'uncertainty_set': set_type,
                    'epsilon': epsilon,
                    'samples': [],
                }

                n_success = 0
                errors_rel_combined = []

                for sample_idx in range(n_samples_per_problem):
                    # Sample random uncertainty
                    u_p = uset_p.sample()
                    u_c = uset_c.sample()

                    # Test envelope theorem
                    sample_result = test_single_sample(problem, u_p, u_c, solver, epsilon)

                    if sample_result['success']:
                        n_success += 1
                        errors_rel_combined.append(sample_result['error_combined'])

                    test_results['samples'].append(sample_result)

                # Compute statistics
                if len(errors_rel_combined) > 0:
                    test_results['n_success'] = n_success
                    test_results['success_rate'] = n_success / n_samples_per_problem
                    test_results['error_mean'] = float(np.mean(errors_rel_combined))
                    test_results['error_std'] = float(np.std(errors_rel_combined))
                    test_results['error_median'] = float(np.median(errors_rel_combined))
                    test_results['error_max'] = float(np.max(errors_rel_combined))
                    test_results['error_min'] = float(np.min(errors_rel_combined))

                    # 95% confidence interval
                    if n_success > 1:
                        ci = confidence_interval(np.array(errors_rel_combined), confidence=0.95)
                        test_results['error_ci_lower'] = float(ci[0])
                        test_results['error_ci_upper'] = float(ci[1])

                    logger.info(f"    ε={epsilon:.1e}: mean={test_results['error_mean']:.2e}, "
                               f"max={test_results['error_max']:.2e}, "
                               f"success={n_success}/{n_samples_per_problem}")
                else:
                    test_results['n_success'] = 0
                    test_results['success_rate'] = 0.0
                    logger.warning(f"    ε={epsilon:.1e}: All samples failed!")

                results['tests'].append(test_results)

    logger.finalize()
    return results


def generate_figures(results: Dict, output_dir: Path):
    """Generate figures for experiment I.1."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.style.use('seaborn-v0_8-darkgrid')
    sns.set_palette("Set2")

    # Figure 1: Error vs Problem Size
    fig, ax = plt.subplots(figsize=(10, 6))

    # Group by epsilon and uncertainty set
    for epsilon in results['epsilon_values']:
        for set_type in results['uncertainty_set_types']:
            sizes = []
            errors = []

            for test in results['tests']:
                if test['epsilon'] == epsilon and test['uncertainty_set'] == set_type:
                    if test['n_success'] > 0:
                        sizes.append(test['n_vars_total'])
                        errors.append(test['error_mean'])

            if len(sizes) > 0:
                ax.plot(sizes, errors, marker='o', label=f"{set_type}, ε={epsilon:.1e}")

    ax.set_xlabel('Total Variables', fontsize=12)
    ax.set_ylabel('Mean Relative Error', fontsize=12)
    ax.set_yscale('log')
    ax.set_title('Envelope Theorem Error vs Problem Size', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'I1_error_vs_size.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 2: Error vs Epsilon
    fig, ax = plt.subplots(figsize=(10, 6))

    for set_type in results['uncertainty_set_types']:
        epsilons = []
        errors = []

        for epsilon in results['epsilon_values']:
            # Average over all problem sizes
            errors_at_eps = []
            for test in results['tests']:
                if test['epsilon'] == epsilon and test['uncertainty_set'] == set_type:
                    if test['n_success'] > 0:
                        errors_at_eps.append(test['error_mean'])

            if len(errors_at_eps) > 0:
                epsilons.append(epsilon)
                errors.append(np.mean(errors_at_eps))

        if len(epsilons) > 0:
            ax.plot(epsilons, errors, marker='s', label=set_type, linewidth=2)

    ax.set_xlabel('Finite Difference Step Size (ε)', fontsize=12)
    ax.set_ylabel('Mean Relative Error', fontsize=12)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_title('Envelope Theorem Error vs Step Size', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'I1_error_vs_epsilon.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 3: Error Distribution by Uncertainty Set
    fig, ax = plt.subplots(figsize=(10, 6))

    # Use best epsilon (smallest)
    best_epsilon = min(results['epsilon_values'])
    data_for_violin = []
    labels = []

    for set_type in results['uncertainty_set_types']:
        errors = []
        for test in results['tests']:
            if test['epsilon'] == best_epsilon and test['uncertainty_set'] == set_type:
                for sample in test['samples']:
                    if sample['success']:
                        errors.append(sample['error_combined'])

        if len(errors) > 0:
            data_for_violin.append(errors)
            labels.append(set_type)

    if len(data_for_violin) > 0:
        parts = ax.violinplot(data_for_violin, positions=range(len(labels)),
                             showmeans=True, showmedians=True)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylabel('Relative Error', fontsize=12)
        ax.set_yscale('log')
        ax.set_title(f'Error Distribution by Uncertainty Set (ε={best_epsilon:.1e})',
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(output_dir / 'I1_error_distribution.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\n✅ Figures saved to {output_dir}/")


def generate_table(results: Dict) -> str:
    """Generate LaTeX table for experiment I.1."""

    # Use best epsilon
    best_epsilon = min(results['epsilon_values'])

    table = r"""\begin{table}[htbp]
\centering
\caption{Envelope Theorem Verification Results}
\label{tab:envelope_verification}
\begin{tabular}{lcccccc}
\toprule
\textbf{Set Type} & \textbf{Size} & \textbf{Mean} & \textbf{Median} & \textbf{Max} & \textbf{CI Lower} & \textbf{CI Upper} \\
\midrule
"""

    for set_type in results['uncertainty_set_types']:
        for test in results['tests']:
            if test['epsilon'] == best_epsilon and test['uncertainty_set'] == set_type:
                if test['n_success'] > 0:
                    size = test['n_vars_total']
                    mean = test['error_mean']
                    median = test['error_median']
                    max_err = test['error_max']
                    ci_low = test.get('error_ci_lower', 0)
                    ci_high = test.get('error_ci_upper', 0)

                    table += f"{set_type} & {size} & "
                    table += f"{mean:.2e} & {median:.2e} & {max_err:.2e} & "
                    table += f"{ci_low:.2e} & {ci_high:.2e} \\\\\n"

    table += r"""\bottomrule
\end{tabular}
\end{table}
"""

    return table


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("EXPERIMENT I.1: ENVELOPE THEOREM VERIFICATION")
    print("="*70)

    # Configuration
    problem_sizes = [
        (5, 10, 3),    # Small
        (10, 15, 5),   # Medium-small
        (20, 20, 8),   # Medium
    ]

    n_samples = 20
    uncertainty_sets = ['L2Ball', 'L1Ball', 'LinfBox']
    epsilons = [1e-4, 1e-5, 1e-6]

    # Run experiment
    logger = ExperimentLogger(
        "I.1_envelope_verification",
        log_dir=Path(__file__).parent.parent.parent / "results" / "category_I",
        console_output=True,
    )

    logger.set_parameters({
        'problem_sizes': problem_sizes,
        'n_samples': n_samples,
        'uncertainty_sets': uncertainty_sets,
        'epsilons': epsilons,
    })

    results = run_experiment(
        problem_sizes=problem_sizes,
        n_samples_per_problem=n_samples,
        uncertainty_set_types=uncertainty_sets,
        epsilon_values=epsilons,
        logger=logger,
    )

    # Save results
    output_dir = Path(__file__).parent.parent.parent / "results" / "category_I"
    saved_files = save_experiment_results(
        experiment_name="I1_envelope_verification",
        category="I",
        results=results,
        save_formats=['json', 'pickle'],
    )

    # Generate figures
    figures_dir = Path(__file__).parent.parent.parent / "figures" / "category_I"
    generate_figures(results, figures_dir)

    # Generate table
    table_dir = Path(__file__).parent.parent.parent / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    table_latex = generate_table(results)
    with open(table_dir / "I1_envelope_verification.tex", 'w') as f:
        f.write(table_latex)
    print(f"\n✅ Table saved to {table_dir}/I1_envelope_verification.tex")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    best_eps = min(epsilons)
    for set_type in uncertainty_sets:
        errors = []
        for test in results['tests']:
            if test['epsilon'] == best_eps and test['uncertainty_set'] == set_type:
                if test['n_success'] > 0:
                    errors.append(test['error_mean'])

        if len(errors) > 0:
            print(f"{set_type:12s}: mean error = {np.mean(errors):.2e}, "
                  f"max error = {np.max(errors):.2e}")

    # Validation check
    all_errors = []
    for test in results['tests']:
        if test['epsilon'] == best_eps and test['n_success'] > 0:
            all_errors.append(test['error_mean'])

    if len(all_errors) > 0:
        overall_mean = np.mean(all_errors)
        print(f"\nOverall mean error: {overall_mean:.2e}")

        if overall_mean < 1e-4:
            print("✅ VALIDATION PASSED: Error < 10^-4")
        else:
            print("⚠️  VALIDATION WARNING: Error >= 10^-4")

    print("="*70)

    return results


if __name__ == "__main__":
    results = main()
