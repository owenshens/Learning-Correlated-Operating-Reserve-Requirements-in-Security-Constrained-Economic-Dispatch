"""
Performance Metrics for Robust Optimization
============================================

Computes standard metrics for evaluating robust optimization algorithms:
- Optimality gaps
- Constraint violations
- Price of robustness (PoR)
- Convergence rates
- Computational efficiency
"""

import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Container for algorithm performance metrics."""

    # Optimality
    objective_value: float
    optimality_gap: Optional[float] = None
    duality_gap: Optional[float] = None

    # Feasibility
    constraint_violation: float = 0.0
    is_feasible: bool = True

    # Convergence
    iterations: int = 0
    solve_time: float = 0.0
    convergence_rate: Optional[float] = None

    # Robustness
    worst_case_value: Optional[float] = None
    price_of_robustness: Optional[float] = None

    # Computational
    inner_iterations: Optional[int] = None
    function_evaluations: Optional[int] = None
    gradient_evaluations: Optional[int] = None


def compute_optimality_gap(
    obj_value: float,
    obj_optimal: float,
    is_minimization: bool = True,
) -> float:
    """
    Compute optimality gap as percentage.

    Gap = |obj - obj*| / |obj*| * 100%

    Args:
        obj_value: Current objective value
        obj_optimal: Optimal objective value
        is_minimization: Whether problem is minimization

    Returns:
        Optimality gap percentage
    """
    if abs(obj_optimal) < 1e-12:
        return abs(obj_value - obj_optimal)

    gap = abs(obj_value - obj_optimal) / abs(obj_optimal) * 100
    return float(gap)


def compute_duality_gap(
    primal_value: float,
    dual_value: float,
    is_minimization: bool = True,
) -> float:
    """
    Compute duality gap.

    For minimization: gap = primal - dual
    For maximization: gap = dual - primal

    Args:
        primal_value: Primal objective
        dual_value: Dual objective
        is_minimization: Whether problem is minimization

    Returns:
        Duality gap
    """
    if is_minimization:
        return float(primal_value - dual_value)
    else:
        return float(dual_value - primal_value)


def compute_constraint_violation(
    A: np.ndarray,
    x: np.ndarray,
    b: np.ndarray,
    constraint_type: str = 'equality',
) -> float:
    """
    Compute constraint violation.

    Args:
        A: Constraint matrix
        x: Solution vector
        b: RHS vector
        constraint_type: 'equality' or 'inequality'

    Returns:
        Violation measure (L1 norm)
    """
    residual = A @ x - b

    if constraint_type == 'equality':
        return float(np.linalg.norm(residual, 1))
    elif constraint_type == 'inequality':
        # Only count violations (Ax <= b)
        violations = np.maximum(residual, 0)
        return float(np.linalg.norm(violations, 1))
    else:
        raise ValueError(f"Unknown constraint type: {constraint_type}")


def compute_price_of_robustness(
    robust_value: float,
    nominal_value: float,
    is_minimization: bool = True,
) -> float:
    """
    Compute Price of Robustness (PoR).

    For minimization: PoR = (V_robust - V_nominal) / V_nominal * 100%
    For maximization: PoR = (V_nominal - V_robust) / V_nominal * 100%

    Args:
        robust_value: Robust objective value
        nominal_value: Nominal objective value
        is_minimization: Whether problem is minimization

    Returns:
        PoR percentage
    """
    if abs(nominal_value) < 1e-12:
        return abs(robust_value - nominal_value)

    if is_minimization:
        por = (robust_value - nominal_value) / abs(nominal_value) * 100
    else:
        por = (nominal_value - robust_value) / abs(nominal_value) * 100

    return float(por)


def compute_convergence_rate(
    error_trajectory: np.ndarray,
    iterations: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    Estimate convergence rate from error trajectory.

    Fits: log(error) ≈ a + b * log(iteration)
    Rate exponent is -b

    Args:
        error_trajectory: Error at each iteration
        iterations: Iteration indices (default: 1, 2, 3, ...)

    Returns:
        Dictionary with rate estimate
    """
    if iterations is None:
        iterations = np.arange(1, len(error_trajectory) + 1)

    # Filter positive errors
    mask = error_trajectory > 0
    if np.sum(mask) < 2:
        return {'rate_exponent': np.nan, 'r_squared': 0.0}

    log_errors = np.log(error_trajectory[mask])
    log_iters = np.log(iterations[mask])

    # Linear regression
    from scipy import stats
    slope, intercept, r_value, _, _ = stats.linregress(log_iters, log_errors)

    return {
        'rate_exponent': float(-slope),
        'r_squared': float(r_value**2),
        'interpretation': _interpret_rate(-slope),
    }


def _interpret_rate(rate: float) -> str:
    """Interpret convergence rate."""
    if abs(rate - 0.5) < 0.1:
        return "O(1/√K)"
    elif abs(rate - 1.0) < 0.1:
        return "O(1/K)"
    elif abs(rate - 2.0) < 0.1:
        return "O(1/K²)"
    else:
        return f"O(1/K^{rate:.2f})"


def compute_speedup(
    time_baseline: float,
    time_method: float,
) -> float:
    """
    Compute speedup factor.

    Speedup = time_baseline / time_method

    Args:
        time_baseline: Baseline algorithm time
        time_method: New algorithm time

    Returns:
        Speedup factor (> 1 means faster)
    """
    if time_method < 1e-12:
        return np.inf
    return float(time_baseline / time_method)


def compute_efficiency(
    solve_time: float,
    problem_size: int,
) -> float:
    """
    Compute time per variable (efficiency metric).

    Args:
        solve_time: Total solve time
        problem_size: Number of variables

    Returns:
        Time per variable (seconds)
    """
    if problem_size == 0:
        return np.inf
    return float(solve_time / problem_size)


def compute_envelope_gradient_error(
    grad_V_numerical: np.ndarray,
    grad_V_envelope: np.ndarray,
    norm_type: int = 2,
) -> float:
    """
    Compute error in envelope theorem gradient.

    Compares numerical gradient to envelope formula: ∇V = -P^T x

    Args:
        grad_V_numerical: Numerical gradient of V(u)
        grad_V_envelope: Envelope theorem gradient
        norm_type: Norm for error (1, 2, or np.inf)

    Returns:
        Relative error
    """
    numerator = np.linalg.norm(grad_V_numerical - grad_V_envelope, ord=norm_type)
    denominator = np.linalg.norm(grad_V_numerical, ord=norm_type)

    if denominator < 1e-12:
        return float(numerator)
    else:
        return float(numerator / denominator)


def compute_dual_penalty_gap(
    V_worst_primal: float,
    Phi_dual: float,
    tolerance: float = 1e-6,
) -> Dict[str, Any]:
    """
    Compute gap between primal and dual formulations.

    For robust optimization:
        max_u V(u)  (primal stress search)
        max_λ Φ(λ) - σ(P^T λ)  (dual price penalty)

    Should satisfy: V* ≈ Φ* (strong duality)

    Args:
        V_worst_primal: Worst-case value from primal
        Phi_dual: Dual objective value
        tolerance: Tolerance for "equal"

    Returns:
        Dictionary with gap metrics
    """
    gap_abs = abs(V_worst_primal - Phi_dual)

    if abs(V_worst_primal) > 1e-12:
        gap_rel = gap_abs / abs(V_worst_primal)
    else:
        gap_rel = gap_abs

    return {
        'gap_absolute': float(gap_abs),
        'gap_relative': float(gap_rel),
        'primal_value': float(V_worst_primal),
        'dual_value': float(Phi_dual),
        'satisfies_duality': bool(gap_abs < tolerance),
    }


def compute_benchmark_comparison(
    results: Dict[str, Dict],
    baseline_key: str = 'baseline',
) -> Dict[str, Dict]:
    """
    Compare multiple algorithms against baseline.

    Args:
        results: Dictionary mapping algorithm name to result dict
        baseline_key: Key for baseline algorithm

    Returns:
        Comparison metrics for each algorithm
    """
    if baseline_key not in results:
        raise ValueError(f"Baseline '{baseline_key}' not found in results")

    baseline = results[baseline_key]
    comparisons = {}

    for name, result in results.items():
        if name == baseline_key:
            continue

        comp = {
            'objective_diff': result['objective'] - baseline['objective'],
            'speedup': compute_speedup(baseline['solve_time'], result['solve_time']),
            'time_diff': baseline['solve_time'] - result['solve_time'],
        }

        if 'iterations' in result and 'iterations' in baseline:
            comp['iteration_ratio'] = result['iterations'] / max(baseline['iterations'], 1)

        comparisons[name] = comp

    return comparisons


def aggregate_metrics_over_runs(
    runs: List[Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    """
    Aggregate metrics across multiple runs.

    Computes mean, std, min, max for each metric.

    Args:
        runs: List of dictionaries with metrics

    Returns:
        Aggregated statistics
    """
    if not runs:
        return {}

    metrics = list(runs[0].keys())
    aggregated = {}

    for metric in metrics:
        values = [run[metric] for run in runs if metric in run and not np.isnan(run[metric])]

        if len(values) == 0:
            continue

        aggregated[metric] = {
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'median': float(np.median(values)),
            'count': len(values),
        }

    return aggregated
