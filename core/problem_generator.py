"""
Problem Generator for Robust QP with Double Uncertainty
========================================================

Generates synthetic robust quadratic programming problems with:
- Objective uncertainty (P matrices)
- Constraint RHS uncertainty (B matrix)
- Block structure (multiple agents with local variables)
- Coupling constraints (resources shared across agents)

Problem format:
    max c'x - 0.5 x'Qx + (Pu_p)'x
    s.t. Ax = b + Bu_c
         x_lower <= x <= x_upper
         ||u_p|| <= rho_p, ||u_c|| <= rho_c

Used for testing DRPG, PRDA, and benchmarks.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
import warnings

# Suppress numerical warnings from matrix operations
# (These occur rarely and are handled by nan_to_num or positive definite checks)
warnings.filterwarnings('ignore', category=RuntimeWarning,
                       message='.*overflow encountered in matmul.*')
warnings.filterwarnings('ignore', category=RuntimeWarning,
                       message='.*divide by zero encountered in matmul.*')
warnings.filterwarnings('ignore', category=RuntimeWarning,
                       message='.*invalid value encountered in matmul.*')


@dataclass
class RobustQPProblem:
    """
    Robust QP problem with double uncertainty.

    Attributes:
        n_agents: Number of agents (blocks)
        n_vars: Variables per agent (list of ints)
        n_resources: Number of coupling constraints
        n_factors_p: Objective uncertainty dimension
        n_factors_c: Constraint uncertainty dimension

        c: Linear costs (maximize) - list of arrays per agent
        Q: Quadratic costs (PSD) - list of matrices per agent
        P: Objective uncertainty coupling - list of matrices per agent
        A: Resource constraint matrices - list per agent
        B: Constraint uncertainty coupling matrix (n_resources x n_factors_c)
        b: Resource limits (nominal RHS)

        x_lower: Lower bounds per agent
        x_upper: Upper bounds per agent
        uncertainty_radius_p: ||u_p||_2 <= rho_p
        uncertainty_radius_c: ||u_c||_2 <= rho_c
    """
    n_agents: int
    n_vars: List[int]
    n_resources: int
    n_factors_p: int
    n_factors_c: int

    c: List[np.ndarray]
    Q: List[np.ndarray]
    P: List[np.ndarray]
    A: List[np.ndarray]
    B: np.ndarray
    b: np.ndarray

    x_lower: List[np.ndarray]
    x_upper: List[np.ndarray]
    uncertainty_radius_p: float
    uncertainty_radius_c: float

    def total_vars(self) -> int:
        """Total number of variables"""
        return sum(self.n_vars)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            'n_agents': self.n_agents,
            'n_vars': self.n_vars,
            'n_resources': self.n_resources,
            'n_factors_p': self.n_factors_p,
            'n_factors_c': self.n_factors_c,
            'c': [c_i.tolist() for c_i in self.c],
            'Q': [Q_i.tolist() for Q_i in self.Q],
            'P': [P_i.tolist() for P_i in self.P],
            'A': [A_i.tolist() for A_i in self.A],
            'B': self.B.tolist(),
            'b': self.b.tolist(),
            'x_lower': [xl.tolist() for xl in self.x_lower],
            'x_upper': [xu.tolist() for xu in self.x_upper],
            'uncertainty_radius_p': float(self.uncertainty_radius_p),
            'uncertainty_radius_c': float(self.uncertainty_radius_c),
        }


def generate_robust_qp(
    n_agents: int = 10,
    avg_vars_per_agent: int = 20,
    n_resources: int = 5,
    n_factors_p: int = 3,
    n_factors_c: int = 3,
    uncertainty_radius_p: float = 5.0,
    uncertainty_radius_c: float = 2.0,
    seed: Optional[int] = None,
    problem_type: str = "generic",
) -> RobustQPProblem:
    """
    Generate a synthetic robust QP problem.

    Args:
        n_agents: Number of agents/blocks
        avg_vars_per_agent: Average variables per agent
        n_resources: Number of coupling constraints
        n_factors_p: Objective uncertainty factors
        n_factors_c: Constraint uncertainty factors
        uncertainty_radius_p: Objective uncertainty radius
        uncertainty_radius_c: Constraint uncertainty radius
        seed: Random seed for reproducibility
        problem_type: "generic", "energy", or "portfolio"

    Returns:
        RobustQPProblem instance
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate variable counts per agent (with some variation)
    n_vars = []
    for i in range(n_agents):
        n_i = avg_vars_per_agent + np.random.randint(-2, 3)
        n_i = max(5, n_i)  # At least 5 vars per agent
        n_vars.append(n_i)

    # Generate costs, quadratics, and uncertainty matrices per agent
    c = []
    Q = []
    P = []
    A = []
    x_lower = []
    x_upper = []

    for i in range(n_agents):
        n_i = n_vars[i]

        # Linear cost (positive for maximization)
        if problem_type == "energy":
            # Energy: costs vary by generator type
            c_i = np.random.uniform(20, 100, n_i)  # $/MWh
        else:
            c_i = np.random.uniform(5, 15, n_i)

        # Quadratic cost (PSD) - stable generation via eigenvalue decomposition
        # Generate random symmetric matrix with controlled eigenvalues
        U_i = np.random.randn(n_i, n_i)
        U_i, _ = np.linalg.qr(U_i)  # Orthogonal matrix
        eigenvalues = np.random.uniform(0.1, 1.0, n_i)  # Positive eigenvalues
        Q_i = U_i @ np.diag(eigenvalues) @ U_i.T

        # Objective uncertainty coupling (P matrices)
        # FIXED: Scale relative to c_i magnitude for realistic uncertainty (15% typical)
        P_i = np.random.randn(n_i, n_factors_p) * (0.15 * c_i[:, None])

        # Resource usage matrix (ensure full rank)
        A_i = np.zeros((n_resources, n_i))
        for j in range(n_resources):
            # Ensure each constraint has at least one nonzero per agent
            n_nonzero = max(1, min(n_i, max(2, int(0.5 * n_i))))
            indices = np.random.choice(n_i, n_nonzero, replace=False)
            A_i[j, indices] = np.random.uniform(0.3, 1.5, n_nonzero)

        # Bounds
        x_lower_i = np.zeros(n_i)
        if problem_type == "energy":
            x_upper_i = np.random.uniform(50, 200, n_i)  # MW capacity
        else:
            x_upper_i = np.random.uniform(5, 10, n_i)

        c.append(c_i)
        Q.append(Q_i)
        P.append(P_i)
        A.append(A_i)
        x_lower.append(x_lower_i)
        x_upper.append(x_upper_i)

    # Resource limits (nominal RHS)
    # Choose b such that problem is feasible at nominal uncertainty
    b = np.zeros(n_resources)
    for j in range(n_resources):
        total_usage = 0
        for i in range(n_agents):
            x_mid = 0.5 * x_upper[i]
            total_usage += np.sum(A[i][j, :] * x_mid)
        b[j] = 0.7 * total_usage  # 70% of max capacity

    # Constraint uncertainty coupling matrix B
    # FIXED: Scale relative to b magnitude for realistic uncertainty (10% typical)
    B = np.zeros((n_resources, n_factors_c))
    for j in range(n_resources):
        B[j, :] = np.random.randn(n_factors_c) * (0.10 * b[j])

    return RobustQPProblem(
        n_agents=n_agents,
        n_vars=n_vars,
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


def generate_problem_suite(
    sizes: List[Tuple[int, int, int]] = None,
    seed: int = 42,
) -> List[RobustQPProblem]:
    """
    Generate a suite of problems for testing.

    Args:
        sizes: List of (n_agents, avg_vars, n_resources) tuples
        seed: Base random seed

    Returns:
        List of RobustQPProblem instances

    Default sizes: small, medium, large
    """
    if sizes is None:
        sizes = [
            (10, 15, 5),    # Small
            (50, 20, 10),   # Medium
            (100, 30, 20),  # Large
        ]

    problems = []
    for i, (n_agents, avg_vars, n_res) in enumerate(sizes):
        prob = generate_robust_qp(
            n_agents=n_agents,
            avg_vars_per_agent=avg_vars,
            n_resources=n_res,
            n_factors_p=min(5, n_res),
            n_factors_c=min(5, n_res),
            uncertainty_radius_p=5.0,
            uncertainty_radius_c=2.0,
            seed=seed + i,
        )
        problems.append(prob)

    return problems


def tighten_uncertainty_radius_for_feasibility(
    problem: RobustQPProblem
) -> float:
    """
    Compute a safe constraint uncertainty radius that maintains feasibility.

    Ensures for each row j: b_j +/- rho_c * ||B_j||_2 fits within
    interval image of A_j x over box bounds.

    Args:
        problem: RobustQPProblem

    Returns:
        Safe radius (<= original uncertainty_radius_c)
    """
    n_total = sum(problem.n_vars)

    # Assemble full A matrix and bounds
    A_full = np.zeros((problem.n_resources, n_total))
    x_lo = np.zeros(n_total)
    x_hi = np.zeros(n_total)

    idx = 0
    for i in range(problem.n_agents):
        n_i = problem.n_vars[i]
        j = idx + n_i
        A_full[:, idx:j] = problem.A[i]
        x_lo[idx:j] = problem.x_lower[i]
        x_hi[idx:j] = problem.x_upper[i]
        idx = j

    # Interval bounds per row of A x
    A_pos = np.maximum(A_full, 0.0)
    A_neg = np.minimum(A_full, 0.0)
    Ax_min = A_pos @ x_lo + A_neg @ x_hi
    Ax_max = A_pos @ x_hi + A_neg @ x_lo

    # Allowed RHS wiggle given box bounds
    wiggle = np.minimum(problem.b - Ax_min, Ax_max - problem.b)
    wiggle = np.maximum(wiggle, 0.0)

    # Row norms of B
    B_norm = np.linalg.norm(problem.B, axis=1)

    mask = B_norm > 1e-12
    if np.any(mask):
        rho_c_max = np.min(wiggle[mask] / B_norm[mask])
        rho_c_safe = float(np.clip(rho_c_max, 0.0, problem.uncertainty_radius_c))
        return rho_c_safe
    else:
        return problem.uncertainty_radius_c


def assemble_full_matrices(problem: RobustQPProblem) -> Tuple[np.ndarray, ...]:
    """
    Assemble block-diagonal matrices into full matrices.

    Args:
        problem: RobustQPProblem

    Returns:
        Tuple of (Q_full, c_full, P_full, A_full, x_lower_full, x_upper_full)
    """
    n_total = sum(problem.n_vars)

    Q_full = np.zeros((n_total, n_total))
    c_full = np.zeros(n_total)
    P_full = np.zeros((n_total, problem.n_factors_p))
    A_full = np.zeros((problem.n_resources, n_total))
    x_lower_full = np.zeros(n_total)
    x_upper_full = np.zeros(n_total)

    idx = 0
    for i in range(problem.n_agents):
        n_i = problem.n_vars[i]
        j = idx + n_i

        Q_full[idx:j, idx:j] = problem.Q[i]
        c_full[idx:j] = problem.c[i]
        P_full[idx:j, :] = problem.P[i]
        A_full[:, idx:j] = problem.A[i]
        x_lower_full[idx:j] = problem.x_lower[i]
        x_upper_full[idx:j] = problem.x_upper[i]

        idx = j

    return Q_full, c_full, P_full, A_full, x_lower_full, x_upper_full


def generate_energy_dispatch_problem(
    n_buses: int = 14,
    n_timesteps: int = 24,
    n_generators: int = 5,
    n_storage: int = 2,
    renewable_penetration: float = 0.3,
    uncertainty_radius: float = 5.0,
    seed: Optional[int] = None,
) -> RobustQPProblem:
    """
    Generate a stylized energy dispatch problem (simplified IEEE-like).

    Args:
        n_buses: Number of buses/nodes
        n_timesteps: Time horizon (hours)
        n_generators: Number of generators
        n_storage: Number of storage units
        renewable_penetration: Fraction of renewable generation
        uncertainty_radius: Uncertainty radius (forecast error)
        seed: Random seed

    Returns:
        RobustQPProblem representing energy dispatch

    Note: This is a simplified version. Use ieee_loader.py for real IEEE systems.
    """
    if seed is not None:
        np.random.seed(seed)

    # Agents: generators (1 per gen), storage (1 per unit)
    n_agents = n_generators + n_storage
    n_vars = []
    c = []
    Q = []
    P = []
    A = []
    x_lower = []
    x_upper = []

    # Resources: nodal balance at each bus-time pair
    n_resources = n_buses * n_timesteps
    n_factors_p = n_buses  # Renewable uncertainty per bus (aggregate over time)
    n_factors_c = n_buses  # Demand uncertainty per bus

    # Generators
    for g in range(n_generators):
        # Each generator has n_timesteps variables (power output)
        n_g = n_timesteps
        n_vars.append(n_g)

        # Cost (quadratic: a + b*p + c*p^2)
        if g < int(renewable_penetration * n_generators):
            # Renewable: low cost
            c_g = np.zeros(n_g)  # Zero marginal cost
            Q_g = 0.001 * np.eye(n_g)  # Minimal quadratic
        else:
            # Conventional: higher cost
            c_g = np.random.uniform(30, 80, n_g)
            Q_g = 0.1 * np.eye(n_g)

        # Objective uncertainty (renewable forecast error)
        P_g = np.zeros((n_g, n_factors_p))
        if g < int(renewable_penetration * n_generators):
            # Renewable uncertainty affects this generator
            bus = np.random.randint(0, n_buses)
            P_g[:, bus] = np.random.uniform(0.3, 0.7, n_g)

        # Resource usage (which bus, which time)
        A_g = np.zeros((n_resources, n_g))
        bus = g % n_buses  # Assign generator to bus
        for t in range(n_timesteps):
            resource_idx = bus * n_timesteps + t
            A_g[resource_idx, t] = 1.0  # Generator output at (bus, t)

        # Capacity bounds
        if g < int(renewable_penetration * n_generators):
            capacity = np.random.uniform(50, 150, n_g)  # MW
        else:
            capacity = np.random.uniform(100, 300, n_g)

        x_lower_g = np.zeros(n_g)
        x_upper_g = capacity

        c.append(c_g)
        Q.append(Q_g)
        P.append(P_g)
        A.append(A_g)
        x_lower.append(x_lower_g)
        x_upper.append(x_upper_g)

    # Storage units
    for s in range(n_storage):
        # Variables: [charge, discharge, SOC] at each timestep
        n_s = 3 * n_timesteps
        n_vars.append(n_s)

        # Cost (variable O&M)
        c_s = np.full(n_s, -0.1)  # Small penalty for cycling
        Q_s = 0.001 * np.eye(n_s)

        # No direct uncertainty coupling
        P_s = np.zeros((n_s, n_factors_p))

        # Resource usage
        A_s = np.zeros((n_resources, n_s))
        bus = (n_generators + s) % n_buses
        for t in range(n_timesteps):
            resource_idx = bus * n_timesteps + t
            # Net discharge - charge
            A_s[resource_idx, 3*t + 1] = 1.0   # discharge
            A_s[resource_idx, 3*t] = -1.0      # charge

        # Bounds
        x_lower_s = np.zeros(n_s)
        x_upper_s = np.full(n_s, 50)  # MW power, MWh energy

        c.append(c_s)
        Q.append(Q_s)
        P.append(P_s)
        A.append(A_s)
        x_lower.append(x_lower_s)
        x_upper.append(x_upper_s)

    # Constraint uncertainty matrix B (demand uncertainty)
    B = np.zeros((n_resources, n_factors_c))
    for bus in range(n_buses):
        for t in range(n_timesteps):
            resource_idx = bus * n_timesteps + t
            B[resource_idx, bus] = 1.0  # Demand at bus affects all timesteps

    # Nominal demand (RHS)
    b = np.zeros(n_resources)
    for bus in range(n_buses):
        for t in range(n_timesteps):
            resource_idx = bus * n_timesteps + t
            # Demand profile (diurnal pattern)
            hour_of_day = t % 24
            demand = 100 + 50 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)  # MW
            b[resource_idx] = demand

    return RobustQPProblem(
        n_agents=n_agents,
        n_vars=n_vars,
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
        uncertainty_radius_p=uncertainty_radius,
        uncertainty_radius_c=uncertainty_radius * 0.5,  # Demand less uncertain
    )


if __name__ == "__main__":
    # Test problem generation
    print("Generating test problem...")
    prob = generate_robust_qp(n_agents=10, avg_vars_per_agent=20, n_resources=5, seed=42)

    print(f"Problem: {prob.n_agents} agents, {prob.total_vars()} total vars, {prob.n_resources} resources")
    print(f"Uncertainty: p-factors={prob.n_factors_p}, c-factors={prob.n_factors_c}")
    print(f"Radii: rho_p={prob.uncertainty_radius_p}, rho_c={prob.uncertainty_radius_c}")

    # Test feasibility tightening
    rho_safe = tighten_uncertainty_radius_for_feasibility(prob)
    print(f"Safe constraint radius: {rho_safe:.3f} (original: {prob.uncertainty_radius_c})")

    # Generate suite
    print("\nGenerating problem suite...")
    suite = generate_problem_suite(seed=42)
    for i, p in enumerate(suite):
        print(f"  Problem {i}: {p.n_agents} agents, {p.total_vars()} vars, {p.n_resources} resources")
