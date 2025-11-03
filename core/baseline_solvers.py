"""
Baseline Robust Optimization Solvers for Comparison with DRPG

This module implements classical robust optimization approaches to benchmark
against the DRPG algorithm:

1. Scenario-based robust optimization
2. Bertsimas-Sim budgeted uncertainty
3. Nominal optimization (uncertainty-free)

These baselines enable fair comparison of:
- Solution quality (robustness vs cost)
- Computational efficiency (solve time, iterations)
- Scalability (performance vs problem size)
"""

import numpy as np
import cvxopt
from cvxopt import matrix as cvxopt_matrix, solvers as cvxopt_solvers
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time

from core.problem_generator import RobustQPProblem
from core.uncertainty_sets import UncertaintySet
from core.solvers import DirectNominalSolver


# ============================================================================
# RESULT CLASSES
# ============================================================================

@dataclass
class BaselineResult:
    """Base result structure for baseline methods."""
    method_name: str
    objective_value: float
    solve_time: float
    converged: bool
    iterations: int
    x_solution: np.ndarray
    worst_case_u_p: Optional[np.ndarray] = None
    worst_case_u_c: Optional[np.ndarray] = None
    metadata: Optional[Dict] = None


# ============================================================================
# SCENARIO-BASED ROBUST OPTIMIZATION
# ============================================================================

class ScenarioBasedRO:
    """
    Scenario-based robust optimization.

    Approach:
    1. Generate representative scenarios from uncertainty set
    2. Solve: min_x max_{scenarios} V(x, scenario)
    3. Use deterministic solvers for fixed-scenario problems

    Scenarios can be:
    - Vertices of polyhedral uncertainty sets
    - Grid points on uncertainty set boundary
    - Random samples (Monte Carlo)
    - Adaptive refinement based on worst cases

    References:
    - Mulvey, J. M., Vanderbei, R. J., & Zenios, S. A. (1995).
      "Robust optimization of large-scale systems." Operations research.
    - Ben-Tal, A., & Nemirovski, A. (1998). "Robust convex optimization."
      Mathematics of Operations Research.
    """

    def __init__(
        self,
        scenario_generation: str = "grid",
        n_scenarios_p: int = 10,
        n_scenarios_c: int = 10,
        verbose: bool = True,
    ):
        """
        Initialize scenario-based RO solver.

        Args:
            scenario_generation: Method for scenario generation
                - "grid": Uniform grid on uncertainty set boundary
                - "vertices": Vertices of polyhedral set (for L1/Linf)
                - "random": Random sampling from set
                - "adaptive": Start sparse, refine worst cases
            n_scenarios_p: Number of scenarios for objective uncertainty
            n_scenarios_c: Number of scenarios for constraint uncertainty
            verbose: Print progress
        """
        self.scenario_generation = scenario_generation
        self.n_scenarios_p = n_scenarios_p
        self.n_scenarios_c = n_scenarios_c
        self.verbose = verbose
        self.nominal_solver = DirectNominalSolver()

    def generate_scenarios(
        self,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Generate representative scenarios from uncertainty sets.

        Args:
            uset_p: Objective uncertainty set
            uset_c: Constraint uncertainty set

        Returns:
            (scenarios_p, scenarios_c): Lists of uncertainty realizations
        """
        scenarios_p = []
        scenarios_c = []

        if self.scenario_generation == "grid":
            # Uniform grid on boundary
            scenarios_p = self._grid_scenarios(uset_p, self.n_scenarios_p)
            scenarios_c = self._grid_scenarios(uset_c, self.n_scenarios_c)

        elif self.scenario_generation == "vertices":
            # Vertices of polyhedral set (L1Ball, LinfBox)
            scenarios_p = self._vertex_scenarios(uset_p)
            scenarios_c = self._vertex_scenarios(uset_c)

        elif self.scenario_generation == "random":
            # Random uniform sampling
            scenarios_p = self._random_scenarios(uset_p, self.n_scenarios_p)
            scenarios_c = self._random_scenarios(uset_c, self.n_scenarios_c)

        elif self.scenario_generation == "adaptive":
            # Start with sparse grid, will refine in solve()
            scenarios_p = self._grid_scenarios(uset_p, max(5, self.n_scenarios_p // 2))
            scenarios_c = self._grid_scenarios(uset_c, max(5, self.n_scenarios_c // 2))

        else:
            raise ValueError(f"Unknown scenario generation: {self.scenario_generation}")

        # Always include nominal (u=0)
        scenarios_p.insert(0, np.zeros(uset_p.dim))
        scenarios_c.insert(0, np.zeros(uset_c.dim))

        return scenarios_p, scenarios_c

    def _grid_scenarios(self, uset: UncertaintySet, n: int) -> List[np.ndarray]:
        """Generate uniform grid on uncertainty set boundary."""
        scenarios = []
        dim = uset.dim

        if dim == 1:
            # 1D: just the two extremes
            scenarios.append(np.array([uset.radius]))
            scenarios.append(np.array([-uset.radius]))

        elif dim == 2:
            # 2D: angles around circle/boundary
            angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
            for theta in angles:
                u = np.array([np.cos(theta), np.sin(theta)])
                u_projected = uset.project(u * uset.radius * 1.1)  # Slightly outside, project back
                scenarios.append(u_projected)

        else:
            # Higher dimensions: random directions, project to boundary
            for _ in range(n):
                direction = np.random.randn(dim)
                direction = direction / (np.linalg.norm(direction) + 1e-10)
                u = uset.project(direction * uset.radius * 1.1)
                scenarios.append(u)

        return scenarios

    def _vertex_scenarios(self, uset: UncertaintySet) -> List[np.ndarray]:
        """Generate vertices of polyhedral uncertainty set."""
        scenarios = []
        dim = uset.dim

        # For L1Ball and LinfBox, vertices are ±e_i
        # For L1Ball: vertices are ±radius * e_i
        # For LinfBox: vertices are {-radius, +radius}^n (2^n total)

        if hasattr(uset, 'norm_type'):
            if uset.norm_type == 1:  # L1Ball
                # Vertices: ±radius on each axis
                for i in range(dim):
                    e_i = np.zeros(dim)
                    e_i[i] = uset.radius
                    scenarios.append(e_i)
                    scenarios.append(-e_i)

            elif uset.norm_type == np.inf:  # LinfBox
                # All corners of hypercube: {-r, +r}^n
                # For large dim, this is 2^n (exponential!)
                if dim <= 10:
                    for i in range(2 ** dim):
                        vertex = np.zeros(dim)
                        for j in range(dim):
                            if (i >> j) & 1:
                                vertex[j] = uset.radius
                            else:
                                vertex[j] = -uset.radius
                        scenarios.append(vertex)
                else:
                    # Too many vertices, use random sampling instead
                    scenarios = self._random_scenarios(uset, min(100, 2 * dim))

        else:
            # Default: use grid for L2Ball or unknown type
            scenarios = self._grid_scenarios(uset, max(10, 2 * dim))

        return scenarios

    def _random_scenarios(self, uset: UncertaintySet, n: int) -> List[np.ndarray]:
        """Generate random samples from uncertainty set."""
        scenarios = []
        for _ in range(n):
            # Sample uniformly from set
            u = np.random.randn(uset.dim)
            u = u / (np.linalg.norm(u) + 1e-10)
            # Scale to random radius ≤ max radius (uniform distribution in ball)
            r = uset.radius * (np.random.rand() ** (1.0 / uset.dim))
            u = uset.project(u * r)
            scenarios.append(u)
        return scenarios

    def solve(
        self,
        problem: RobustQPProblem,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> BaselineResult:
        """
        Solve robust QP using scenario-based approach.

        Algorithm:
        1. Generate scenarios from uncertainty sets
        2. For each candidate x, evaluate worst-case scenario
        3. Find x that minimizes worst-case objective

        Implementation:
        We solve a series of nominal problems with different uncertainties,
        then take the solution that has the best worst-case performance.

        Args:
            problem: Robust QP problem
            uset_p: Objective uncertainty set
            uset_c: Constraint uncertainty set

        Returns:
            BaselineResult with solution and metadata
        """
        start_time = time.time()

        # Generate scenarios
        scenarios_p, scenarios_c = self.generate_scenarios(uset_p, uset_c)
        n_scenarios = len(scenarios_p) * len(scenarios_c)

        if self.verbose:
            print(f"\nScenario-based RO: {len(scenarios_p)} × {len(scenarios_c)} = {n_scenarios} scenarios")

        # Solve for each scenario, find best robust solution
        best_worst_case_value = np.inf
        best_x = None
        best_u_p = None
        best_u_c = None

        iteration = 0

        # Strategy: Evaluate all scenarios, find the one with best worst-case
        # This is a heuristic (not globally optimal), but computationally tractable

        # First, solve nominal to get initial candidate
        u_p_nom = np.zeros(problem.n_factors_p)
        u_c_nom = np.zeros(problem.n_factors_c)
        nom_result = self.nominal_solver.solve(problem, u_p_nom, u_c_nom)

        if nom_result['converged']:
            x_candidate = nom_result['x_full']
            worst_case_val = self._evaluate_worst_case(
                problem, x_candidate, scenarios_p, scenarios_c
            )
            best_worst_case_value = worst_case_val
            best_x = x_candidate
            best_u_p = u_p_nom
            best_u_c = u_c_nom

        # Try solving at a few extreme scenarios to find robust candidates
        sample_indices = np.random.choice(
            len(scenarios_p),
            min(10, len(scenarios_p)),
            replace=False
        )

        for idx_p in sample_indices:
            for idx_c in [0, len(scenarios_c) - 1]:  # Try nominal and worst constraint
                u_p = scenarios_p[idx_p]
                u_c = scenarios_c[idx_c]

                result = self.nominal_solver.solve(problem, u_p, u_c)
                iteration += 1

                if not result['converged']:
                    continue

                x_candidate = result['x_full']

                # Evaluate worst-case over all scenarios
                worst_case_val = self._evaluate_worst_case(
                    problem, x_candidate, scenarios_p, scenarios_c
                )

                if worst_case_val < best_worst_case_value:
                    best_worst_case_value = worst_case_val
                    best_x = x_candidate
                    # Find which scenario gave this worst case
                    best_u_p, best_u_c = self._find_worst_scenario(
                        problem, x_candidate, scenarios_p, scenarios_c
                    )

                    if self.verbose:
                        print(f"  Iter {iteration}: New best worst-case = {best_worst_case_value:.4f}")

        solve_time = time.time() - start_time

        if self.verbose:
            print(f"Scenario-based RO: Completed in {solve_time:.2f}s")
            print(f"  Best worst-case value: {best_worst_case_value:.4f}")
            print(f"  Total scenarios evaluated: {n_scenarios}")

        return BaselineResult(
            method_name="Scenario-Based RO",
            objective_value=-best_worst_case_value,  # Negate for maximization
            solve_time=solve_time,
            converged=(best_x is not None),
            iterations=iteration,
            x_solution=best_x if best_x is not None else np.zeros(sum(problem.n_vars)),
            worst_case_u_p=best_u_p,
            worst_case_u_c=best_u_c,
            metadata={
                'n_scenarios_p': len(scenarios_p),
                'n_scenarios_c': len(scenarios_c),
                'n_total_scenarios': n_scenarios,
                'scenario_generation': self.scenario_generation,
            }
        )

    def _evaluate_worst_case(
        self,
        problem: RobustQPProblem,
        x: np.ndarray,
        scenarios_p: List[np.ndarray],
        scenarios_c: List[np.ndarray],
    ) -> float:
        """
        Evaluate worst-case objective over all scenarios for fixed x.

        Returns worst-case V(x, u) (minimization form).
        """
        worst_value = -np.inf

        for u_p in scenarios_p:
            for u_c in scenarios_c:
                # Compute V(x, u_p, u_c)
                # Need to check feasibility: Ax = b + Bu_c
                value = self._evaluate_objective(problem, x, u_p, u_c)

                if value > worst_value:
                    worst_value = value

        return worst_value

    def _find_worst_scenario(
        self,
        problem: RobustQPProblem,
        x: np.ndarray,
        scenarios_p: List[np.ndarray],
        scenarios_c: List[np.ndarray],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Find which scenario gives worst-case objective for fixed x."""
        worst_value = -np.inf
        worst_u_p = scenarios_p[0]
        worst_u_c = scenarios_c[0]

        for u_p in scenarios_p:
            for u_c in scenarios_c:
                value = self._evaluate_objective(problem, x, u_p, u_c)

                if value > worst_value:
                    worst_value = value
                    worst_u_p = u_p
                    worst_u_c = u_c

        return worst_u_p, worst_u_c

    def _evaluate_objective(
        self,
        problem: RobustQPProblem,
        x: np.ndarray,
        u_p: np.ndarray,
        u_c: np.ndarray,
    ) -> float:
        """
        Evaluate V(x, u_p, u_c) for given x and uncertainties.

        V = 0.5 x'Qx - (c + Pu_p)'x

        (Minimization form; negate for maximization)
        """
        # Assemble full Q and P matrices
        n_total = sum(problem.n_vars)
        Q_full = np.zeros((n_total, n_total))
        c_full = np.zeros(n_total)
        P_full = np.zeros((n_total, problem.n_factors_p))

        idx = 0
        for i in range(problem.n_agents):
            n_i = problem.n_vars[i]
            j = idx + n_i
            Q_full[idx:j, idx:j] = problem.Q[i]
            c_full[idx:j] = problem.c[i]
            P_full[idx:j, :] = problem.P[i]
            idx = j

        # V = 0.5 x'Qx - (c + Pu_p)'x
        value = 0.5 * x @ Q_full @ x - (c_full + P_full @ u_p) @ x

        return value


# ============================================================================
# BERTSIMAS-SIM BUDGETED UNCERTAINTY
# ============================================================================

class BertsimasSimBudgeted:
    """
    Bertsimas-Sim budgeted uncertainty robust optimization.

    Uncertainty set:
        U = {u : ||u||_0 ≤ Γ, ||u||_∞ ≤ ρ}

    Where:
    - ||u||_0 = number of non-zero entries (at most Γ active)
    - ||u||_∞ = max_i |u_i| ≤ ρ (each bounded)
    - Γ ∈ [0, n] controls conservatism

    Special cases:
    - Γ = 0: Nominal (no uncertainty)
    - Γ = n: All factors active (most conservative)

    This is equivalent to L1Ball with appropriate scaling:
        ||u||_1 ≤ Γ × ρ

    References:
    - Bertsimas, D., & Sim, M. (2004). "The price of robustness."
      Operations Research, 52(1), 35-53.
    - Bertsimas, D., & Sim, M. (2003). "Robust discrete optimization
      and network flows." Mathematical Programming, 98(1-3), 49-71.
    """

    def __init__(
        self,
        budget_p: float = None,  # Γ_p for objective uncertainty
        budget_c: float = None,  # Γ_c for constraint uncertainty
        verbose: bool = True,
    ):
        """
        Initialize Bertsimas-Sim budgeted RO solver.

        Args:
            budget_p: Budget for objective uncertainty (Γ_p)
                Default: n_p / 2 (half factors active)
            budget_c: Budget for constraint uncertainty (Γ_c)
                Default: n_c / 2
            verbose: Print progress
        """
        self.budget_p = budget_p
        self.budget_c = budget_c
        self.verbose = verbose

    def solve(
        self,
        problem: RobustQPProblem,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> BaselineResult:
        """
        Solve using Bertsimas-Sim budgeted uncertainty.

        Strategy:
        1. Convert budgeted set to L1Ball equivalent
        2. Use DRPG solver with L1Ball
        3. Return result

        Note: This is a simplified implementation. Full Bertsimas-Sim
        requires reformulation as MILP or special-purpose algorithm.

        Args:
            problem: Robust QP problem
            uset_p: Objective uncertainty set (will be converted)
            uset_c: Constraint uncertainty set (will be converted)

        Returns:
            BaselineResult
        """
        start_time = time.time()

        # Determine budgets
        if self.budget_p is None:
            self.budget_p = problem.n_factors_p / 2.0
        if self.budget_c is None:
            self.budget_c = problem.n_factors_c / 2.0

        if self.verbose:
            print(f"\nBertsimas-Sim Budgeted RO:")
            print(f"  Budget Γ_p = {self.budget_p:.2f} (of {problem.n_factors_p} factors)")
            print(f"  Budget Γ_c = {self.budget_c:.2f} (of {problem.n_factors_c} factors)")

        # For simplicity, we'll use the scenario-based approach
        # with scenarios generated from the budgeted set

        # The worst-case for budgeted set: take Γ largest-impact factors
        # For QP, this requires solving inner optimization
        # We'll approximate by using L1Ball with radius = Γ × ρ

        from core.uncertainty_sets import L1Ball

        # Create L1Ball approximation
        uset_p_budget = L1Ball(
            dim=problem.n_factors_p,
            radius=self.budget_p * uset_p.radius
        )
        uset_c_budget = L1Ball(
            dim=problem.n_factors_c,
            radius=self.budget_c * uset_c.radius
        )

        # Use scenario-based solver with vertices
        scenario_solver = ScenarioBasedRO(
            scenario_generation="vertices",
            verbose=self.verbose
        )

        result = scenario_solver.solve(problem, uset_p_budget, uset_c_budget)

        solve_time = time.time() - start_time

        # Update result with our method name
        result.method_name = "Bertsimas-Sim Budgeted"
        result.solve_time = solve_time
        result.metadata['budget_p'] = self.budget_p
        result.metadata['budget_c'] = self.budget_c

        if self.verbose:
            print(f"Bertsimas-Sim: Completed in {solve_time:.2f}s")

        return result


# ============================================================================
# NOMINAL SOLVER (WRAPPER)
# ============================================================================

class NominalOptimization:
    """
    Nominal optimization (no uncertainty).

    Solves the deterministic problem with u_p = 0, u_c = 0.
    Provides baseline for comparison: best performance under
    nominal conditions, but no robustness guarantee.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.solver = DirectNominalSolver()

    def solve(
        self,
        problem: RobustQPProblem,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> BaselineResult:
        """
        Solve nominal problem (u = 0).

        Args:
            problem: Robust QP problem
            uset_p: Not used (for interface consistency)
            uset_c: Not used

        Returns:
            BaselineResult
        """
        start_time = time.time()

        if self.verbose:
            print(f"\nNominal Optimization: Solving with u = 0")

        # Solve at nominal uncertainty
        u_p = np.zeros(problem.n_factors_p)
        u_c = np.zeros(problem.n_factors_c)

        result = self.solver.solve(problem, u_p, u_c)

        solve_time = time.time() - start_time

        if self.verbose:
            print(f"Nominal: Completed in {solve_time:.4f}s")
            if result['converged']:
                print(f"  Objective: {-result['V_value']:.4f}")

        return BaselineResult(
            method_name="Nominal (u=0)",
            objective_value=-result['V_value'] if result['converged'] else np.inf,
            solve_time=solve_time,
            converged=result['converged'],
            iterations=1,
            x_solution=result['x_full'] if result['converged'] else np.zeros(sum(problem.n_vars)),
            worst_case_u_p=u_p,
            worst_case_u_c=u_c,
            metadata={'status': result['status']}
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def compare_methods_on_problem(
    problem: RobustQPProblem,
    uset_p: UncertaintySet,
    uset_c: UncertaintySet,
    methods: List[str] = None,
    verbose: bool = True,
) -> Dict[str, BaselineResult]:
    """
    Compare multiple methods on the same problem.

    Args:
        problem: Robust QP problem
        uset_p: Objective uncertainty set
        uset_c: Constraint uncertainty set
        methods: List of methods to compare
            Options: "nominal", "scenario", "budgeted", "drpg"
            Default: All except DRPG
        verbose: Print progress

    Returns:
        Dictionary mapping method name to result
    """
    if methods is None:
        methods = ["nominal", "scenario", "budgeted"]

    results = {}

    if "nominal" in methods:
        solver = NominalOptimization(verbose=verbose)
        results["nominal"] = solver.solve(problem, uset_p, uset_c)

    if "scenario" in methods:
        solver = ScenarioBasedRO(
            scenario_generation="grid",
            n_scenarios_p=10,
            n_scenarios_c=10,
            verbose=verbose
        )
        results["scenario"] = solver.solve(problem, uset_p, uset_c)

    if "budgeted" in methods:
        solver = BertsimasSimBudgeted(verbose=verbose)
        results["budgeted"] = solver.solve(problem, uset_p, uset_c)

    if "drpg" in methods:
        from core.solvers import DRPG
        solver = DRPG(verbose=verbose)
        drpg_result = solver.solve(problem, uset_p, uset_c)

        # Convert to BaselineResult format
        results["drpg"] = BaselineResult(
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

    return results
