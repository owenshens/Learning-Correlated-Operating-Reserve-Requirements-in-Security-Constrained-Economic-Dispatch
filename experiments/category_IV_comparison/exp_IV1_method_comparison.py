"""
Experiment IV.1: Comprehensive Method Comparison
================================================

Compare DRPG against baseline robust optimization methods:
- Nominal optimization (u=0)
- Scenario-based robust optimization
- Bertsimas-Sim budgeted uncertainty

Performance Metrics:
- Solution quality (worst-case objective)
- Computational efficiency (solve time, iterations)
- Robustness (out-of-sample performance)
- Scalability (performance vs problem size)

Experimental Design:
- Problem sizes: N ∈ {5, 10, 20} agents
- Uncertainty sets: L2Ball, L1Ball, LinfBox
- Uncertainty radii: ρ ∈ {0.10, 0.15, 0.20}
- Replications: 3 per configuration

Total experiments: 3 sizes × 3 sets × 3 radii × 3 reps = 81 problems × 4 methods = 324 runs
"""

import sys
import numpy as np
from pathlib import Path
import time
import json
from typing import Dict, List, Tuple

# Add experiment root to path
experiment_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(experiment_root))

from core.problem_generator import generate_robust_qp
from core.uncertainty_sets import L2Ball, L1Ball, LinfBox, create_uncertainty_set
from core.baseline_solvers import (
    NominalOptimization,
    ScenarioBasedRO,
    BertsimasSimBudgeted,
    BaselineResult
)
from core.solvers import DRPG
from utils.logging_utils import ExperimentLogger


def create_uncertainty_set_pair(
    set_type: str,
    dim_p: int,
    dim_c: int,
    radius_p: float,
    radius_c: float,
):
    """Create matched pair of uncertainty sets."""
    if set_type == "L2Ball":
        uset_p = L2Ball(dim=dim_p, radius=radius_p)
        uset_c = L2Ball(dim=dim_c, radius=radius_c)
    elif set_type == "L1Ball":
        uset_p = L1Ball(dim=dim_p, radius=radius_p)
        uset_c = L1Ball(dim=dim_c, radius=radius_c)
    elif set_type == "LinfBox":
        uset_p = LinfBox(dim=dim_p, radius=radius_p)
        uset_c = LinfBox(dim=dim_c, radius=radius_c)
    else:
        raise ValueError(f"Unknown set type: {set_type}")

    return uset_p, uset_c


def run_single_comparison(
    problem_config: Dict,
    uncertainty_config: Dict,
    methods: List[str],
    verbose: bool = False,
) -> Dict:
    """
    Run all methods on a single problem instance.

    Args:
        problem_config: Problem generation parameters
        uncertainty_config: Uncertainty set configuration
        methods: List of methods to run
        verbose: Print detailed progress

    Returns:
        Dictionary of results for each method
    """
    # Generate problem
    problem = generate_robust_qp(**problem_config)

    # Create uncertainty sets
    uset_p, uset_c = create_uncertainty_set_pair(
        set_type=uncertainty_config['set_type'],
        dim_p=problem.n_factors_p,
        dim_c=problem.n_factors_c,
        radius_p=uncertainty_config['radius_p'],
        radius_c=uncertainty_config['radius_c'],
    )

    results = {}

    # Run each method
    for method in methods:
        if verbose:
            print(f"    Running {method}...", end=" ", flush=True)

        try:
            if method == "nominal":
                solver = NominalOptimization(verbose=False)
                result = solver.solve(problem, uset_p, uset_c)

            elif method == "scenario":
                solver = ScenarioBasedRO(
                    scenario_generation="grid",
                    n_scenarios_p=10,
                    n_scenarios_c=10,
                    verbose=False
                )
                result = solver.solve(problem, uset_p, uset_c)

            elif method == "budgeted":
                solver = BertsimasSimBudgeted(
                    budget_p=problem.n_factors_p / 2.0,
                    budget_c=problem.n_factors_c / 2.0,
                    verbose=False
                )
                result = solver.solve(problem, uset_p, uset_c)

            elif method == "drpg":
                solver = DRPG(
                    outer_tolerance=1e-4,
                    max_outer_iterations=100,
                    verbose=False
                )
                drpg_result = solver.solve(problem, uset_p, uset_c)

                # Convert to BaselineResult format
                result = BaselineResult(
                    method_name="DRPG",
                    objective_value=-drpg_result.worst_case_value,
                    solve_time=drpg_result.solve_time,
                    converged=drpg_result.converged,
                    iterations=drpg_result.outer_iterations,
                    x_solution=np.concatenate(drpg_result.x_blocks),
                    worst_case_u_p=drpg_result.u_p_optimal,
                    worst_case_u_c=drpg_result.u_c_optimal,
                    metadata={
                        'total_inner_iterations': drpg_result.total_inner_iterations
                    }
                )

            else:
                raise ValueError(f"Unknown method: {method}")

            results[method] = {
                'converged': result.converged,
                'objective': result.objective_value,
                'solve_time': result.solve_time,
                'iterations': result.iterations,
                'worst_case_u_p': result.worst_case_u_p.tolist() if result.worst_case_u_p is not None else None,
                'worst_case_u_c': result.worst_case_u_c.tolist() if result.worst_case_u_c is not None else None,
                'metadata': result.metadata or {}
            }

            if verbose:
                if result.converged:
                    print(f"✓ obj=${-result.objective_value:.2f}, t={result.solve_time:.3f}s")
                else:
                    print(f"✗ Failed")

        except Exception as e:
            print(f"✗ Error: {e}")
            results[method] = {
                'converged': False,
                'objective': np.inf,
                'solve_time': 0.0,
                'iterations': 0,
                'error': str(e)
            }

    return results


def run_comprehensive_comparison(
    output_dir: Path = None,
    quick_test: bool = False,
):
    """
    Run comprehensive comparison across all configurations.

    Args:
        output_dir: Where to save results
        quick_test: If True, run reduced test matrix (faster)
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize logger
    logger = ExperimentLogger(
        experiment_name="Method_Comparison",
        log_dir=output_dir
    )

    logger.log("="*70)
    logger.log("EXPERIMENT IV.1: COMPREHENSIVE METHOD COMPARISON")
    logger.log("="*70)

    # Define experimental design
    if quick_test:
        # Reduced for fast testing
        problem_sizes = [(5, 10, 2)]  # (n_agents, avg_vars, n_resources)
        uncertainty_sets = ["L2Ball"]
        uncertainty_radii = [(0.15, 0.10)]  # (radius_p, radius_c)
        n_replications = 1
    else:
        # Full experimental design
        problem_sizes = [
            (5, 10, 2),    # Small: 5 agents, 50 vars
            (10, 10, 3),   # Medium: 10 agents, 100 vars
            (20, 10, 5),   # Large: 20 agents, 200 vars
        ]
        uncertainty_sets = ["L2Ball", "L1Ball", "LinfBox"]
        uncertainty_radii = [
            (0.10, 0.05),  # Low uncertainty
            (0.15, 0.10),  # Baseline (from Phase 2)
            (0.20, 0.15),  # High uncertainty
        ]
        n_replications = 3

    methods = ["nominal", "scenario", "budgeted", "drpg"]

    # Calculate total experiments
    n_configs = len(problem_sizes) * len(uncertainty_sets) * len(uncertainty_radii)
    total_experiments = n_configs * n_replications * len(methods)

    logger.log(f"\nExperimental Design:")
    logger.log(f"  Problem sizes: {len(problem_sizes)}")
    logger.log(f"  Uncertainty sets: {len(uncertainty_sets)}")
    logger.log(f"  Uncertainty radii: {len(uncertainty_radii)}")
    logger.log(f"  Replications: {n_replications}")
    logger.log(f"  Methods: {len(methods)}")
    logger.log(f"  Total configurations: {n_configs}")
    logger.log(f"  Total method runs: {total_experiments}")

    # Storage for all results
    all_results = []
    experiment_idx = 0

    # Main experimental loop
    for size_config in problem_sizes:
        n_agents, avg_vars, n_resources = size_config

        for set_type in uncertainty_sets:
            for radius_p, radius_c in uncertainty_radii:
                for rep in range(n_replications):
                    experiment_idx += 1

                    # Create problem configuration
                    problem_config = {
                        'n_agents': n_agents,
                        'avg_vars_per_agent': avg_vars,
                        'n_resources': n_resources,
                        'n_factors_p': 3,
                        'n_factors_c': 2,
                        'uncertainty_radius_p': radius_p,
                        'uncertainty_radius_c': radius_c,
                        'seed': 42 + rep,
                        'problem_type': 'energy'
                    }

                    uncertainty_config = {
                        'set_type': set_type,
                        'radius_p': radius_p,
                        'radius_c': radius_c,
                    }

                    # Log progress
                    logger.log(f"\n{'='*70}")
                    logger.log(f"Experiment {experiment_idx}/{n_configs * n_replications}")
                    logger.log(f"{'='*70}")
                    logger.log(f"  Problem: N={n_agents}, vars≈{n_agents*avg_vars}, resources={n_resources}")
                    logger.log(f"  Uncertainty: {set_type}, ρ_p={radius_p}, ρ_c={radius_c}")
                    logger.log(f"  Replication: {rep + 1}/{n_replications}")

                    # Run comparison
                    results = run_single_comparison(
                        problem_config=problem_config,
                        uncertainty_config=uncertainty_config,
                        methods=methods,
                        verbose=True
                    )

                    # Store results
                    experiment_record = {
                        'experiment_id': experiment_idx,
                        'problem_config': problem_config,
                        'uncertainty_config': uncertainty_config,
                        'replication': rep,
                        'results': results
                    }
                    all_results.append(experiment_record)

                    # Save intermediate results
                    if experiment_idx % 10 == 0:
                        output_file = output_dir / "method_comparison_results.json"
                        with open(output_file, 'w') as f:
                            json.dump(all_results, f, indent=2)

    # Final save
    output_file = output_dir / "method_comparison_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    logger.log(f"\n{'='*70}")
    logger.log("EXPERIMENT COMPLETE")
    logger.log(f"{'='*70}")
    logger.log(f"\nResults saved to: {output_file}")

    # Generate summary statistics
    generate_summary(all_results, logger, output_dir)

    return all_results


def generate_summary(all_results: List[Dict], logger: ExperimentLogger, output_dir: Path):
    """Generate summary statistics and tables."""
    logger.log(f"\n{'='*70}")
    logger.log("SUMMARY STATISTICS")
    logger.log(f"{'='*70}")

    methods = ["nominal", "scenario", "budgeted", "drpg"]

    # Aggregate by method
    method_stats = {m: {'objectives': [], 'times': [], 'iterations': [], 'converged': []}
                    for m in methods}

    for exp in all_results:
        for method in methods:
            if method in exp['results']:
                result = exp['results'][method]
                if result['converged']:
                    method_stats[method]['objectives'].append(result['objective'])
                    method_stats[method]['times'].append(result['solve_time'])
                    method_stats[method]['iterations'].append(result['iterations'])
                    method_stats[method]['converged'].append(1)
                else:
                    method_stats[method]['converged'].append(0)

    # Compute statistics
    logger.log(f"\n{'Method':<15} {'Mean Obj':<12} {'Mean Time (s)':<15} {'Mean Iters':<12} {'Success Rate':<12}")
    logger.log("-"*70)

    for method in methods:
        stats = method_stats[method]
        if len(stats['objectives']) > 0:
            mean_obj = np.mean(stats['objectives'])
            mean_time = np.mean(stats['times'])
            mean_iters = np.mean(stats['iterations'])
            success_rate = np.mean(stats['converged']) * 100
        else:
            mean_obj = np.nan
            mean_time = np.nan
            mean_iters = np.nan
            success_rate = 0.0

        logger.log(f"{method.capitalize():<15} ${-mean_obj:<11.2f} {mean_time:<15.4f} {mean_iters:<12.1f} {success_rate:<11.1f}%")

    # Save summary to CSV
    import csv
    summary_file = output_dir / "method_comparison_summary.csv"
    with open(summary_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Method', 'Mean_Objective', 'Mean_Time', 'Mean_Iterations', 'Success_Rate'])
        for method in methods:
            stats = method_stats[method]
            if len(stats['objectives']) > 0:
                writer.writerow([
                    method,
                    np.mean(stats['objectives']),
                    np.mean(stats['times']),
                    np.mean(stats['iterations']),
                    np.mean(stats['converged']) * 100
                ])

    logger.log(f"\nSummary CSV saved to: {summary_file}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run comprehensive method comparison')
    parser.add_argument('--quick', action='store_true', help='Run quick test (reduced matrix)')
    parser.add_argument('--output', type=str, default=None, help='Output directory')

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else None

    # Run experiments
    results = run_comprehensive_comparison(
        output_dir=output_dir,
        quick_test=args.quick
    )

    print(f"\n{'='*70}")
    print("✅ COMPREHENSIVE METHOD COMPARISON COMPLETE")
    print(f"{'='*70}")
