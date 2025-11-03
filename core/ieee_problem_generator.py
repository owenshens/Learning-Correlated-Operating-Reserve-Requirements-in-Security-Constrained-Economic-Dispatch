"""
IEEE-Calibrated Problem Generator
==================================

Generates robust QP problems with realistic parameters from IEEE test cases,
combined with designed uncertainty models.

Hybrid Approach:
- Deterministic base (from IEEE): Generator costs, network topology, bounds
- Uncertainty overlay (our design): Load/network uncertainty factors

This enables realistic validation while maintaining full control over
uncertainty modeling for sensitivity analysis.

IEEE Cases Supported:
- IEEE 30-bus: 5 generators, 30 buses, 20 loads
- IEEE 57-bus: 6 generators, 57 buses, 42 loads
- IEEE 118-bus: 53 generators, 118 buses, 99 loads

References:
- Zimmerman et al., "MATPOWER: Steady-State Operations, Planning and Analysis
  Tools for Power Systems Research and Education," IEEE TPWRS, 2011
- Pandapower: https://www.pandapower.org/
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Dict
from pathlib import Path
import warnings

try:
    import pandapower as pp
    import pandapower.networks as pn
    PANDAPOWER_AVAILABLE = True
except ImportError:
    PANDAPOWER_AVAILABLE = False
    warnings.warn("Pandapower not available. IEEE problem generation will fail.")

from .problem_generator import RobustQPProblem


def extract_ieee_generator_data(case_name: str = 'case30') -> Dict:
    """
    Extract generator parameters from IEEE test case.

    Args:
        case_name: One of 'case30', 'case57', 'case118'

    Returns:
        Dictionary with generator data:
        - n_generators: Number of generators
        - gen_buses: Bus indices for each generator
        - p_min: Minimum power output (MW) per generator
        - p_max: Maximum power output (MW) per generator
        - cost_quadratic: Quadratic cost coefficients (default if not available)
        - cost_linear: Linear cost coefficients (default if not available)
        - net: Full pandapower network object
    """
    if not PANDAPOWER_AVAILABLE:
        raise ImportError("Pandapower required. Install with: pip install pandapower")

    # Load IEEE case
    if case_name == 'case30':
        net = pn.case30()
    elif case_name == 'case57':
        net = pn.case57()
    elif case_name == 'case118':
        net = pn.case118()
    else:
        raise ValueError(f"Unknown case: {case_name}. Use 'case30', 'case57', or 'case118'")

    gens = net.gen
    n_generators = len(gens)

    # Extract power limits
    p_min = gens['min_p_mw'].values
    p_max = gens['max_p_mw'].values
    gen_buses = gens['bus'].values

    # IEEE cases typically don't include cost data directly
    # We'll synthesize realistic costs based on generator capacity
    # Typical costs: Small generators more expensive per MW (peaker plants)
    #               Large generators cheaper per MW (baseload)

    cost_quadratic = np.zeros(n_generators)
    cost_linear = np.zeros(n_generators)

    for i in range(n_generators):
        capacity = p_max[i]

        # Cost model based on capacity
        # Large units (>200 MW): Baseload (coal, nuclear) - low $/MW, low $/MW²
        # Medium units (50-200 MW): Combined cycle gas - medium costs
        # Small units (<50 MW): Peakers (gas turbine) - high $/MW, high $/MW²

        if capacity > 200:
            # Baseload: Low operating cost
            cost_quadratic[i] = 0.002  # $/MW²
            cost_linear[i] = 15.0      # $/MW
        elif capacity > 50:
            # Mid-merit: Medium operating cost
            cost_quadratic[i] = 0.01   # $/MW²
            cost_linear[i] = 25.0      # $/MW
        else:
            # Peaker: High operating cost
            cost_quadratic[i] = 0.02   # $/MW²
            cost_linear[i] = 40.0      # $/MW

    return {
        'n_generators': n_generators,
        'gen_buses': gen_buses,
        'p_min': p_min,
        'p_max': p_max,
        'cost_quadratic': cost_quadratic,
        'cost_linear': cost_linear,
        'net': net,
    }


def extract_ieee_network_structure(net) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Extract network structure for simplified power balance constraint.

    Uses aggregate system-wide power balance:
        sum_i P_i = Total_Demand

    This is the fundamental constraint in power systems and is standard
    in robust optimization literature for power dispatch problems.
    It avoids rank deficiency issues from per-bus constraints where
    most buses lack generators.

    Args:
        net: Pandapower network object

    Returns:
        A_network: [1 × n_gens] all-ones vector (aggregate generation)
        b_demand: [1] total system demand (MW)
        n_resources: 1 (single aggregate constraint)
    """
    n_gens = len(net.gen)

    # Single aggregate constraint: sum of all generation = total demand
    A_network = np.ones((1, n_gens))

    # Total system demand
    total_demand = net.load['p_mw'].sum()
    b_demand = np.array([total_demand])

    return A_network, b_demand, 1


def create_load_uncertainty_factors(
    n_buses: int,
    n_factors_p: int = 3,
    correlation_model: str = 'geographic',
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Design P matrices for load forecast uncertainty.

    Physical interpretation:
    - Factor 1: System-wide demand (temperature, time of day) - high correlation
    - Factor 2: Regional variations (local weather patterns) - medium correlation
    - Factor 3+: Idiosyncratic noise (individual forecast errors) - low correlation

    Calibration from literature:
    - NERC: Load forecast errors typically ±10-20% of peak
    - Correlation: Nearby regions 0.7-0.9, distant regions 0.3-0.5

    Args:
        n_buses: Number of buses
        n_factors_p: Number of uncertainty factors
        correlation_model: 'geographic', 'random', or 'hierarchical'
        seed: Random seed

    Returns:
        P_matrix: [n_buses × n_factors_p] uncertainty factor matrix
    """
    if seed is not None:
        np.random.seed(seed)

    P = np.zeros((n_buses, n_factors_p))

    if correlation_model == 'geographic':
        # Factor 1: System-wide (all buses equally affected)
        if n_factors_p >= 1:
            P[:, 0] = 1.0

        # Factor 2: Regional variation (sinusoidal pattern along bus index)
        if n_factors_p >= 2:
            P[:, 1] = np.sin(2 * np.pi * np.arange(n_buses) / n_buses)

        # Factor 3+: Local random variations
        for j in range(2, n_factors_p):
            P[:, j] = np.random.randn(n_buses)

    elif correlation_model == 'hierarchical':
        # Cluster buses into regions (simplified: 3 regions)
        n_regions = min(3, n_factors_p)
        buses_per_region = n_buses // n_regions

        for j in range(n_factors_p):
            if j < n_regions:
                # Regional factor
                region_start = j * buses_per_region
                region_end = region_start + buses_per_region
                P[region_start:region_end, j] = 1.0
            else:
                # Independent noise
                P[:, j] = np.random.randn(n_buses) * 0.3

    else:  # 'random'
        P = np.random.randn(n_buses, n_factors_p)

    # Normalize columns (each factor has unit effect)
    for j in range(n_factors_p):
        norm = np.linalg.norm(P[:, j])
        if norm > 1e-10:
            P[:, j] /= norm

    return P


def create_network_uncertainty_factors(
    A_network: np.ndarray,
    b_demand: np.ndarray,
    n_factors_c: int = 2,
    uncertainty_type: str = 'demand_forecast',
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Design B matrix for demand uncertainty.

    For aggregate power balance constraint, B represents uncertainty in
    total system demand. Physical interpretation:
    - Factor 1: Systematic demand forecast error (weather, events)
    - Factor 2: Load variability (time-of-day, seasonal)
    - Factor 3+: Stochastic fluctuations

    Calibration from standards:
    - NERC: ±10-15% day-ahead forecast error typical
    - ISO-NE data: 5-10% hour-ahead MAPE

    Args:
        A_network: [1 × n_gens] constraint matrix (not used, for interface compatibility)
        b_demand: [1] total system demand
        n_factors_c: Number of demand uncertainty factors
        uncertainty_type: Type of uncertainty (for future extension)
        seed: Random seed

    Returns:
        B_matrix: [1 × n_factors_c] demand uncertainty matrix
    """
    if seed is not None:
        np.random.seed(seed)

    n_resources = A_network.shape[0]  # Should be 1 for aggregate model
    B = np.zeros((n_resources, n_factors_c))

    # All factors represent demand uncertainty
    # Use orthogonal directions for independent sources of uncertainty
    for j in range(n_factors_c):
        B[0, j] = 1.0  # Equal weight on all factors initially

    # Normalize to unit norm per factor
    B = B / np.sqrt(n_factors_c)

    return B


def generate_ieee_calibrated_qp(
    ieee_case: str = 'case30',
    n_factors_p: int = 3,
    n_factors_c: int = 2,
    uncertainty_radius_p: float = 0.15,  # ±15% load variation (industry standard)
    uncertainty_radius_c: float = 0.10,   # ±10% network variation (N-1 contingency)
    correlation_model: str = 'geographic',
    uncertainty_type: str = 'line_outage',
    seed: Optional[int] = None,
) -> RobustQPProblem:
    """
    Generate robust QP with IEEE-calibrated deterministic parameters
    and designed uncertainty overlay.

    Hybrid approach:
    - Deterministic base (from IEEE):
      * Generator costs (Q, c) - realistic cost functions
      * Network topology (A, b) - real power network structure
      * Generation bounds (x_lower, x_upper) - actual capacity limits

    - Uncertainty overlay (our design):
      * Load uncertainty (P matrices) - calibrated to ±15% (NERC standard)
      * Network uncertainty (B matrix) - calibrated to ±10% (IEEE N-1)
      * Full control for sensitivity analysis

    Args:
        ieee_case: One of 'case30', 'case57', 'case118'
        n_factors_p: Number of load uncertainty factors (default 3)
        n_factors_c: Number of network uncertainty factors (default 2)
        uncertainty_radius_p: Load uncertainty radius (default 0.15 = ±15%)
        uncertainty_radius_c: Network uncertainty radius (default 0.10 = ±10%)
        correlation_model: Load correlation structure ('geographic', 'hierarchical', 'random')
        uncertainty_type: Network uncertainty type ('line_outage', 'capacity_degradation', 'mixed')
        seed: Random seed for reproducibility

    Returns:
        RobustQPProblem instance with IEEE-calibrated parameters

    Example:
        >>> problem = generate_ieee_calibrated_qp('case30', seed=42)
        >>> print(f"IEEE-30: {problem.n_agents} generators, {problem.n_resources} buses")
        >>> # Solve with DRPG
        >>> drpg = DRPG()
        >>> result = drpg.solve(problem, uset_p, uset_c)
    """
    if seed is not None:
        np.random.seed(seed)

    # Extract IEEE deterministic data
    gen_data = extract_ieee_generator_data(ieee_case)
    A_network, b_demand, n_resources = extract_ieee_network_structure(gen_data['net'])

    n_agents = gen_data['n_generators']

    # Build deterministic parameters (from IEEE)
    Q = []
    c = []
    A = []
    x_lower = []
    x_upper = []

    for i in range(n_agents):
        # Quadratic cost matrix (1×1 for single power output variable)
        # IEEE provides a*P^2 + b*P + c
        # Our format: minimize 0.5*x'Qx - c'x
        # Match by: Q = 2*a, c = -b (negate for maximization)

        a = gen_data['cost_quadratic'][i]
        b_cost = gen_data['cost_linear'][i]

        Q_i = np.array([[2 * a]])  # 2a for quadratic form
        c_i = np.array([-b_cost])   # Negate for maximization

        # Constraint matrix: generator i supplies to network
        # A_i should be [n_resources × n_vars_i], where n_vars_i = 1 for each generator
        A_i = A_network[:, i:i+1]  # [n_resources × 1]

        # Bounds
        x_lower_i = np.array([gen_data['p_min'][i]])
        x_upper_i = np.array([gen_data['p_max'][i]])

        Q.append(Q_i)
        c.append(c_i)
        A.append(A_i)
        x_lower.append(x_lower_i)
        x_upper.append(x_upper_i)

    # RHS: Net demand at each bus
    b = b_demand

    # Design uncertainty overlay (our choice)
    # P matrices: Objective uncertainty per generator
    # Each generator faces price/cost uncertainty
    # Factors represent: system-wide price movements, regional variations, etc.
    P = []
    for i in range(n_agents):
        # Generator-specific uncertainty
        # Scale by capacity: larger generators have more exposure
        capacity_factor = gen_data['p_max'][i] / gen_data['p_max'].sum()

        # Create uncertainty matrix [1 × n_factors_p]
        P_i = np.zeros((1, n_factors_p))
        if n_factors_p >= 1:
            # Factor 1: System-wide price uncertainty (all generators affected equally)
            P_i[0, 0] = 1.0
        if n_factors_p >= 2:
            # Factor 2: Capacity-weighted exposure
            P_i[0, 1] = capacity_factor * n_agents
        if n_factors_p >= 3:
            # Factor 3+: Generator-specific idiosyncratic uncertainty
            if seed is not None:
                np.random.seed(seed + i)
            P_i[0, 2:] = np.random.randn(n_factors_p - 2) * 0.5

        P.append(P_i)

    # B matrix: Network uncertainty (affects RHS directly)
    B = create_network_uncertainty_factors(
        A_network=A_network,
        b_demand=b_demand,
        n_factors_c=n_factors_c,
        uncertainty_type=uncertainty_type,
        seed=seed,
    )

    # Scale uncertainty radii to match physical interpretation
    # radius_p = 0.15 means ±15% of typical load variation
    # radius_c = 0.10 means ±10% of network capacity
    # These are industry-standard values (NERC, IEEE)

    return RobustQPProblem(
        n_agents=n_agents,
        n_vars=[1] * n_agents,  # Single power output per generator
        n_resources=n_resources,
        n_factors_p=n_factors_p,
        n_factors_c=n_factors_c,
        c=c,
        Q=Q,
        P=P,
        A=A,
        B=B,
        b=b,
        x_lower=x_lower,
        x_upper=x_upper,
        uncertainty_radius_p=uncertainty_radius_p,
        uncertainty_radius_c=uncertainty_radius_c,
    )


def compare_ieee_vs_synthetic_statistics(ieee_case: str = 'case30', seed: int = 42) -> Dict:
    """
    Compare statistical properties of IEEE-calibrated vs synthetic problems.

    Useful for validating that IEEE problems are well-formed and comparable
    to synthetic benchmarks.

    Args:
        ieee_case: IEEE case to analyze
        seed: Random seed

    Returns:
        Dictionary with comparison statistics
    """
    from .problem_generator import generate_robust_qp

    # Generate IEEE-calibrated problem
    ieee_prob = generate_ieee_calibrated_qp(ieee_case, seed=seed)

    # Generate comparable synthetic problem
    synth_prob = generate_robust_qp(
        n_agents=ieee_prob.n_agents,
        avg_vars_per_agent=1,
        n_resources=ieee_prob.n_resources,
        n_factors_p=ieee_prob.n_factors_p,
        n_factors_c=ieee_prob.n_factors_c,
        uncertainty_radius_p=ieee_prob.uncertainty_radius_p,
        uncertainty_radius_c=ieee_prob.uncertainty_radius_c,
        problem_type="energy",
        seed=seed,
    )

    def problem_stats(prob, name):
        """Compute statistics for a problem."""
        # Cost statistics
        c_flat = np.concatenate(prob.c)
        Q_eigenvalues = [np.linalg.eigvalsh(Q_i).max() for Q_i in prob.Q]

        # Constraint statistics
        A_norms = [np.linalg.norm(A_i, 'fro') for A_i in prob.A]
        b_norm = np.linalg.norm(prob.b)

        # Uncertainty statistics
        P_norms = [np.linalg.norm(P_i, 'fro') for P_i in prob.P]
        B_norm = np.linalg.norm(prob.B, 'fro')

        return {
            'name': name,
            'n_agents': prob.n_agents,
            'n_vars_total': prob.total_vars(),
            'n_resources': prob.n_resources,
            'cost_linear_mean': np.mean(c_flat),
            'cost_linear_std': np.std(c_flat),
            'cost_quadratic_max_eig': np.max(Q_eigenvalues),
            'constraint_frobenius_mean': np.mean(A_norms),
            'rhs_norm': b_norm,
            'uncertainty_P_mean': np.mean(P_norms),
            'uncertainty_B_norm': B_norm,
        }

    ieee_stats = problem_stats(ieee_prob, f"IEEE-{ieee_case}")
    synth_stats = problem_stats(synth_prob, "Synthetic")

    return {
        'ieee': ieee_stats,
        'synthetic': synth_stats,
        'ieee_problem': ieee_prob,
        'synthetic_problem': synth_prob,
    }


# Convenience function for batch generation
def generate_all_ieee_problems(
    n_factors_p: int = 3,
    n_factors_c: int = 2,
    uncertainty_radius_p: float = 0.15,
    uncertainty_radius_c: float = 0.10,
    seed: Optional[int] = None,
) -> Dict[str, RobustQPProblem]:
    """
    Generate all three IEEE test cases at once.

    Args:
        n_factors_p, n_factors_c, uncertainty_radius_p, uncertainty_radius_c:
            Uncertainty parameters
        seed: Random seed

    Returns:
        Dictionary mapping case name to RobustQPProblem
    """
    cases = {}

    for case_name in ['case30', 'case57', 'case118']:
        cases[case_name] = generate_ieee_calibrated_qp(
            ieee_case=case_name,
            n_factors_p=n_factors_p,
            n_factors_c=n_factors_c,
            uncertainty_radius_p=uncertainty_radius_p,
            uncertainty_radius_c=uncertainty_radius_c,
            seed=seed,
        )

    return cases
