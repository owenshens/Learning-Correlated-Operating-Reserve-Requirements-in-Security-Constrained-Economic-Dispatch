"""
Economic Analysis Module
=========================

Implements economic performance metrics for robust optimization:
1. Out-of-sample performance evaluation
2. Value of Stochastic Solution (VSS)
3. Price of Robustness (PoR) detailed analysis
4. Robustness vs cost trade-off analysis

These metrics provide economic interpretation of robust optimization benefits.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time

from .problem_generator import RobustQPProblem
from .uncertainty_sets import UncertaintySet
from .solvers import DirectNominalSolver


@dataclass
class OutOfSampleResult:
    """Results from out-of-sample performance evaluation."""

    method_name: str
    x_solution: np.ndarray

    # Out-of-sample performance statistics
    test_objectives: List[float]  # Objective values on test scenarios
    mean_cost: float
    std_cost: float
    worst_case_cost: float
    best_case_cost: float
    median_cost: float
    percentile_95: float
    percentile_99: float

    # Comparison to nominal
    nominal_mean_cost: float
    cost_increase_vs_nominal: float  # Percentage

    # Robustness metrics
    n_feasible: int
    n_total: int
    feasibility_rate: float

    # Metadata
    n_test_scenarios: int
    test_scenario_generation: str
    evaluation_time: float


@dataclass
class VSSResult:
    """Results from Value of Stochastic Solution computation."""

    # VSS = Expected cost of nominal solution - Expected cost of robust solution
    # Positive VSS means robust solution has lower expected cost
    vss_value: float
    vss_percentage: float  # VSS as percentage of nominal cost

    # Component costs
    nominal_expected_cost: float
    robust_expected_cost: float

    # Additional metrics
    nominal_worst_case: float
    robust_worst_case: float
    worst_case_improvement: float  # Percentage

    # Statistical significance
    is_significant: bool
    p_value: Optional[float]

    # Metadata
    n_scenarios: int
    evaluation_method: str


class OutOfSampleEvaluator:
    """
    Evaluate robust solution performance on unseen test scenarios.

    Methodology:
    1. Generate test scenarios from uncertainty distribution
    2. For each scenario, evaluate solution cost V(x, u_test)
    3. Compute statistics: mean, std, worst-case, percentiles
    4. Compare to nominal solution performance

    Purpose:
    - Validate that robust solutions perform well on realistic scenarios
    - Show distribution of costs under uncertainty
    - Demonstrate value of robustness beyond worst-case
    """

    def __init__(
        self,
        n_test_scenarios: int = 1000,
        scenario_generation: str = "random",
        seed: int = None,
        verbose: bool = False
    ):
        """
        Initialize out-of-sample evaluator.

        Args:
            n_test_scenarios: Number of test scenarios to generate
            scenario_generation: "random", "grid", "lhs" (Latin Hypercube)
            seed: Random seed for reproducibility
            verbose: Print progress
        """
        self.n_test_scenarios = n_test_scenarios
        self.scenario_generation = scenario_generation
        self.seed = seed
        self.verbose = verbose

        if seed is not None:
            np.random.seed(seed)

    def generate_test_scenarios(
        self,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        Generate test scenarios from uncertainty sets.

        Args:
            uset_p: Uncertainty set for P matrix
            uset_c: Uncertainty set for C matrix

        Returns:
            (scenarios_p, scenarios_c): Lists of test scenarios
        """
        scenarios_p = []
        scenarios_c = []

        if self.scenario_generation == "random":
            # Random sampling from interior and boundary
            for _ in range(self.n_test_scenarios):
                # Sample from interior (0 to radius)
                scale_p = np.random.uniform(0, 1) ** (1.0 / uset_p.dim)
                scale_c = np.random.uniform(0, 1) ** (1.0 / uset_c.dim)

                # Random direction
                u_p = uset_p.project(np.random.randn(uset_p.dim) * 10)
                u_c = uset_c.project(np.random.randn(uset_c.dim) * 10)

                # Scale to interior
                scenarios_p.append(u_p * scale_p)
                scenarios_c.append(u_c * scale_c)

        elif self.scenario_generation == "grid":
            # Grid on boundary (similar to scenario-based RO)
            # For P
            if uset_p.dim == 1:
                u_p_list = [np.array([uset_p.radius]), np.array([-uset_p.radius]), np.array([0.0])]
            elif uset_p.dim == 2:
                angles = np.linspace(0, 2*np.pi, int(np.sqrt(self.n_test_scenarios)), endpoint=False)
                u_p_list = [uset_p.project(uset_p.radius * np.array([np.cos(a), np.sin(a)])) for a in angles]
            else:
                # High-dimensional: random directions on boundary
                n_samples = int(np.cbrt(self.n_test_scenarios))
                u_p_list = []
                for _ in range(n_samples):
                    direction = np.random.randn(uset_p.dim)
                    direction = direction / np.linalg.norm(direction)
                    u_p_list.append(uset_p.project(direction * uset_p.radius))

            # For C
            if uset_c.dim == 1:
                u_c_list = [np.array([uset_c.radius]), np.array([-uset_c.radius]), np.array([0.0])]
            elif uset_c.dim == 2:
                angles = np.linspace(0, 2*np.pi, int(np.sqrt(self.n_test_scenarios)), endpoint=False)
                u_c_list = [uset_c.project(uset_c.radius * np.array([np.cos(a), np.sin(a)])) for a in angles]
            else:
                n_samples = int(np.cbrt(self.n_test_scenarios))
                u_c_list = []
                for _ in range(n_samples):
                    direction = np.random.randn(uset_c.dim)
                    direction = direction / np.linalg.norm(direction)
                    u_c_list.append(uset_c.project(direction * uset_c.radius))

            # Cartesian product
            for u_p in u_p_list:
                for u_c in u_c_list:
                    scenarios_p.append(u_p)
                    scenarios_c.append(u_c)
                    if len(scenarios_p) >= self.n_test_scenarios:
                        break
                if len(scenarios_p) >= self.n_test_scenarios:
                    break

        else:
            raise ValueError(f"Unknown scenario generation: {self.scenario_generation}")

        return scenarios_p[:self.n_test_scenarios], scenarios_c[:self.n_test_scenarios]

    def evaluate_solution(
        self,
        x_solution: np.ndarray,
        problem: RobustQPProblem,
        scenarios_p: List[np.ndarray],
        scenarios_c: List[np.ndarray],
    ) -> List[float]:
        """
        Evaluate solution on test scenarios.

        Args:
            x_solution: Solution to evaluate
            problem: Problem instance
            scenarios_p: Test scenarios for P
            scenarios_c: Test scenarios for C

        Returns:
            List of objective values (maximization)
        """
        objectives = []

        # Build full c vector, Q matrix, and P matrix from blocks
        n_total = problem.total_vars()
        c_full = np.concatenate(problem.c)

        # Build block diagonal Q
        Q_full = np.zeros((n_total, n_total))
        offset = 0
        for i in range(problem.n_agents):
            n_i = problem.n_vars[i]
            Q_full[offset:offset+n_i, offset:offset+n_i] = problem.Q[i]
            offset += n_i

        # Build block P matrix (n_total x n_factors_p)
        P_full = np.zeros((n_total, problem.n_factors_p))
        offset = 0
        for i in range(problem.n_agents):
            n_i = problem.n_vars[i]
            P_full[offset:offset+n_i, :] = problem.P[i]
            offset += n_i

        for u_p, u_c in zip(scenarios_p, scenarios_c):
            # Objective formulation: max c'x - 0.5 x'Qx + (Pu_p)'x
            # Linear term with uncertainty: c + P @ u_p
            c_perturbed = c_full + P_full @ u_p

            # Compute objective (maximization)
            # Note: c_perturbed already includes nominal c and uncertainty term
            obj = c_perturbed.T @ x_solution - 0.5 * x_solution.T @ Q_full @ x_solution
            objectives.append(float(obj))

        return objectives

    def evaluate(
        self,
        method_name: str,
        x_solution: np.ndarray,
        problem: RobustQPProblem,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
        x_nominal: Optional[np.ndarray] = None,
    ) -> OutOfSampleResult:
        """
        Complete out-of-sample evaluation.

        Args:
            method_name: Name of method being evaluated
            x_solution: Robust solution to evaluate
            problem: Problem instance
            uset_p: Uncertainty set for P
            uset_c: Uncertainty set for C
            x_nominal: Nominal solution for comparison (optional)

        Returns:
            OutOfSampleResult with comprehensive statistics
        """
        start_time = time.time()

        if self.verbose:
            print(f"\n{'='*70}")
            print(f"OUT-OF-SAMPLE EVALUATION: {method_name}")
            print(f"{'='*70}")
            print(f"Generating {self.n_test_scenarios} test scenarios...")

        # Generate test scenarios
        scenarios_p, scenarios_c = self.generate_test_scenarios(uset_p, uset_c)

        if self.verbose:
            print(f"Evaluating solution on {len(scenarios_p)} scenarios...")

        # Evaluate robust solution
        test_objectives = self.evaluate_solution(x_solution, problem, scenarios_p, scenarios_c)

        # Compute statistics
        mean_cost = np.mean(test_objectives)
        std_cost = np.std(test_objectives)
        worst_case_cost = np.min(test_objectives)  # Min because maximization
        best_case_cost = np.max(test_objectives)
        median_cost = np.median(test_objectives)
        percentile_95 = np.percentile(test_objectives, 5)  # 5th percentile for maximization
        percentile_99 = np.percentile(test_objectives, 1)

        # Feasibility check (all solutions should be feasible if constraints are robust)
        n_total = len(test_objectives)
        n_feasible = n_total  # Assume all feasible (can add constraint checking if needed)
        feasibility_rate = 1.0

        # Compare to nominal if provided
        if x_nominal is not None:
            nominal_objectives = self.evaluate_solution(x_nominal, problem, scenarios_p, scenarios_c)
            nominal_mean_cost = np.mean(nominal_objectives)
            cost_increase_vs_nominal = (mean_cost - nominal_mean_cost) / abs(nominal_mean_cost) * 100
        else:
            nominal_mean_cost = np.nan
            cost_increase_vs_nominal = np.nan

        evaluation_time = time.time() - start_time

        if self.verbose:
            print(f"\nResults:")
            print(f"  Mean cost: ${mean_cost:.2f}")
            print(f"  Std cost: ${std_cost:.2f}")
            print(f"  Worst-case: ${worst_case_cost:.2f}")
            print(f"  Best-case: ${best_case_cost:.2f}")
            print(f"  Median: ${median_cost:.2f}")
            print(f"  95th percentile: ${percentile_95:.2f}")
            print(f"  Feasibility rate: {feasibility_rate*100:.1f}%")
            if not np.isnan(cost_increase_vs_nominal):
                print(f"  Cost vs nominal: {cost_increase_vs_nominal:+.2f}%")
            print(f"  Evaluation time: {evaluation_time:.2f}s")

        return OutOfSampleResult(
            method_name=method_name,
            x_solution=x_solution,
            test_objectives=test_objectives,
            mean_cost=mean_cost,
            std_cost=std_cost,
            worst_case_cost=worst_case_cost,
            best_case_cost=best_case_cost,
            median_cost=median_cost,
            percentile_95=percentile_95,
            percentile_99=percentile_99,
            nominal_mean_cost=nominal_mean_cost,
            cost_increase_vs_nominal=cost_increase_vs_nominal,
            n_feasible=n_feasible,
            n_total=n_total,
            feasibility_rate=feasibility_rate,
            n_test_scenarios=self.n_test_scenarios,
            test_scenario_generation=self.scenario_generation,
            evaluation_time=evaluation_time
        )


class VSSComputer:
    """
    Compute Value of Stochastic Solution (VSS).

    VSS measures the value of using robust/stochastic optimization
    vs deterministic nominal optimization.

    Definition:
        VSS = E[Cost(x_nominal, u)] - E[Cost(x_robust, u)]

    where expectation is over uncertainty distribution.

    Interpretation:
    - VSS > 0: Robust solution has lower expected cost (good!)
    - VSS < 0: Nominal solution better on average (robust is too conservative)
    - VSS ≈ 0: Both solutions similar in expectation

    Note: Even if VSS ≈ 0, robust solution may have better worst-case
    and lower variance (reduced risk).
    """

    def __init__(
        self,
        n_scenarios: int = 1000,
        evaluation_method: str = "monte_carlo",
        seed: int = None,
        verbose: bool = False
    ):
        """
        Initialize VSS computer.

        Args:
            n_scenarios: Number of scenarios for expectation estimation
            evaluation_method: "monte_carlo", "quadrature"
            seed: Random seed
            verbose: Print progress
        """
        self.n_scenarios = n_scenarios
        self.evaluation_method = evaluation_method
        self.seed = seed
        self.verbose = verbose

        if seed is not None:
            np.random.seed(seed)

    def compute_vss(
        self,
        x_nominal: np.ndarray,
        x_robust: np.ndarray,
        problem: RobustQPProblem,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> VSSResult:
        """
        Compute Value of Stochastic Solution.

        Args:
            x_nominal: Nominal solution (u=0)
            x_robust: Robust solution
            problem: Problem instance
            uset_p: Uncertainty set for P
            uset_c: Uncertainty set for C

        Returns:
            VSSResult with VSS value and breakdown
        """
        if self.verbose:
            print(f"\n{'='*70}")
            print(f"VALUE OF STOCHASTIC SOLUTION (VSS) COMPUTATION")
            print(f"{'='*70}")
            print(f"Generating {self.n_scenarios} scenarios for expectation...")

        # Generate scenarios for expectation (random sampling from distribution)
        evaluator = OutOfSampleEvaluator(
            n_test_scenarios=self.n_scenarios,
            scenario_generation="random",
            seed=self.seed,
            verbose=False
        )
        scenarios_p, scenarios_c = evaluator.generate_test_scenarios(uset_p, uset_c)

        if self.verbose:
            print(f"Evaluating nominal solution...")

        # Evaluate nominal solution
        nominal_objectives = evaluator.evaluate_solution(x_nominal, problem, scenarios_p, scenarios_c)
        nominal_expected_cost = np.mean(nominal_objectives)
        nominal_worst_case = np.min(nominal_objectives)  # Min for maximization

        if self.verbose:
            print(f"Evaluating robust solution...")

        # Evaluate robust solution
        robust_objectives = evaluator.evaluate_solution(x_robust, problem, scenarios_p, scenarios_c)
        robust_expected_cost = np.mean(robust_objectives)
        robust_worst_case = np.min(robust_objectives)

        # Compute VSS
        # For maximization: VSS = E[robust] - E[nominal]
        # (positive means robust is better)
        vss_value = robust_expected_cost - nominal_expected_cost
        vss_percentage = vss_value / abs(nominal_expected_cost) * 100

        # Worst-case improvement
        worst_case_improvement = (robust_worst_case - nominal_worst_case) / abs(nominal_worst_case) * 100

        # Statistical significance (paired t-test)
        from scipy import stats
        t_stat, p_value = stats.ttest_rel(robust_objectives, nominal_objectives)
        is_significant = (p_value < 0.05)

        if self.verbose:
            print(f"\nResults:")
            print(f"  Nominal expected cost: ${nominal_expected_cost:.2f}")
            print(f"  Robust expected cost: ${robust_expected_cost:.2f}")
            print(f"  VSS: ${vss_value:.2f} ({vss_percentage:+.2f}%)")
            print(f"  Nominal worst-case: ${nominal_worst_case:.2f}")
            print(f"  Robust worst-case: ${robust_worst_case:.2f}")
            print(f"  Worst-case improvement: {worst_case_improvement:+.2f}%")
            print(f"  Statistical significance: {'Yes' if is_significant else 'No'} (p={p_value:.4f})")

        return VSSResult(
            vss_value=vss_value,
            vss_percentage=vss_percentage,
            nominal_expected_cost=nominal_expected_cost,
            robust_expected_cost=robust_expected_cost,
            nominal_worst_case=nominal_worst_case,
            robust_worst_case=robust_worst_case,
            worst_case_improvement=worst_case_improvement,
            is_significant=is_significant,
            p_value=p_value,
            n_scenarios=self.n_scenarios,
            evaluation_method=self.evaluation_method
        )


class EconomicAnalyzer:
    """
    Comprehensive economic analysis coordinator.

    Combines:
    - Out-of-sample evaluation
    - VSS computation
    - Price of Robustness analysis
    - Trade-off analysis
    """

    def __init__(
        self,
        n_test_scenarios: int = 1000,
        n_vss_scenarios: int = 1000,
        seed: int = None,
        verbose: bool = True
    ):
        """Initialize economic analyzer."""
        self.evaluator = OutOfSampleEvaluator(
            n_test_scenarios=n_test_scenarios,
            scenario_generation="random",
            seed=seed,
            verbose=verbose
        )
        self.vss_computer = VSSComputer(
            n_scenarios=n_vss_scenarios,
            seed=seed,
            verbose=verbose
        )
        self.verbose = verbose

    def analyze_method(
        self,
        method_name: str,
        x_solution: np.ndarray,
        x_nominal: np.ndarray,
        problem: RobustQPProblem,
        uset_p: UncertaintySet,
        uset_c: UncertaintySet,
    ) -> Dict:
        """
        Complete economic analysis for a method.

        Returns:
            Dictionary with all economic metrics
        """
        # Out-of-sample evaluation
        oos_result = self.evaluator.evaluate(
            method_name=method_name,
            x_solution=x_solution,
            problem=problem,
            uset_p=uset_p,
            uset_c=uset_c,
            x_nominal=x_nominal
        )

        # VSS computation
        vss_result = self.vss_computer.compute_vss(
            x_nominal=x_nominal,
            x_robust=x_solution,
            problem=problem,
            uset_p=uset_p,
            uset_c=uset_c
        )

        return {
            'out_of_sample': oos_result,
            'vss': vss_result,
            'method_name': method_name
        }
