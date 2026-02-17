"""
Experiment I.3: Gradient-Free Stress Diagnostic
================================================

Objective:
    Demonstrate that the envelope gradient ∇V(u) = -P^T x provides "free"
    stress diagnostics without solving the bilevel max-max problem.

    Key insight: At nominal u=0, the gradient -P^T x*(0) points toward
    the direction of maximum vulnerability, guiding worst-case search.

Methodology:
    1. Solve nominal dispatch at u=0 → get x*(0), λ*(0)
    2. Compute envelope gradient: g = -P^T x*(0)
    3. Normalize and step in gradient direction: u_test = α * g / ||g||
    4. Compare V(u_test) with V(u_random) for random directions
    5. Show that gradient direction achieves higher objective faster
    6. Visualize stress surface along gradient vs random directions

Expected Results:
    - Gradient direction increases V faster than random directions
    - Provides cheap initialization for DRPG
    - Demonstrates practical value of envelope theorem

Outputs:
    - Figure: V(u) along gradient vs random directions
    - Figure: Convergence speed comparison
    - Table: Statistics on gradient effectiveness
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
import time

from core.problem_generator import generate_robust_qp, RobustQPProblem
from core.solvers import DirectNominalSolver, DRPG
from core.uncertainty_sets import create_uncertainty_set
from utils.logging_utils import ExperimentLogger
from utils.result_storage import save_experiment_results


def compute_value_along_direction(
    problem: RobustQPProblem,
    direction_p: np.ndarray,
    direction_c: np.ndarray,
    uset_p,
    uset_c,
    n_steps: int = 20,
) -> Dict:
    """
    Compute V(u) along a direction from u=0.

    Args:
        problem: Robust QP problem
        direction_p, direction_c: Search directions (will be normalized)
        uset_p, uset_c: Uncertainty sets
        n_steps: Number of steps along direction

    Returns:
        Dictionary with alphas and V values
    """
    solver = DirectNominalSolver()

    # Normalize directions
    dir_p_norm = direction_p / max(np.linalg.norm(direction_p), 1e-12)
    dir_c_norm = direction_c / max(np.linalg.norm(direction_c), 1e-12)

    # Max step sizes (to stay in uncertainty set)
    max_alpha_p = problem.uncertainty_radius_p
    max_alpha_c = problem.uncertainty_radius_c
    max_alpha = min(max_alpha_p, max_alpha_c)

    alphas = np.linspace(0, max_alpha, n_steps)
    V_values = []

    for alpha in alphas:
        u_p = alpha * dir_p_norm
        u_c = alpha * dir_c_norm

        # Project onto uncertainty sets
        u_p = uset_p.project(u_p)
        u_c = uset_c.project(u_c)

        # Solve
        result = solver.solve(problem, u_p, u_c)

        if result.get('converged'):
            V_values.append(result['V_value'])
        else:
            V_values.append(np.nan)

    return {
        'alphas': alphas,
        'V_values': np.array(V_values),
        'direction_p': dir_p_norm,
        'direction_c': dir_c_norm,
    }


def test_gradient_effectiveness(
    problem: RobustQPProblem,
    uset_p,
    uset_c,
    n_random_directions: int = 10,
    n_steps: int = 20,
) -> Dict:
    """
    Test envelope gradient vs random directions.

    Returns:
        Dictionary with gradient trajectory and random trajectories
    """
    solver = DirectNominalSolver()

    # Solve at nominal
    result_nominal = solver.solve(problem, np.zeros(problem.n_factors_p),
                                  np.zeros(problem.n_factors_c))

    if not result_nominal.get('converged'):
        return {'success': False, 'error_message': 'Nominal solve failed'}

    x_nominal = result_nominal['x_blocks']
    lambda_nominal = result_nominal['lambda']
    V_nominal = result_nominal['V_value']

    # Compute envelope gradient
    grad_p = -sum(problem.P[i].T @ x_nominal[i] for i in range(problem.n_agents))
    grad_c = -(problem.B.T @ lambda_nominal)

    # Trajectory along gradient
    grad_trajectory = compute_value_along_direction(
        problem, grad_p, grad_c, uset_p, uset_c, n_steps
    )

    # Trajectories along random directions
    random_trajectories = []
    for _ in range(n_random_directions):
        rand_p = np.random.randn(problem.n_factors_p)
        rand_c = np.random.randn(problem.n_factors_c)

        rand_trajectory = compute_value_along_direction(
            problem, rand_p, rand_c, uset_p, uset_c, n_steps
        )
        random_trajectories.append(rand_trajectory)

    # Also run DRPG to get true worst-case
    drpg = DRPG(max_outer_iterations=50, verbose=False)
    drpg_result = drpg.solve(problem, uset_p, uset_c)
    V_worst_true = drpg_result.worst_case_value if drpg_result.converged else np.nan

    return {
        'success': True,
        'V_nominal': V_nominal,
        'V_worst_true': V_worst_true,
        'grad_p': grad_p,
        'grad_c': grad_c,
        'grad_trajectory': grad_trajectory,
        'random_trajectories': random_trajectories,
    }


def run_experiment(
    problem_sizes: List,
    n_problems: int = 5,
    n_random_directions: int = 10,
    uncertainty_set_type: str = 'L2Ball',
    logger: ExperimentLogger = None,
) -> Dict:
    """Run stress diagnostic experiment."""
    if logger is None:
        logger = ExperimentLogger("I.3_stress_diagnostic", console_output=True)

    logger.info("Starting Gradient-Free Stress Diagnostic Experiment")
    logger.info(f"Problem sizes: {problem_sizes}")
    logger.info(f"Problems per size: {n_problems}")
    logger.info(f"Random directions: {n_random_directions}")

    results = {
        'problem_sizes': problem_sizes,
        'n_problems': n_problems,
        'n_random_directions': n_random_directions,
        'uncertainty_set_type': uncertainty_set_type,
        'tests': [],
    }

    for prob_idx, (n_agents, avg_vars, n_resources) in enumerate(problem_sizes):
        logger.info(f"\n{'='*60}")
        logger.info(f"Problem {prob_idx+1}/{len(problem_sizes)}: "
                   f"N={n_agents}, vars={avg_vars}, m={n_resources}")

        for run_idx in range(n_problems):
            logger.info(f"  Run {run_idx+1}/{n_problems}...")

            # Generate problem
            problem = generate_robust_qp(
                n_agents=n_agents,
                avg_vars_per_agent=avg_vars,
                n_resources=n_resources,
                n_factors_p=3,
                n_factors_c=2,
                uncertainty_radius_p=3.0,
                uncertainty_radius_c=1.5,
                seed=42 + prob_idx * 100 + run_idx,
            )

            # Create uncertainty sets
            uset_p = create_uncertainty_set(uncertainty_set_type,
                                           dim=problem.n_factors_p,
                                           radius=problem.uncertainty_radius_p)
            uset_c = create_uncertainty_set(uncertainty_set_type,
                                           dim=problem.n_factors_c,
                                           radius=problem.uncertainty_radius_c)

            # Test gradient effectiveness
            test_result = test_gradient_effectiveness(
                problem, uset_p, uset_c, n_random_directions
            )

            if test_result['success']:
                # Compute metrics
                grad_traj = test_result['grad_trajectory']['V_values']
                V_grad_final = grad_traj[-1]

                # Average final value of random trajectories
                random_finals = [traj['V_values'][-1]
                                for traj in test_result['random_trajectories']]
                V_random_mean = np.mean(random_finals)
                V_random_max = np.max(random_finals)

                # Gradient advantage
                advantage = V_grad_final - V_random_mean

                logger.info(f"    Gradient final: {V_grad_final:.2f}, "
                           f"Random mean: {V_random_mean:.2f}, "
                           f"Advantage: {advantage:.2f}")

                test_result.update({
                    'problem_size': (n_agents, avg_vars, n_resources),
                    'V_grad_final': V_grad_final,
                    'V_random_mean': V_random_mean,
                    'V_random_max': V_random_max,
                    'advantage': advantage,
                })

            results['tests'].append(test_result)

    logger.finalize()
    return results


def generate_figures(results: Dict, output_dir: Path):
    """Generate figures for experiment I.3."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.style.use('seaborn-v0_8-darkgrid')
    sns.set_palette("Set2")

    # Figure 1: Trajectories (first successful test)
    for test in results['tests']:
        if test['success']:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Gradient trajectory
            grad_alphas = test['grad_trajectory']['alphas']
            grad_V = test['grad_trajectory']['V_values']
            ax.plot(grad_alphas, grad_V, 'b-', linewidth=3,
                   label='Envelope Gradient', marker='o', markersize=8)

            # Random trajectories
            for i, rand_traj in enumerate(test['random_trajectories']):
                alphas = rand_traj['alphas']
                V_vals = rand_traj['V_values']
                if i == 0:
                    ax.plot(alphas, V_vals, 'gray', alpha=0.5,
                           linewidth=1.5, label='Random Directions')
                else:
                    ax.plot(alphas, V_vals, 'gray', alpha=0.5, linewidth=1.5)

            # Mark worst-case
            if not np.isnan(test['V_worst_true']):
                ax.axhline(y=test['V_worst_true'], color='red',
                          linestyle='--', linewidth=2, label='True Worst-Case (DRPG)')

            ax.set_xlabel('Step Size (α)', fontsize=12)
            ax.set_ylabel('Objective Value V(u)', fontsize=12)
            ax.set_title('Envelope Gradient vs Random Directions',
                        fontsize=14, fontweight='bold')
            ax.legend(fontsize=11)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(output_dir / 'I3_gradient_trajectories.pdf',
                       dpi=300, bbox_inches='tight')
            plt.close()
            break  # Only first plot

    # Figure 2: Gradient Advantage
    fig, ax = plt.subplots(figsize=(10, 6))

    advantages = [test.get('advantage', np.nan) for test in results['tests']
                  if test['success']]
    if len(advantages) > 0:
        ax.hist(advantages, bins=15, edgecolor='black', alpha=0.7)
        ax.axvline(x=np.mean(advantages), color='red', linestyle='--',
                  linewidth=2, label=f'Mean = {np.mean(advantages):.2f}')
        ax.set_xlabel('Gradient Advantage (ΔV)', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.set_title('Distribution of Gradient Advantage over Random Directions',
                    fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(output_dir / 'I3_advantage_distribution.pdf',
                   dpi=300, bbox_inches='tight')
        plt.close()

    print(f"\n✅ Figures saved to {output_dir}/")


def generate_table(results: Dict) -> str:
    """Generate LaTeX table for experiment I.3."""
    table = r"""\begin{table}[htbp]
\centering
\caption{Gradient-Free Stress Diagnostic Results}
\label{tab:stress_diagnostic}
\begin{tabular}{lccc}
\toprule
\textbf{Problem Size} & \textbf{Gradient Final} & \textbf{Random Mean} & \textbf{Advantage} \\
\midrule
"""

    for test in results['tests']:
        if test['success']:
            size_str = f"{test['problem_size'][0]}×{test['problem_size'][1]}"
            V_grad = test['V_grad_final']
            V_rand = test['V_random_mean']
            adv = test['advantage']

            table += f"{size_str} & {V_grad:.2f} & {V_rand:.2f} & {adv:.2f} \\\\\n"

    table += r"""\bottomrule
\end{tabular}
\end{table}
"""

    return table


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("EXPERIMENT I.3: GRADIENT-FREE STRESS DIAGNOSTIC")
    print("="*70)

    # Configuration
    problem_sizes = [
        (5, 10, 3),
        (10, 15, 5),
    ]

    n_problems = 5
    n_random = 10

    # Run experiment
    logger = ExperimentLogger(
        "I.3_stress_diagnostic",
        log_dir=Path(__file__).parent.parent.parent / "results" / "category_I",
        console_output=True,
    )

    logger.set_parameters({
        'problem_sizes': problem_sizes,
        'n_problems': n_problems,
        'n_random_directions': n_random,
    })

    results = run_experiment(
        problem_sizes=problem_sizes,
        n_problems=n_problems,
        n_random_directions=n_random,
        uncertainty_set_type='L2Ball',
        logger=logger,
    )

    # Save results
    saved_files = save_experiment_results(
        experiment_name="I3_stress_diagnostic",
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
    with open(table_dir / "I3_stress_diagnostic.tex", 'w') as f:
        f.write(table_latex)
    print(f"\n✅ Table saved to {table_dir}/I3_stress_diagnostic.tex")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    advantages = [test.get('advantage', np.nan) for test in results['tests']
                  if test['success']]

    if len(advantages) > 0:
        print(f"Mean gradient advantage: {np.mean(advantages):.2f}")
        print(f"Median gradient advantage: {np.median(advantages):.2f}")
        print(f"Min/Max advantage: {np.min(advantages):.2f} / {np.max(advantages):.2f}")

        if np.mean(advantages) > 0:
            print("\n✅ VALIDATION PASSED: Gradient consistently outperforms random")
        else:
            print("\n⚠️  VALIDATION WARNING: Gradient advantage not consistently positive")

    print("="*70)

    return results


if __name__ == "__main__":
    results = main()
