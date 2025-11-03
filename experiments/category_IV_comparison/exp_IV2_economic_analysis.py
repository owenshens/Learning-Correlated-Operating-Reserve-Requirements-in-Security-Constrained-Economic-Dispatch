"""
Experiment IV.2: Economic Analysis of Robust Solutions
=======================================================

Perform comprehensive economic analysis of all methods:
1. Out-of-sample performance evaluation
2. Value of Stochastic Solution (VSS)
3. Detailed Price of Robustness (PoR) analysis
4. Robustness vs cost trade-off curves

Uses results from Experiment IV.1 (method comparison) to analyze
economic properties of each solution.

Outputs:
- LaTeX tables for economic metrics
- CSV files for plotting trade-off curves
- Comprehensive analysis report
"""

import sys
import numpy as np
from pathlib import Path
import json
import time
from typing import Dict, List
import csv

# Add experiment root to path
experiment_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(experiment_root))

from core.problem_generator import generate_robust_qp
from core.uncertainty_sets import L2Ball, L1Ball, LinfBox
from core.economic_analysis import (
    OutOfSampleEvaluator,
    VSSComputer,
    EconomicAnalyzer
)
from core.baseline_solvers import NominalOptimization, ScenarioBasedRO, BertsimasSimBudgeted
from core.solvers import DRPG
from utils.logging_utils import ExperimentLogger


def load_method_comparison_results(results_dir: Path) -> List[Dict]:
    """Load results from Experiment IV.1."""
    results_file = results_dir / "method_comparison_results.json"
    if not results_file.exists():
        raise FileNotFoundError(
            f"Method comparison results not found at {results_file}. "
            "Run exp_IV1_method_comparison.py first!"
        )

    with open(results_file, 'r') as f:
        return json.load(f)


def run_economic_analysis_on_results(
    comparison_results: List[Dict],
    output_dir: Path,
    n_test_scenarios: int = 1000,
    sample_size: int = None,
):
    """
    Run economic analysis on existing method comparison results.

    Args:
        comparison_results: Results from exp_IV1
        output_dir: Where to save economic analysis results
        n_test_scenarios: Number of scenarios for out-of-sample evaluation
        sample_size: Number of problems to analyze (None = all)
    """
    # Initialize logger
    logger = ExperimentLogger(
        experiment_name="Economic_Analysis",
        log_dir=output_dir
    )

    logger.log("="*70)
    logger.log("EXPERIMENT IV.2: ECONOMIC ANALYSIS")
    logger.log("="*70)
    logger.log(f"\nTotal problems available: {len(comparison_results)}")

    if sample_size:
        logger.log(f"Analyzing sample of: {sample_size} problems")
        # Sample evenly across problem configurations
        indices = np.linspace(0, len(comparison_results)-1, sample_size, dtype=int)
        comparison_results = [comparison_results[i] for i in indices]
    else:
        logger.log(f"Analyzing all problems")

    # Storage for economic results
    economic_results = []

    # Process each problem
    for idx, exp_result in enumerate(comparison_results):
        logger.log(f"\n{'='*70}")
        logger.log(f"Problem {idx+1}/{len(comparison_results)}")
        logger.log(f"{'='*70}")

        # Extract problem configuration
        problem_config = exp_result['problem_config']
        uncertainty_config = exp_result['uncertainty_config']

        logger.log(f"  Size: N={problem_config['n_agents']}, "
                  f"vars≈{problem_config['n_agents'] * problem_config['avg_vars_per_agent']}")
        logger.log(f"  Uncertainty: {uncertainty_config['set_type']}, "
                  f"ρ_p={uncertainty_config['radius_p']}, ρ_c={uncertainty_config['radius_c']}")

        # Regenerate problem (same seed gives same problem)
        problem = generate_robust_qp(**problem_config)

        # Create uncertainty sets
        set_type = uncertainty_config['set_type']
        if set_type == "L2Ball":
            uset_p = L2Ball(dim=problem.n_factors_p, radius=uncertainty_config['radius_p'])
            uset_c = L2Ball(dim=problem.n_factors_c, radius=uncertainty_config['radius_c'])
        elif set_type == "L1Ball":
            uset_p = L1Ball(dim=problem.n_factors_p, radius=uncertainty_config['radius_p'])
            uset_c = L1Ball(dim=problem.n_factors_c, radius=uncertainty_config['radius_c'])
        elif set_type == "LinfBox":
            uset_p = LinfBox(dim=problem.n_factors_p, radius=uncertainty_config['radius_p'])
            uset_c = LinfBox(dim=problem.n_factors_c, radius=uncertainty_config['radius_c'])
        else:
            raise ValueError(f"Unknown set type: {set_type}")

        # Get solutions from Phase 3 results
        solutions = {}
        methods_to_analyze = []

        for method in ['nominal', 'scenario', 'drpg']:
            if method in exp_result['results']:
                result = exp_result['results'][method]
                if result['converged']:
                    # Reconstruct solution
                    if method == 'drpg':
                        # For DRPG, we need to re-solve (solutions not stored in Phase 3)
                        logger.log(f"  Re-solving {method}...")
                        solver = DRPG(outer_tolerance=1e-4, max_outer_iterations=100, verbose=False)
                        drpg_result = solver.solve(problem, uset_p, uset_c)
                        if drpg_result.converged:
                            x_sol = np.concatenate(drpg_result.x_blocks)
                            solutions[method] = x_sol
                            methods_to_analyze.append(method)
                    else:
                        # For nominal and scenario, re-solve quickly
                        logger.log(f"  Re-solving {method}...")
                        if method == 'nominal':
                            solver = NominalOptimization(verbose=False)
                        elif method == 'scenario':
                            solver = ScenarioBasedRO(
                                scenario_generation="grid",
                                n_scenarios_p=10,
                                n_scenarios_c=10,
                                verbose=False
                            )

                        sol_result = solver.solve(problem, uset_p, uset_c)
                        if sol_result.converged:
                            solutions[method] = sol_result.x_solution
                            methods_to_analyze.append(method)

        if 'nominal' not in solutions:
            logger.log("  ⚠️  Skipping: nominal solution required for economic analysis")
            continue

        # Perform economic analysis
        logger.log(f"\n  Performing economic analysis on {len(methods_to_analyze)} methods...")

        analyzer = EconomicAnalyzer(
            n_test_scenarios=n_test_scenarios,
            n_vss_scenarios=n_test_scenarios,
            seed=42 + idx,
            verbose=False
        )

        problem_economic_results = {
            'experiment_id': exp_result['experiment_id'],
            'problem_config': problem_config,
            'uncertainty_config': uncertainty_config,
            'methods': {}
        }

        x_nominal = solutions['nominal']

        for method in methods_to_analyze:
            if method == 'nominal':
                # For nominal, just do out-of-sample (no VSS vs itself)
                evaluator = OutOfSampleEvaluator(
                    n_test_scenarios=n_test_scenarios,
                    scenario_generation="random",
                    seed=42 + idx,
                    verbose=False
                )
                oos_result = evaluator.evaluate(
                    method_name=method,
                    x_solution=solutions[method],
                    problem=problem,
                    uset_p=uset_p,
                    uset_c=uset_c,
                    x_nominal=x_nominal
                )

                problem_economic_results['methods'][method] = {
                    'out_of_sample': {
                        'mean_cost': oos_result.mean_cost,
                        'std_cost': oos_result.std_cost,
                        'worst_case': oos_result.worst_case_cost,
                        'best_case': oos_result.best_case_cost,
                        'median_cost': oos_result.median_cost,
                        'percentile_95': oos_result.percentile_95,
                        'percentile_99': oos_result.percentile_99,
                        'feasibility_rate': oos_result.feasibility_rate,
                    }
                }

                logger.log(f"    {method.capitalize()}: Mean=${oos_result.mean_cost:.2f}, "
                          f"Worst=${oos_result.worst_case_cost:.2f}, Std=${oos_result.std_cost:.2f}")

            else:
                # For robust methods, full economic analysis
                analysis = analyzer.analyze_method(
                    method_name=method,
                    x_solution=solutions[method],
                    x_nominal=x_nominal,
                    problem=problem,
                    uset_p=uset_p,
                    uset_c=uset_c
                )

                oos = analysis['out_of_sample']
                vss = analysis['vss']

                problem_economic_results['methods'][method] = {
                    'out_of_sample': {
                        'mean_cost': oos.mean_cost,
                        'std_cost': oos.std_cost,
                        'worst_case': oos.worst_case_cost,
                        'best_case': oos.best_case_cost,
                        'median_cost': oos.median_cost,
                        'percentile_95': oos.percentile_95,
                        'percentile_99': oos.percentile_99,
                        'feasibility_rate': oos.feasibility_rate,
                        'cost_increase_vs_nominal': oos.cost_increase_vs_nominal,
                    },
                    'vss': {
                        'vss_value': float(vss.vss_value),
                        'vss_percentage': float(vss.vss_percentage),
                        'worst_case_improvement': float(vss.worst_case_improvement),
                        'is_significant': int(vss.is_significant),  # Convert bool to int for JSON
                        'p_value': float(vss.p_value) if vss.p_value is not None else None,
                    }
                }

                logger.log(f"    {method.capitalize()}: Mean=${oos.mean_cost:.2f}, "
                          f"Worst=${oos.worst_case_cost:.2f}, VSS={vss.vss_percentage:.3f}%")

        economic_results.append(problem_economic_results)

        # Save intermediate results every 10 problems
        if (idx + 1) % 10 == 0:
            output_file = output_dir / "economic_analysis_results.json"
            with open(output_file, 'w') as f:
                json.dump(economic_results, f, indent=2)
            logger.log(f"\n  Saved intermediate results ({idx+1} problems)")

    # Final save
    output_file = output_dir / "economic_analysis_results.json"
    with open(output_file, 'w') as f:
        json.dump(economic_results, f, indent=2)

    logger.log(f"\n{'='*70}")
    logger.log("ECONOMIC ANALYSIS COMPLETE")
    logger.log(f"{'='*70}")
    logger.log(f"\nAnalyzed {len(economic_results)} problems")
    logger.log(f"Results saved to: {output_file}")

    return economic_results


def generate_economic_tables(economic_results: List[Dict], output_dir: Path):
    """Generate LaTeX tables for economic metrics."""

    print("\n" + "="*70)
    print("GENERATING ECONOMIC TABLES")
    print("="*70)

    # Aggregate results by method
    methods = ['nominal', 'scenario', 'drpg']
    aggregated = {m: {
        'mean_costs': [],
        'worst_cases': [],
        'std_costs': [],
        'vss_values': [],
        'vss_percentages': [],
        'worst_improvements': [],
    } for m in methods}

    for exp in economic_results:
        for method in methods:
            if method in exp['methods']:
                data = exp['methods'][method]

                if 'out_of_sample' in data:
                    oos = data['out_of_sample']
                    aggregated[method]['mean_costs'].append(oos['mean_cost'])
                    aggregated[method]['worst_cases'].append(oos['worst_case'])
                    aggregated[method]['std_costs'].append(oos['std_cost'])

                if 'vss' in data:
                    vss = data['vss']
                    aggregated[method]['vss_values'].append(vss['vss_value'])
                    aggregated[method]['vss_percentages'].append(vss['vss_percentage'])
                    aggregated[method]['worst_improvements'].append(vss['worst_case_improvement'])

    # Table 1: Out-of-Sample Performance
    table1 = r"""
\begin{table}[t]
\centering
\caption{Out-of-Sample Performance Evaluation}
\label{tab:oos_performance}
\begin{tabular}{lrrrr}
\toprule
\textbf{Method} & \textbf{Mean Cost} & \textbf{Worst-case} & \textbf{Std Dev} & \textbf{CoV} \\
\midrule
"""

    methods_display = {
        'nominal': 'Nominal (u=0)',
        'scenario': 'Scenario-Based RO',
        'drpg': 'DRPG (Ours)'
    }

    for method in methods:
        if len(aggregated[method]['mean_costs']) > 0:
            mean_cost = np.mean(aggregated[method]['mean_costs'])
            mean_worst = np.mean(aggregated[method]['worst_cases'])
            mean_std = np.mean(aggregated[method]['std_costs'])
            cov = mean_std / abs(mean_cost) * 100  # Coefficient of variation

            table1 += f"{methods_display[method]:<22} & "
            table1 += f"${-mean_cost:.0f} & "
            table1 += f"${-mean_worst:.0f} & "
            table1 += f"${mean_std:.2f} & "
            table1 += f"{cov:.2f}\\% \\\\\\\n"

    table1 += r"""\bottomrule
\end{tabular}
\end{table}

% Note: Negative values shown for cost minimization.
% CoV = Coefficient of Variation (Std/Mean × 100%)
"""

    # Save Table 1
    table1_file = output_dir / "table_oos_performance.tex"
    with open(table1_file, 'w') as f:
        f.write(table1)
    print(f"✓ Generated: {table1_file}")

    # Table 2: Value of Stochastic Solution
    table2 = r"""
\begin{table}[t]
\centering
\caption{Value of Stochastic Solution (VSS) Analysis}
\label{tab:vss_analysis}
\begin{tabular}{lrrr}
\toprule
\textbf{Method} & \textbf{VSS (\$)} & \textbf{VSS (\%)} & \textbf{Worst-case Imp. (\%)} \\
\midrule
"""

    for method in ['scenario', 'drpg']:  # Only robust methods have VSS
        if len(aggregated[method]['vss_values']) > 0:
            mean_vss = np.mean(aggregated[method]['vss_values'])
            mean_vss_pct = np.mean(aggregated[method]['vss_percentages'])
            mean_worst_imp = np.mean(aggregated[method]['worst_improvements'])

            table2 += f"{methods_display[method]:<22} & "
            table2 += f"${mean_vss:.2f} & "
            table2 += f"{mean_vss_pct:+.3f}\\% & "
            table2 += f"{mean_worst_imp:+.3f}\\% \\\\\\\n"

    table2 += r"""\bottomrule
\end{tabular}
\end{table}

% VSS = Expected cost improvement over nominal solution
% Worst-case Imp. = Robust worst-case improvement over nominal worst-case
"""

    # Save Table 2
    table2_file = output_dir / "table_vss_analysis.tex"
    with open(table2_file, 'w') as f:
        f.write(table2)
    print(f"✓ Generated: {table2_file}")

    # CSV for plotting
    csv_file = output_dir / "economic_metrics.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Method', 'Mean_Cost', 'Worst_Case', 'Std_Cost', 'VSS_Value', 'VSS_Percent', 'Worst_Improvement'])

        for method in methods:
            if len(aggregated[method]['mean_costs']) > 0:
                mean_cost = np.mean(aggregated[method]['mean_costs'])
                mean_worst = np.mean(aggregated[method]['worst_cases'])
                mean_std = np.mean(aggregated[method]['std_costs'])
                vss_val = np.mean(aggregated[method]['vss_values']) if aggregated[method]['vss_values'] else np.nan
                vss_pct = np.mean(aggregated[method]['vss_percentages']) if aggregated[method]['vss_percentages'] else np.nan
                worst_imp = np.mean(aggregated[method]['worst_improvements']) if aggregated[method]['worst_improvements'] else np.nan

                writer.writerow([method, mean_cost, mean_worst, mean_std, vss_val, vss_pct, worst_imp])

    print(f"✓ Generated: {csv_file}")


def main():
    """Main analysis pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Run economic analysis')
    parser.add_argument('--sample', type=int, default=None, help='Sample size (None = all)')
    parser.add_argument('--scenarios', type=int, default=1000, help='Number of test scenarios')
    args = parser.parse_args()

    # Setup paths
    results_dir = Path(__file__).parent / "results"
    output_dir = results_dir  # Same directory as Phase 3 results

    # Load Phase 3 results
    print("Loading method comparison results from Experiment IV.1...")
    try:
        comparison_results = load_method_comparison_results(results_dir)
        print(f"✓ Loaded {len(comparison_results)} problem results")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return 1

    # Run economic analysis
    print(f"\nRunning economic analysis...")
    print(f"  Test scenarios per problem: {args.scenarios}")
    if args.sample:
        print(f"  Analyzing sample of: {args.sample} problems")
    else:
        print(f"  Analyzing all {len(comparison_results)} problems")

    economic_results = run_economic_analysis_on_results(
        comparison_results=comparison_results,
        output_dir=output_dir,
        n_test_scenarios=args.scenarios,
        sample_size=args.sample
    )

    # Generate tables
    generate_economic_tables(economic_results, output_dir)

    print("\n" + "="*70)
    print("✅ ECONOMIC ANALYSIS COMPLETE")
    print("="*70)
    print(f"\nOutputs in: {output_dir}")
    print("  - economic_analysis_results.json")
    print("  - table_oos_performance.tex")
    print("  - table_vss_analysis.tex")
    print("  - economic_metrics.csv")

    return 0


if __name__ == '__main__':
    exit(main())
