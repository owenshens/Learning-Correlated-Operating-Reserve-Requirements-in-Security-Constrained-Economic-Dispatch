"""
Experiment III.1: DRPG Scalability Analysis
============================================

Objective:
    Test DRPG computational performance across problem sizes from small to large.

    Key questions:
    - How does runtime scale with problem size?
    - Does the fast convergence from Phase 2 hold for larger problems?
    - What is the practical size limit?
    - How do iterations scale with size?

Methodology:
    1. Generate problems of increasing size: N ∈ {5, 10, 20, 50, 100}
    2. For each size, run multiple instances (3-5 runs)
    3. Measure:
       - Total solve time
       - Number of outer iterations
       - Number of inner solves
       - Convergence quality
    4. Analyze scaling patterns:
       - Fit runtime ~ N^α to estimate complexity exponent α
       - Compare to theoretical expectations
       - Identify practical limits

Expected Results:
    - Runtime should scale polynomially (hopefully N^2 to N^3)
    - Iterations may increase slowly with size
    - Fast convergence should persist for larger problems
    - Identify practical size limit (where runtime becomes prohibitive)

Outputs:
    - Figure: Runtime vs problem size (log-log)
    - Figure: Iterations vs problem size
    - Figure: Solve time per iteration vs size
    - Table: Scalability statistics by problem size
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


def test_drpg_scalability(
    problem: RobustQPProblem,
    uset_p: UncertaintySet,
    uset_c: UncertaintySet,
    max_iters: int = 100,
) -> Dict:
    """
    Test DRPG performance on a single problem.

    Returns:
        Dictionary with timing and convergence metrics
    """
    # Run DRPG with standard settings
    drpg = DRPG(
        max_outer_iterations=max_iters,
        outer_tolerance=1e-3,  # Standard tolerance
        verbose=False,
    )

    start_time = time.time()
    result = drpg.solve(problem, uset_p, uset_c)
    total_time = time.time() - start_time

    if not result.converged:
        return {
            'success': False,
            'error_message': 'DRPG did not converge',
        }

    # Extract metrics
    n_agents = problem.n_agents
    n_vars_total = sum(problem.n_vars)
    n_resources = problem.n_resources
    n_iterations = result.outer_iterations
    n_inner_solves = result.total_inner_iterations

    return {
        'success': True,
        'problem_size': {
            'n_agents': n_agents,
            'n_vars_total': n_vars_total,
            'n_resources': n_resources,
        },
        'performance': {
            'total_time': total_time,
            'n_iterations': n_iterations,
            'n_inner_solves': n_inner_solves,
            'time_per_iteration': total_time / max(n_iterations, 1),
            'time_per_inner_solve': total_time / max(n_inner_solves, 1),
        },
        'solution_quality': {
            'worst_case_value': result.worst_case_value,
            'converged': result.converged,
        },
        'solve_time': result.solve_time,
    }


def run_experiment(
    problem_sizes: List[Tuple[int, int, int]],
    n_runs_per_size: int,
    uncertainty_set_type: str,
    max_iters: int,
    logger: ExperimentLogger,
) -> Dict:
    """
    Run scalability experiment across problem sizes.

    Args:
        problem_sizes: List of (N_agents, n_vars_per_agent, n_resources)
        n_runs_per_size: Number of random problems per size
        uncertainty_set_type: Type of uncertainty set
        max_iters: Maximum DRPG iterations
        logger: Experiment logger

    Returns:
        Dictionary with all results
    """
    logger.info("Starting DRPG Scalability Experiment")
    logger.info(f"Problem sizes: {problem_sizes}")
    logger.info(f"Runs per size: {n_runs_per_size}")
    logger.info(f"Uncertainty set: {uncertainty_set_type}")
    logger.info(f"Max iterations: {max_iters}")

    all_results = []
    total_tests = len(problem_sizes) * n_runs_per_size
    test_idx = 0
    start_time = time.time()

    for size_idx, (N, n_vars, m) in enumerate(problem_sizes):
        logger.info(f"\n{'='*60}")
        logger.info(f"Problem Size {size_idx + 1}/{len(problem_sizes)}: N={N}, vars/agent={n_vars}, m={m}")
        logger.info(f"  Total variables: {N * n_vars}, Total constraints: {m}")

        size_results = []

        for run_idx in range(n_runs_per_size):
            test_idx += 1
            elapsed = time.time() - start_time
            eta = elapsed / test_idx * (total_tests - test_idx) if test_idx > 0 else 0

            logger.log_progress(test_idx, total_tests,
                              f"N={N}, run {run_idx+1}/{n_runs_per_size}")

            # Generate random problem
            problem = generate_robust_qp(
                n_agents=N,
                avg_vars_per_agent=n_vars,
                n_resources=m,
                n_factors_p=max(3, m // 2),
                n_factors_c=max(2, m // 3),
                uncertainty_radius_p=2.0,
                uncertainty_radius_c=1.5,
                seed=1000 * size_idx + 100 * run_idx,
            )

            # Create uncertainty sets
            uset_p = create_uncertainty_set(
                uncertainty_set_type,
                dim=problem.n_factors_p,
                radius=problem.uncertainty_radius_p,
            )
            uset_c = create_uncertainty_set(
                uncertainty_set_type,
                dim=problem.n_factors_c,
                radius=problem.uncertainty_radius_c,
            )

            # Test scalability
            result = test_drpg_scalability(problem, uset_p, uset_c, max_iters=max_iters)

            if result['success']:
                result_record = {
                    'size_params': (N, n_vars, m),
                    'run_idx': run_idx,
                    **result,
                }
                size_results.append(result_record)
                all_results.append(result_record)

                # Log performance
                perf = result['performance']
                logger.info(f"    Run {run_idx+1}: {perf['total_time']:.2f}s, "
                          f"{perf['n_iterations']} iters, "
                          f"{perf['time_per_iteration']*1000:.1f}ms/iter")

        # Summary for this size
        if size_results:
            times = [r['performance']['total_time'] for r in size_results]
            iters = [r['performance']['n_iterations'] for r in size_results]

            mean_time = np.mean(times)
            std_time = np.std(times)
            mean_iters = np.mean(iters)

            logger.info(f"\n  Size N={N} Summary:")
            logger.info(f"    Mean time: {mean_time:.2f}s ± {std_time:.2f}s")
            logger.info(f"    Mean iterations: {mean_iters:.1f}")

    elapsed_total = time.time() - start_time
    logger.info(f"\n{'='*70}")
    logger.info(f"Experiment completed in {elapsed_total:.2f}s")
    logger.info(f"{'='*70}\n")

    return {
        'all_results': all_results,
        'config': {
            'problem_sizes': problem_sizes,
            'n_runs_per_size': n_runs_per_size,
            'uncertainty_set_type': uncertainty_set_type,
            'max_iters': max_iters,
        },
        'total_time': elapsed_total,
    }


def analyze_scaling(results: Dict) -> Dict:
    """
    Analyze computational scaling patterns.

    Fit models:
    - Runtime ~ N^α (power law)
    - Iterations ~ log(N) or ~ N^β

    Returns:
        Dictionary with scaling analysis
    """
    all_results = results['all_results']

    # Group by problem size
    size_data = {}
    for r in all_results:
        N = r['size_params'][0]
        if N not in size_data:
            size_data[N] = {
                'times': [],
                'iterations': [],
                'vars': [],
                'resources': [],
            }

        size_data[N]['times'].append(r['performance']['total_time'])
        size_data[N]['iterations'].append(r['performance']['n_iterations'])
        size_data[N]['vars'].append(r['problem_size']['n_vars_total'])
        size_data[N]['resources'].append(r['problem_size']['n_resources'])

    # Compute statistics per size
    sizes = sorted(size_data.keys())
    mean_times = []
    std_times = []
    mean_iters = []
    mean_vars = []

    for N in sizes:
        mean_times.append(np.mean(size_data[N]['times']))
        std_times.append(np.std(size_data[N]['times']))
        mean_iters.append(np.mean(size_data[N]['iterations']))
        mean_vars.append(np.mean(size_data[N]['vars']))

    sizes_arr = np.array(sizes)
    times_arr = np.array(mean_times)
    iters_arr = np.array(mean_iters)
    vars_arr = np.array(mean_vars)

    # Fit power law: time ~ N^α
    if len(sizes) >= 3:
        log_N = np.log(sizes_arr)
        log_time = np.log(times_arr)

        slope_time, intercept_time, r_time, _, _ = linregress(log_N, log_time)

        # Also fit vs total variables
        log_vars = np.log(vars_arr)
        slope_vars, intercept_vars, r_vars, _, _ = linregress(log_vars, log_time)

        # Fit iterations scaling
        slope_iters, intercept_iters, r_iters, _, _ = linregress(log_N, np.log(iters_arr))

        scaling_analysis = {
            'runtime_vs_agents': {
                'exponent': slope_time,
                'constant': np.exp(intercept_time),
                'r_squared': r_time**2,
                'interpretation': f"Runtime ~ N^{slope_time:.2f}",
            },
            'runtime_vs_vars': {
                'exponent': slope_vars,
                'constant': np.exp(intercept_vars),
                'r_squared': r_vars**2,
                'interpretation': f"Runtime ~ vars^{slope_vars:.2f}",
            },
            'iterations_scaling': {
                'exponent': slope_iters,
                'constant': np.exp(intercept_iters),
                'r_squared': r_iters**2,
                'interpretation': f"Iterations ~ N^{slope_iters:.2f}",
            },
            'size_statistics': {
                'sizes': sizes,
                'mean_times': mean_times,
                'std_times': std_times,
                'mean_iterations': mean_iters,
                'mean_vars': mean_vars,
            },
        }
    else:
        scaling_analysis = {
            'error': 'Insufficient data points for scaling analysis',
            'size_statistics': {
                'sizes': sizes,
                'mean_times': mean_times,
                'std_times': std_times,
                'mean_iterations': mean_iters,
                'mean_vars': mean_vars,
            },
        }

    return scaling_analysis


def generate_figures(results: Dict, scaling_analysis: Dict, output_dir: Path):
    """Generate scalability analysis figures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = results['all_results']
    size_stats = scaling_analysis['size_statistics']

    if not all_results:
        print("No results to plot!")
        return

    # Figure 1: Runtime vs Problem Size (log-log)
    fig, ax = plt.subplots(figsize=(10, 7))

    sizes = size_stats['sizes']
    mean_times = size_stats['mean_times']
    std_times = size_stats['std_times']

    # Scatter plot of individual runs
    for r in all_results:
        N = r['size_params'][0]
        t = r['performance']['total_time']
        ax.scatter(N, t, alpha=0.4, s=50, color='steelblue')

    # Mean with error bars
    ax.errorbar(sizes, mean_times, yerr=std_times,
                fmt='o-', markersize=10, linewidth=2, capsize=5,
                color='darkblue', label='Mean ± Std')

    # Fitted power law
    if 'runtime_vs_agents' in scaling_analysis:
        rt_scaling = scaling_analysis['runtime_vs_agents']
        N_fit = np.linspace(min(sizes), max(sizes), 100)
        t_fit = rt_scaling['constant'] * N_fit ** rt_scaling['exponent']

        ax.plot(N_fit, t_fit, '--', linewidth=2, color='red',
               label=f"Fit: $t \\propto N^{{{rt_scaling['exponent']:.2f}}}$ ($R^2$={rt_scaling['r_squared']:.3f})")

    ax.set_xlabel('Number of Agents (N)', fontsize=14)
    ax.set_ylabel('Total Solve Time (seconds)', fontsize=14)
    ax.set_title('DRPG Scalability: Runtime vs Problem Size', fontsize=16, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    plt.tight_layout()
    plt.savefig(output_dir / 'III1_runtime_scaling.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 2: Iterations vs Problem Size
    fig, ax = plt.subplots(figsize=(10, 7))

    mean_iters = size_stats['mean_iterations']

    # Scatter individual runs
    for r in all_results:
        N = r['size_params'][0]
        iters = r['performance']['n_iterations']
        ax.scatter(N, iters, alpha=0.4, s=50, color='green')

    # Mean line
    ax.plot(sizes, mean_iters, 'o-', markersize=10, linewidth=2,
           color='darkgreen', label='Mean iterations')

    # Fitted scaling
    if 'iterations_scaling' in scaling_analysis:
        iter_scaling = scaling_analysis['iterations_scaling']
        iters_fit = iter_scaling['constant'] * N_fit ** iter_scaling['exponent']

        ax.plot(N_fit, iters_fit, '--', linewidth=2, color='red',
               label=f"Fit: $k \\propto N^{{{iter_scaling['exponent']:.2f}}}$")

    ax.set_xlabel('Number of Agents (N)', fontsize=14)
    ax.set_ylabel('Number of Outer Iterations', fontsize=14)
    ax.set_title('DRPG Convergence: Iterations vs Problem Size', fontsize=16, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'III1_iterations_scaling.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    # Figure 3: Time per iteration vs size
    fig, ax = plt.subplots(figsize=(10, 7))

    time_per_iter = [t/k for t, k in zip(mean_times, mean_iters)]

    for r in all_results:
        N = r['size_params'][0]
        tpi = r['performance']['time_per_iteration']
        ax.scatter(N, tpi * 1000, alpha=0.4, s=50, color='purple')  # Convert to ms

    ax.plot(sizes, [t*1000 for t in time_per_iter], 'o-', markersize=10, linewidth=2,
           color='darkviolet', label='Mean time/iteration')

    ax.set_xlabel('Number of Agents (N)', fontsize=14)
    ax.set_ylabel('Time per Iteration (ms)', fontsize=14)
    ax.set_title('DRPG Efficiency: Per-Iteration Cost', fontsize=16, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    plt.tight_layout()
    plt.savefig(output_dir / 'III1_time_per_iteration.pdf', dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\n✅ Figures saved to {output_dir}/")


def generate_table(results: Dict, scaling_analysis: Dict, output_path: Path):
    """Generate LaTeX table with scalability statistics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    size_stats = scaling_analysis['size_statistics']

    lines = []
    lines.append("\\begin{table}[h]")
    lines.append("\\centering")
    lines.append("\\caption{DRPG Scalability Analysis}")
    lines.append("\\begin{tabular}{cccccc}")
    lines.append("\\hline")
    lines.append("$N$ & Vars & $m$ & Mean Time (s) & Iters & Time/Iter (ms) \\\\")
    lines.append("\\hline")

    sizes = size_stats['sizes']
    mean_times = size_stats['mean_times']
    std_times = size_stats['std_times']
    mean_iters = size_stats['mean_iterations']
    mean_vars = size_stats['mean_vars']

    # Get resources from first result of each size
    size_to_m = {}
    for r in results['all_results']:
        N = r['size_params'][0]
        if N not in size_to_m:
            size_to_m[N] = r['problem_size']['n_resources']

    for i, N in enumerate(sizes):
        m = size_to_m.get(N, '-')
        t_mean = mean_times[i]
        t_std = std_times[i]
        iters = mean_iters[i]
        vars_total = int(mean_vars[i])
        time_per_iter = (t_mean / iters) * 1000  # ms

        lines.append(f"{N} & {vars_total} & {m} & "
                    f"{t_mean:.2f}$\\pm${t_std:.2f} & "
                    f"{iters:.1f} & {time_per_iter:.1f} \\\\")

    lines.append("\\hline")

    # Add scaling summary
    if 'runtime_vs_agents' in scaling_analysis:
        rt = scaling_analysis['runtime_vs_agents']
        lines.append(f"\\multicolumn{{6}}{{l}}{{Scaling: $t \\propto N^{{{rt['exponent']:.2f}}}$ "
                    f"($R^2$={rt['r_squared']:.3f})}} \\\\")

    lines.append("\\end{tabular}")
    lines.append("\\end{table}")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"\n✅ Table saved to {output_path}")


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("EXPERIMENT III.1: DRPG SCALABILITY ANALYSIS")
    print("="*70)

    # Configuration
    problem_sizes = [
        (5, 10, 3),      # Small (50 vars)
        (10, 15, 5),     # Medium (150 vars)
        (20, 15, 8),     # Large (300 vars)
        (50, 20, 10),    # Very large (1000 vars)
        # (100, 20, 15),   # Huge (2000 vars) - optional, may be slow
    ]

    n_runs = 3  # Fewer runs since larger problems take longer
    uncertainty_set = 'L2Ball'  # Most stable
    max_iters = 100

    # Run experiment
    logger = ExperimentLogger(
        "III.1_drpg_scalability",
        log_dir=Path(__file__).parent.parent.parent / "results" / "category_III",
        console_output=True,
    )

    logger.set_parameters({
        'problem_sizes': problem_sizes,
        'n_runs': n_runs,
        'uncertainty_set': uncertainty_set,
        'max_iters': max_iters,
    })

    results = run_experiment(
        problem_sizes=problem_sizes,
        n_runs_per_size=n_runs,
        uncertainty_set_type=uncertainty_set,
        max_iters=max_iters,
        logger=logger,
    )

    # Analyze scaling
    scaling_analysis = analyze_scaling(results)

    # Save results
    results['scaling_analysis'] = scaling_analysis

    saved_files = save_experiment_results(
        experiment_name="III1_drpg_scalability",
        category="III",
        results=results,
        save_formats=['json', 'pickle'],
    )

    # Generate figures
    figures_dir = Path(__file__).parent.parent.parent / "figures" / "category_III"
    generate_figures(results, scaling_analysis, figures_dir)

    # Generate table
    table_path = Path(__file__).parent.parent.parent / "tables" / "III1_drpg_scalability.tex"
    generate_table(results, scaling_analysis, table_path)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    if 'runtime_vs_agents' in scaling_analysis:
        rt = scaling_analysis['runtime_vs_agents']
        iter_scale = scaling_analysis.get('iterations_scaling', {})

        print(f"Runtime scaling: t ∝ N^{rt['exponent']:.2f} (R²={rt['r_squared']:.3f})")

        if 'exponent' in iter_scale:
            print(f"Iterations scaling: k ∝ N^{iter_scale['exponent']:.2f}")

        # Interpretation
        if rt['exponent'] < 2.5:
            complexity_class = "better than O(N²·⁵) - EXCELLENT"
        elif rt['exponent'] < 3.5:
            complexity_class = "approximately O(N³) - GOOD"
        elif rt['exponent'] < 4.5:
            complexity_class = "approximately O(N⁴) - ACCEPTABLE"
        else:
            complexity_class = "worse than O(N⁴) - CONCERNING"

        print(f"\nComplexity class: {complexity_class}")

        # Largest problem solved
        largest_N = max(scaling_analysis['size_statistics']['sizes'])
        idx = scaling_analysis['size_statistics']['sizes'].index(largest_N)
        largest_time = scaling_analysis['size_statistics']['mean_times'][idx]

        print(f"\nLargest problem tested: N={largest_N}")
        print(f"Solved in: {largest_time:.2f}s")

        # Extrapolation
        if largest_N < 100:
            t_100 = rt['constant'] * (100 ** rt['exponent'])
            print(f"\nExtrapolated time for N=100: {t_100:.1f}s ({t_100/60:.1f} min)")

        if rt['exponent'] < 3.5:
            print("\n✅ VALIDATION PASSED: DRPG scales well to realistic problem sizes")
        else:
            print("\n⚠️ VALIDATION PARTIAL: Scaling may limit very large problems")

    print("="*70)


if __name__ == "__main__":
    main()
