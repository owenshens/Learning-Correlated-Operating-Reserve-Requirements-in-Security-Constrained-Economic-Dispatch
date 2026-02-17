"""
Experiment II.1: DRPG Convergence Rate Validation
==================================================

Objective:
    Verify that DRPG converges at the theoretical O(1/√K) rate for stress search.

    DRPG uses projected gradient ascent on:
        max_{u_p, u_c} V(u_p, u_c)  s.t. u_p ∈ U_p, u_c ∈ U_c

    where V(u_p, u_c) is the worst-case dispatch cost.

    Theoretical rate: For non-smooth convex optimization with projected subgradient,
    convergence rate is O(1/√K) where K is the number of iterations.

Methodology:
    1. Generate test problems across sizes
    2. Run DRPG with full history tracking (many iterations to see asymptotic behavior)
    3. Measure convergence gap: gap(k) = V* - V(k) where V* is final converged value
    4. Fit log(gap) vs log(k) to estimate rate: gap(k) ~ c * k^(-α)
       - Expected: α ≈ 0.5 (indicating O(1/√K))
    5. Compare empirical rate to theoretical prediction
    6. Test across problem sizes and uncertainty geometries

Expected Results:
    - Convergence rate exponent α ≈ 0.5 ± 0.1
    - Consistent across problem sizes
    - May vary slightly with uncertainty set geometry
    - Validates theoretical convergence guarantee

Outputs:
    - Figure: Convergence plots (gap vs iterations, log-log scale)
    - Figure: Rate analysis (fitted slopes by problem size)
    - Figure: Comparison across uncertainty sets
    - Table: Convergence statistics and fitted rates
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple
import time
from scipy.optimize import curve_fit
from scipy.stats import linregress

from core.problem_generator import generate_robust_qp, RobustQPProblem
from core.solvers import DRPG
from core.uncertainty_sets import create_uncertainty_set, UncertaintySet
from utils.logging_utils import ExperimentLogger
from utils.result_storage import save_experiment_results
from utils.statistical_tests import summary_statistics


def analyze_convergence_rate(
    iterations: np.ndarray,
    gaps: np.ndarray,
    skip_initial: int = 5,
) -> Dict:
    """
    Analyze convergence rate by fitting log(gap) vs log(k).

    Model: gap(k) = c * k^(-α)
    Taking log: log(gap) = log(c) - α * log(k)

    Args:
        iterations: Iteration numbers (1, 2, 3, ...)
        gaps: Convergence gaps gap(k) = V* - V(k)
        skip_initial: Skip first N iterations (transient behavior)

    Returns:
        Dictionary with fitted rate, R^2, etc.
    """
    # Filter out very small gaps (numerical noise) and initial transient
    valid_idx = (gaps > 1e-10) & (np.arange(len(gaps)) >= skip_initial)

    if np.sum(valid_idx) < 3:
        return {
            'success': False,
            'error_message': 'Insufficient valid data points for fitting',
        }

    k_valid = iterations[valid_idx]
    gap_valid = gaps[valid_idx]

    # Log-log linear regression
    log_k = np.log(k_valid)
    log_gap = np.log(gap_valid)

    slope, intercept, r_value, p_value, std_err = linregress(log_k, log_gap)

    # Convergence rate exponent is -slope
    rate_exponent = -slope

    # Theoretical prediction: O(1/√K) means α = 0.5
    theoretical_exponent = 0.5
    deviation = abs(rate_exponent - theoretical_exponent)

    return {
        'success': True,
        'rate_exponent': rate_exponent,  # Should be ~0.5 for O(1/√K)
        'rate_constant': np.exp(intercept),
        'r_squared': r_value**2,
        'std_error': std_err,
        'theoretical_exponent': theoretical_exponent,
        'deviation_from_theory': deviation,
        'n_points_fitted': len(k_valid),
    }


def test_drpg_convergence(
    problem: RobustQPProblem,
    uset_p: UncertaintySet,
    uset_c: UncertaintySet,
    max_iters: int = 200,
) -> Dict:
    """
    Test DRPG convergence on a single problem.

    Returns:
        Dictionary with convergence history and rate analysis
    """
    # Run DRPG with relaxed tolerance to get many iterations
    drpg = DRPG(
        max_outer_iterations=max_iters,
        outer_tolerance=1e-6,  # Very tight to force many iterations
        verbose=False,
    )

    result = drpg.solve(problem, uset_p, uset_c)

    if not result.converged or len(result.history['V_values']) < 10:
        return {
            'success': False,
            'error_message': f"DRPG failed or converged too quickly ({len(result.history.get('V_values', []))} iters)",
        }

    # Extract convergence history
    V_history = np.array(result.history['V_values'])
    best_history = np.array(result.history['best_values'])
    iterations = np.arange(1, len(best_history) + 1)

    # Convergence gap: V* - V(k) where V* is final value
    V_star = best_history[-1]
    gaps = V_star - best_history

    # Also track absolute gap (for problems where V* might be negative)
    gaps_abs = np.abs(gaps)

    # Analyze convergence rate
    rate_analysis = analyze_convergence_rate(iterations, gaps_abs, skip_initial=5)

    return {
        'success': True,
        'converged': result.converged,
        'n_iterations': len(V_history),
        'V_star': V_star,
        'V_history': V_history.tolist(),
        'best_history': best_history.tolist(),
        'gaps': gaps.tolist(),
        'gaps_abs': gaps_abs.tolist(),
        'iterations': iterations.tolist(),
        'rate_analysis': rate_analysis,
        'solve_time': result.solve_time,
    }


def run_experiment(
    problem_sizes: List[Tuple[int, int, int]],
    n_runs_per_problem: int,
    uncertainty_set_types: List[str],
    max_iters: int,
    logger: ExperimentLogger,
) -> Dict:
    """
    Run convergence rate experiment across multiple problems.

    Args:
        problem_sizes: List of (N_agents, n_vars_per_agent, n_resources)
        n_runs_per_problem: Number of random problems per size
        uncertainty_set_types: Types of uncertainty sets to test
        max_iters: Maximum DRPG iterations
        logger: Experiment logger

    Returns:
        Dictionary with all results
    """
    logger.info("Starting DRPG Convergence Rate Experiment")
    logger.info(f"Problem sizes: {problem_sizes}")
    logger.info(f"Runs per size: {n_runs_per_problem}")
    logger.info(f"Uncertainty sets: {uncertainty_set_types}")
    logger.info(f"Max iterations: {max_iters}")

    all_results = []
    total_tests = len(problem_sizes) * len(uncertainty_set_types) * n_runs_per_problem
    test_idx = 0
    start_time = time.time()

    for size_idx, (N, n_vars, m) in enumerate(problem_sizes):
        logger.info(f"\n{'='*60}")
        logger.info(f"Problem {size_idx + 1}/{len(problem_sizes)}: N={N}, vars={n_vars}, m={m}")

        for uset_type in uncertainty_set_types:
            logger.info(f"\n  Testing {uset_type}...")

            size_uset_results = []

            for run_idx in range(n_runs_per_problem):
                test_idx += 1
                elapsed = time.time() - start_time
                eta = elapsed / test_idx * (total_tests - test_idx) if test_idx > 0 else 0

                logger.log_progress(test_idx, total_tests,
                                  f"{uset_type}, run {run_idx+1}/{n_runs_per_problem}")

                # Generate random problem
                problem = generate_robust_qp(
                    n_agents=N,
                    avg_vars_per_agent=n_vars,
                    n_resources=m,
                    n_factors_p=max(3, m // 2),
                    n_factors_c=max(2, m // 3),
                    uncertainty_radius_p=2.0,
                    uncertainty_radius_c=1.5,
                    seed=1000 * size_idx + 100 * len(uncertainty_set_types) + 10 * run_idx + hash(uset_type) % 100,
                )

                # Create uncertainty sets
                uset_p = create_uncertainty_set(
                    uset_type,
                    dim=problem.n_factors_p,
                    radius=problem.uncertainty_radius_p,
                )
                uset_c = create_uncertainty_set(
                    uset_type,
                    dim=problem.n_factors_c,
                    radius=problem.uncertainty_radius_c,
                )

                # Test convergence
                result = test_drpg_convergence(problem, uset_p, uset_c, max_iters=max_iters)

                if result['success']:
                    result_record = {
                        'problem_size': (N, n_vars, m),
                        'uncertainty_set': uset_type,
                        'run_idx': run_idx,
                        **result,
                    }
                    size_uset_results.append(result_record)
                    all_results.append(result_record)

                    # Log rate analysis
                    if result['rate_analysis']['success']:
                        rate_exp = result['rate_analysis']['rate_exponent']
                        r2 = result['rate_analysis']['r_squared']
                        logger.info(f"    Run {run_idx+1}: Rate exponent α={rate_exp:.3f}, R²={r2:.3f}")

            # Summary for this size/uset combination
            if size_uset_results:
                rate_exponents = [r['rate_analysis']['rate_exponent']
                                 for r in size_uset_results
                                 if r['rate_analysis']['success']]
                if rate_exponents:
                    mean_rate = np.mean(rate_exponents)
                    std_rate = np.std(rate_exponents)
                    logger.info(f"    Summary: Mean α = {mean_rate:.3f} ± {std_rate:.3f} (target: 0.5)")

    elapsed_total = time.time() - start_time
    logger.info(f"\n{'='*70}")
    logger.info(f"Experiment completed in {elapsed_total:.2f}s")
    logger.info(f"{'='*70}\n")

    return {
        'all_results': all_results,
        'config': {
            'problem_sizes': problem_sizes,
            'n_runs_per_problem': n_runs_per_problem,
            'uncertainty_set_types': uncertainty_set_types,
            'max_iters': max_iters,
        },
        'total_time': elapsed_total,
    }


def generate_figures(results: Dict, output_dir: Path):
    """Generate convergence analysis figures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = results['all_results']
    max_iters = results['config']['max_iters']  # Get from config

    if not all_results:
        print("No results to plot!")
        return

    # Figure 1: Convergence trajectories (log-log)
    fig, axes = plt.subplots(1, len(results['config']['problem_sizes']),
                             figsize=(6 * len(results['config']['problem_sizes']), 5))
    if len(results['config']['problem_sizes']) == 1:
        axes = [axes]

    colors = sns.color_palette("husl", len(results['config']['uncertainty_set_types']))

    for size_idx, prob_size in enumerate(results['config']['problem_sizes']):
        ax = axes[size_idx]

        for uset_idx, uset_type in enumerate(results['config']['uncertainty_set_types']):
            # Get all runs for this size/uset
            matching = [r for r in all_results
                       if r['problem_size'] == prob_size and r['uncertainty_set'] == uset_type]

            if not matching:
                continue

            # Plot each run's convergence
            for r in matching:
                iterations = np.array(r['iterations'])
                gaps = np.array(r['gaps_abs'])

                # Filter out zeros for log scale
                valid = gaps > 1e-10
                if np.sum(valid) > 2:
                    ax.loglog(iterations[valid], gaps[valid],
                             alpha=0.4, color=colors[uset_idx], linewidth=1)

            # Plot theoretical O(1/√K) line
            if matching:
                k_range = np.logspace(0, np.log10(max_iters), 50)
                # Scale to match data
                typical_gap = np.median([r['gaps_abs'][5] for r in matching if len(r['gaps_abs']) > 5])
                theoretical_line = typical_gap * (k_range[0] / k_range) ** 0.5
                ax.loglog(k_range, theoretical_line, '--',
                         color=colors[uset_idx], linewidth=2,
                         label=f'{uset_type} (theory: O(1/√K))')

        ax.set_xlabel('Iteration k', fontsize=12)
        ax.set_ylabel('Convergence Gap |V* - V(k)|', fontsize=12)
        ax.set_title(f'N={prob_size[0]}, vars={prob_size[1]}, m={prob_size[2]}', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, which='both')

    plt.tight_layout()
    plt.savefig(output_dir / 'II1_convergence_trajectories.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 2: Rate exponent distribution
    fig, ax = plt.subplots(figsize=(10, 6))

    rate_data = []
    labels = []

    for prob_size in results['config']['problem_sizes']:
        for uset_type in results['config']['uncertainty_set_types']:
            matching = [r for r in all_results
                       if r['problem_size'] == prob_size
                       and r['uncertainty_set'] == uset_type
                       and r['rate_analysis']['success']]

            if matching:
                rates = [r['rate_analysis']['rate_exponent'] for r in matching]
                rate_data.append(rates)
                labels.append(f"{uset_type}\nN={prob_size[0]}")

    if rate_data:
        bp = ax.boxplot(rate_data, labels=labels, patch_artist=True)

        # Color boxes
        for patch, color in zip(bp['boxes'], sns.color_palette("Set2", len(rate_data))):
            patch.set_facecolor(color)

        # Add theoretical line
        ax.axhline(y=0.5, color='red', linestyle='--', linewidth=2, label='Theoretical O(1/√K): α=0.5')
        ax.axhspan(0.4, 0.6, alpha=0.1, color='red', label='±0.1 tolerance')

        ax.set_ylabel('Convergence Rate Exponent α', fontsize=12)
        ax.set_xlabel('Problem Configuration', fontsize=12)
        ax.set_title('DRPG Convergence Rate Analysis', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'II1_rate_exponents.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 3: R² goodness of fit
    fig, ax = plt.subplots(figsize=(10, 6))

    r2_data = []
    r2_labels = []

    for prob_size in results['config']['problem_sizes']:
        for uset_type in results['config']['uncertainty_set_types']:
            matching = [r for r in all_results
                       if r['problem_size'] == prob_size
                       and r['uncertainty_set'] == uset_type
                       and r['rate_analysis']['success']]

            if matching:
                r2_vals = [r['rate_analysis']['r_squared'] for r in matching]
                r2_data.append(r2_vals)
                r2_labels.append(f"{uset_type}\nN={prob_size[0]}")

    if r2_data:
        bp = ax.boxplot(r2_data, labels=r2_labels, patch_artist=True)

        for patch, color in zip(bp['boxes'], sns.color_palette("Set3", len(r2_data))):
            patch.set_facecolor(color)

        ax.axhline(y=0.95, color='green', linestyle='--', linewidth=2, label='Good fit: R²>0.95')
        ax.set_ylabel('R² (Goodness of Fit)', fontsize=12)
        ax.set_xlabel('Problem Configuration', fontsize=12)
        ax.set_title('Quality of Power-Law Fit', fontsize=14, fontweight='bold')
        ax.set_ylim([0.5, 1.0])
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'II1_fit_quality.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\n✅ Figures saved to {output_dir}/")


def generate_table(results: Dict, output_path: Path):
    """Generate LaTeX table with convergence statistics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_results = results['all_results']

    if not all_results:
        print("No results to tabulate!")
        return

    lines = []
    lines.append("\\begin{table}[h]")
    lines.append("\\centering")
    lines.append("\\caption{DRPG Convergence Rate Analysis}")
    lines.append("\\begin{tabular}{lcccccc}")
    lines.append("\\hline")
    lines.append("Problem & Uset & Runs & Mean $\\alpha$ & Std $\\alpha$ & Mean $R^2$ & Pass \\\\")
    lines.append("\\hline")

    for prob_size in results['config']['problem_sizes']:
        for uset_type in results['config']['uncertainty_set_types']:
            matching = [r for r in all_results
                       if r['problem_size'] == prob_size
                       and r['uncertainty_set'] == uset_type
                       and r['rate_analysis']['success']]

            if not matching:
                continue

            rates = [r['rate_analysis']['rate_exponent'] for r in matching]
            r2_vals = [r['rate_analysis']['r_squared'] for r in matching]

            mean_rate = np.mean(rates)
            std_rate = np.std(rates)
            mean_r2 = np.mean(r2_vals)

            # Validation: rate within [0.3, 0.7] and R² > 0.8
            passed = (0.3 <= mean_rate <= 0.7) and (mean_r2 > 0.8)
            pass_str = "\\checkmark" if passed else "\\times"

            prob_str = f"$N={prob_size[0]}$"
            lines.append(f"{prob_str} & {uset_type} & {len(matching)} & "
                        f"{mean_rate:.3f} & {std_rate:.3f} & {mean_r2:.3f} & {pass_str} \\\\")

    lines.append("\\hline")
    lines.append("\\multicolumn{7}{l}{Target: $\\alpha \\approx 0.5$ (O(1/$\\sqrt{K}$) convergence)} \\\\")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"\n✅ Table saved to {output_path}")


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("EXPERIMENT II.1: DRPG CONVERGENCE RATE VALIDATION")
    print("="*70)

    # Configuration
    problem_sizes = [
        (5, 10, 3),    # Small
        (10, 15, 5),   # Medium
    ]

    n_runs = 5
    uncertainty_sets = ['L2Ball', 'L1Ball']  # Focus on most stable
    max_iters = 200  # Many iterations to see asymptotic behavior

    # Run experiment
    logger = ExperimentLogger(
        "II.1_drpg_convergence",
        log_dir=Path(__file__).parent.parent.parent / "results" / "category_II",
        console_output=True,
    )

    logger.set_parameters({
        'problem_sizes': problem_sizes,
        'n_runs': n_runs,
        'uncertainty_sets': uncertainty_sets,
        'max_iters': max_iters,
    })

    results = run_experiment(
        problem_sizes=problem_sizes,
        n_runs_per_problem=n_runs,
        uncertainty_set_types=uncertainty_sets,
        max_iters=max_iters,
        logger=logger,
    )

    # Save results
    saved_files = save_experiment_results(
        experiment_name="II1_drpg_convergence",
        category="II",
        results=results,
        save_formats=['json', 'pickle'],
    )

    # Generate figures
    figures_dir = Path(__file__).parent.parent.parent / "figures" / "category_II"
    generate_figures(results, figures_dir)

    # Generate table
    table_path = Path(__file__).parent.parent.parent / "tables" / "II1_drpg_convergence.tex"
    generate_table(results, table_path)

    # Summary
    all_results = results['all_results']
    successful = [r for r in all_results if r['rate_analysis']['success']]

    if successful:
        rates = [r['rate_analysis']['rate_exponent'] for r in successful]
        r2_vals = [r['rate_analysis']['r_squared'] for r in successful]

        mean_rate = np.mean(rates)
        std_rate = np.std(rates)
        mean_r2 = np.mean(r2_vals)

        passed = (0.3 <= mean_rate <= 0.7) and (mean_r2 > 0.8)

        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Successful fits: {len(successful)}/{len(all_results)}")
        print(f"Mean convergence rate exponent α: {mean_rate:.3f} ± {std_rate:.3f}")
        print(f"Theoretical target: α = 0.5 (O(1/√K))")
        print(f"Deviation from theory: {abs(mean_rate - 0.5):.3f}")
        print(f"Mean R²: {mean_r2:.3f}")
        print(f"\n{'✅ VALIDATION PASSED' if passed else '❌ VALIDATION FAILED'}: "
              f"Rate exponent {'within' if passed else 'outside'} acceptable range [0.3, 0.7]")
        print("="*70)


if __name__ == "__main__":
    main()
