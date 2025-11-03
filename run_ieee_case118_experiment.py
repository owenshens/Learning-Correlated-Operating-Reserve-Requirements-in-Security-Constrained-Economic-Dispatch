"""
IEEE Case118 Comprehensive Experiment
======================================

Run DRPG and baseline methods on IEEE case118 and generate visualizations.
"""

import sys
import numpy as np
from pathlib import Path
import time
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, str(Path(__file__).parent))

from core.ieee_problem_generator import generate_ieee_calibrated_qp
from core.uncertainty_sets import L2Ball
from core.baseline_solvers import (
    NominalOptimization,
    ScenarioBasedRO,
)
from core.solvers import DRPG, DirectNominalSolver

# Publication style
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 13,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
})

# Colors (colorblind-friendly)
COLORS = {
    'nominal': '#0173B2',   # Blue
    'scenario': '#DE8F05',  # Orange
    'drpg': '#029E73',      # Green
}

def run_ieee_case118_experiment():
    """Run comprehensive experiment on IEEE case118."""

    print("="*80)
    print("IEEE CASE118 COMPREHENSIVE EXPERIMENT")
    print("="*80)

    # Generate IEEE case118 problem
    print("\n[1/4] Generating IEEE case118 problem...")
    problem = generate_ieee_calibrated_qp(
        ieee_case='case118',
        n_factors_p=3,
        n_factors_c=2,
        uncertainty_radius_p=0.15,  # ±15% load uncertainty
        uncertainty_radius_c=0.10,  # ±10% network uncertainty
        seed=42
    )

    print(f"  ✓ Problem generated:")
    print(f"    Generators (agents): {problem.n_agents}")
    print(f"    Total variables: {sum(problem.n_vars)}")
    print(f"    Resources (constraints): {problem.n_resources}")
    print(f"    Uncertainty factors: P={problem.n_factors_p}, C={problem.n_factors_c}")

    # Create uncertainty sets
    uset_p = L2Ball(dim=problem.n_factors_p, radius=problem.uncertainty_radius_p)
    uset_c = L2Ball(dim=problem.n_factors_c, radius=problem.uncertainty_radius_c)

    results = {}

    # [2/4] Run Nominal
    print("\n[2/4] Running Nominal optimization...")
    try:
        nominal_solver = NominalOptimization(verbose=False)
        start = time.time()
        nominal_result = nominal_solver.solve(problem, uset_p, uset_c)
        nominal_time = time.time() - start

        results['nominal'] = {
            'converged': nominal_result.converged,
            'objective': float(nominal_result.objective_value),
            'solve_time': nominal_time,
            'iterations': nominal_result.iterations,
        }
        print(f"  ✓ Nominal: Objective=${-nominal_result.objective_value:.2f}, Time={nominal_time:.3f}s")
    except Exception as e:
        print(f"  ✗ Nominal failed: {e}")
        results['nominal'] = {'converged': False, 'error': str(e)}

    # [3/4] Run Scenario-based RO
    print("\n[3/4] Running Scenario-based RO...")
    try:
        scenario_solver = ScenarioBasedRO(
            scenario_generation="grid",
            n_scenarios_p=10,
            n_scenarios_c=10,
            verbose=False
        )
        start = time.time()
        scenario_result = scenario_solver.solve(problem, uset_p, uset_c)
        scenario_time = time.time() - start

        results['scenario'] = {
            'converged': scenario_result.converged,
            'objective': float(scenario_result.objective_value),
            'solve_time': scenario_time,
            'iterations': scenario_result.iterations,
        }
        print(f"  ✓ Scenario: Objective=${-scenario_result.objective_value:.2f}, Time={scenario_time:.3f}s")
    except Exception as e:
        print(f"  ✗ Scenario failed: {e}")
        results['scenario'] = {'converged': False, 'error': str(e)}

    # [4/4] Run DRPG
    print("\n[4/4] Running DRPG...")
    try:
        drpg_solver = DRPG(
            max_outer_iterations=100,
            outer_tolerance=1e-4,
            verbose=True
        )
        start = time.time()
        drpg_result = drpg_solver.solve(problem, uset_p, uset_c)
        drpg_time = time.time() - start

        results['drpg'] = {
            'converged': drpg_result.converged,
            'objective': float(-drpg_result.worst_case_value),  # Convert to minimization
            'solve_time': drpg_time,
            'iterations': drpg_result.outer_iterations,
            'total_inner_iterations': drpg_result.total_inner_iterations,
            'convergence_history': {
                'outer_iterations': list(range(drpg_result.outer_iterations + 1)),
                'worst_case_values': [float(v) for v in drpg_result.history.get('V_values', [])],
                'gradient_norms': [float(g) for g in drpg_result.history.get('gradient_norms', [])],
            }
        }
        print(f"  ✓ DRPG: Objective=${-drpg_result.worst_case_value:.2f}, Time={drpg_time:.3f}s")
        print(f"    Iterations: {drpg_result.outer_iterations}, Inner: {drpg_result.total_inner_iterations}")
    except Exception as e:
        print(f"  ✗ DRPG failed: {e}")
        import traceback
        traceback.print_exc()
        results['drpg'] = {'converged': False, 'error': str(e)}

    # Compute Price of Robustness
    if results['nominal']['converged'] and results['drpg']['converged']:
        nominal_obj = results['nominal']['objective']
        drpg_obj = results['drpg']['objective']
        por = (nominal_obj - drpg_obj) / abs(nominal_obj) * 100
        results['price_of_robustness'] = float(por)
        print(f"\n  Price of Robustness: {por:.2f}%")

    # Save results
    output_dir = Path(__file__).parent / "results" / "ieee_experiments"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "ieee_case118_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'problem_info': {
                'case': 'case118',
                'n_agents': problem.n_agents,
                'n_vars': sum(problem.n_vars),
                'n_resources': problem.n_resources,
                'n_factors_p': problem.n_factors_p,
                'n_factors_c': problem.n_factors_c,
                'uncertainty_radius_p': problem.uncertainty_radius_p,
                'uncertainty_radius_c': problem.uncertainty_radius_c,
            },
            'results': results
        }, f, indent=2)

    print(f"\n✓ Results saved to: {output_file}")

    return results, output_dir


def generate_visualizations(results, output_dir):
    """Generate comprehensive visualizations."""

    print("\n" + "="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)

    # Create figure directory
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(exist_ok=True)

    # Figure 1: Method Comparison (2 panels)
    print("\n[1/3] Generating method comparison figure...")
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.5))

    # Panel A: Objective values
    ax = axes[0]
    methods = []
    objectives = []
    colors = []

    for method in ['nominal', 'scenario', 'drpg']:
        if method in results and results[method]['converged']:
            methods.append(method.capitalize())
            objectives.append(-results[method]['objective'])  # Negate for maximization
            colors.append(COLORS[method])

    bars = ax.bar(methods, objectives, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
    ax.set_ylabel('Objective Value ($)')
    ax.set_title('(A) Solution Quality')
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:,.0f}',
                ha='center', va='bottom', fontsize=8)

    # Panel B: Solve times
    ax = axes[1]
    times = []

    for method in ['nominal', 'scenario', 'drpg']:
        if method in results and results[method]['converged']:
            times.append(results[method]['solve_time'])

    bars = ax.bar(methods, times, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
    ax.set_ylabel('Solve Time (s)')
    ax.set_title('(B) Computational Efficiency')
    ax.set_yscale('log')
    ax.grid(axis='y', alpha=0.3, linestyle='--', which='both')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s',
                ha='center', va='bottom', fontsize=8)

    plt.tight_layout()

    # Save
    for ext in ['pdf', 'png']:
        fig.savefig(fig_dir / f"ieee_case118_comparison.{ext}", dpi=600 if ext=='png' else None)
    print(f"  ✓ Saved: {fig_dir / 'ieee_case118_comparison.pdf'}")
    plt.close()

    # Figure 2: DRPG Convergence (if available)
    if 'drpg' in results and results['drpg']['converged'] and 'convergence_history' in results['drpg']:
        print("\n[2/3] Generating DRPG convergence figure...")

        history = results['drpg']['convergence_history']
        iterations = history['outer_iterations']
        V_values = history['worst_case_values']
        gradient_norms = history['gradient_norms']

        fig, axes = plt.subplots(1, 2, figsize=(8, 3.5))

        # Panel A: Worst-case value convergence
        ax = axes[0]
        # V_values has length outer_iterations + 1 (includes initial)
        iters_plot = iterations[:len(V_values)]
        ax.plot(iters_plot, [-v for v in V_values], 'o-', color=COLORS['drpg'],
                linewidth=2, markersize=5, label='Worst-case value')
        ax.set_xlabel('Outer Iteration')
        ax.set_ylabel('Worst-Case Objective ($)')
        ax.set_title('(A) Objective Convergence')
        ax.grid(alpha=0.3, linestyle='--')
        ax.legend()

        # Panel B: Gradient norm (adversarial search intensity)
        ax = axes[1]
        # Gradient norms has length outer_iterations (one per iteration, not including final)
        grad_iters = iterations[:len(gradient_norms)]
        ax.semilogy(grad_iters, gradient_norms, 'o-', color=COLORS['drpg'],
                    linewidth=2, markersize=5, label='Gradient norm')
        ax.set_xlabel('Outer Iteration')
        ax.set_ylabel('Gradient Norm (log scale)')
        ax.set_title('(B) Adversarial Search Intensity')
        ax.grid(alpha=0.3, linestyle='--', which='both')
        ax.legend()

        plt.tight_layout()

        # Save
        for ext in ['pdf', 'png']:
            fig.savefig(fig_dir / f"ieee_case118_drpg_convergence.{ext}", dpi=600 if ext=='png' else None)
        print(f"  ✓ Saved: {fig_dir / 'ieee_case118_drpg_convergence.pdf'}")
        plt.close()

    # Figure 3: Summary Statistics
    print("\n[3/3] Generating summary statistics table...")

    fig, ax = plt.subplots(1, 1, figsize=(7, 2.5))
    ax.axis('tight')
    ax.axis('off')

    # Create table data
    table_data = [['Method', 'Objective ($)', 'Solve Time (s)', 'Iterations', 'Status']]

    for method in ['nominal', 'scenario', 'drpg']:
        if method in results:
            if results[method]['converged']:
                row = [
                    method.capitalize(),
                    f"${-results[method]['objective']:,.2f}",
                    f"{results[method]['solve_time']:.3f}",
                    f"{results[method].get('iterations', 'N/A')}",
                    '✓ Converged'
                ]
            else:
                row = [method.capitalize(), 'N/A', 'N/A', 'N/A', '✗ Failed']
            table_data.append(row)

    # Add PoR if available
    if 'price_of_robustness' in results:
        table_data.append(['', '', '', '', ''])
        table_data.append(['Price of Robustness:', f"{results['price_of_robustness']:.2f}%", '', '', ''])

    table = ax.table(cellText=table_data, cellLoc='left', loc='center',
                     colWidths=[0.15, 0.20, 0.20, 0.15, 0.20])

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)

    # Style header row
    for i in range(5):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(weight='bold', color='white')

    # Color code methods
    for i, method in enumerate(['nominal', 'scenario', 'drpg'], start=1):
        if method in results and results[method]['converged']:
            table[(i, 0)].set_facecolor(COLORS[method])
            table[(i, 0)].set_text_props(color='white', weight='bold')

    plt.title('IEEE Case118 Experimental Results Summary', fontsize=12, weight='bold', pad=20)

    # Save
    for ext in ['pdf', 'png']:
        fig.savefig(fig_dir / f"ieee_case118_summary_table.{ext}", dpi=600 if ext=='png' else None)
    print(f"  ✓ Saved: {fig_dir / 'ieee_case118_summary_table.pdf'}")
    plt.close()

    print("\n" + "="*80)
    print("✅ ALL VISUALIZATIONS GENERATED")
    print("="*80)
    print(f"\nFigures saved to: {fig_dir}")
    print("  - ieee_case118_comparison.pdf/png")
    print("  - ieee_case118_drpg_convergence.pdf/png")
    print("  - ieee_case118_summary_table.pdf/png")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("IEEE CASE118 EXPERIMENT - DRPG VALIDATION")
    print("="*80)
    print("\nThis experiment validates DRPG on a real IEEE test case with:")
    print("  - 54 generators (agents)")
    print("  - Real generator costs and capacity limits")
    print("  - Industry-realistic uncertainty (±15% load, ±10% network)")
    print("\n" + "="*80)

    # Run experiment
    results, output_dir = run_ieee_case118_experiment()

    # Generate visualizations
    generate_visualizations(results, output_dir)

    print("\n" + "="*80)
    print("✅ IEEE CASE118 EXPERIMENT COMPLETE")
    print("="*80)
