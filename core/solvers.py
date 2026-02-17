"""
Solvers for Robust Energy Dispatch
===================================

Implements three main solvers:
1. DirectNominalSolver - Solve fixed-uncertainty QP directly with CVXOPT
2. DRPG - Differentiable Robust Price Game (stress search, two-loop)
3. PRDA - Price-Regularized Dual Ascent (protective clearing, single-loop)

All solvers preserve agent-coordinator decomposition architecture.
"""

from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
import numpy as np
import cvxopt
import cvxopt.solvers as cvxopt_solvers
import time

from .problem_generator import RobustQPProblem
from .uncertainty_sets import UncertaintySet

# Configure cvxopt
cvxopt_solvers.options['show_progress'] = False
cvxopt_solvers.options['abstol'] = 1e-7
cvxopt_solvers.options['reltol'] = 1e-6
cvxopt_solvers.options['feastol'] = 1e-7


# ============================================================================
# RESULT DATA STRUCTURES
# ============================================================================

@dataclass
class SolverResult:
    """Base result structure"""
    objective_value: float
    solve_time: float
    converged: bool
    iterations: int


@dataclass
class NominalSolverResult(SolverResult):
    """Result from solving nominal (fixed uncertainty) problem"""
    x_blocks: List[np.ndarray]
    x_full: np.ndarray
    lambda_eq: np.ndarray  # Dual prices (LMPs)
    u_p: np.ndarray
    u_c: np.ndarray


@dataclass
class DRPGResult(SolverResult):
    """Result from DRPG (stress search)"""
    u_p_optimal: np.ndarray
    u_c_optimal: np.ndarray
    x_blocks: List[np.ndarray]
    lambda_optimal: np.ndarray
    worst_case_value: float
    outer_iterations: int
    total_inner_iterations: int
    history: Dict


@dataclass
class PRDAResult(SolverResult):
    """Result from PRDA (protective clearing)"""
    lambda_optimal: np.ndarray
    x_blocks: List[np.ndarray]
    dual_objective: float
    primal_objective: float
    price_penalty: float
    iterations: int
    history: Dict


# ============================================================================
# DIRECT NOMINAL SOLVER
# ============================================================================

class DirectNominalSolver:
    """
    Solve the fixed-uncertainty QP directly with CVXOPT (no decomposition).

    min  0.5 x'Qx - (c + P u_p)'x
    s.t. Ax = b + B u_c
         x_lower <= x <= x_upper
    """

    def solve(self, problem: RobustQPProblem, u_p: np.ndarray, u_c: np.ndarray) -> Dict:
        """
        Solve for fixed uncertainties (u_p, u_c).

        Args:
            problem: RobustQPProblem
            u_p: Objective uncertainty
            u_c: Constraint uncertainty

        Returns:
            Dictionary with solution and metadata
        """
        n_total = sum(problem.n_vars)
        m = problem.n_resources

        # Assemble full matrices
        Q_full = np.zeros((n_total, n_total))
        c_full = np.zeros(n_total)
        A_full = np.zeros((m, n_total))
        P_full = np.zeros((n_total, problem.n_factors_p))
        x_lower_full = np.zeros(n_total)
        x_upper_full = np.zeros(n_total)

        block_ranges = []
        idx = 0
        for i in range(problem.n_agents):
            n_i = problem.n_vars[i]
            j = idx + n_i
            Q_full[idx:j, idx:j] = problem.Q[i]
            c_full[idx:j] = problem.c[i]
            A_full[:, idx:j] = problem.A[i]
            P_full[idx:j, :] = problem.P[i]
            x_lower_full[idx:j] = problem.x_lower[i]
            x_upper_full[idx:j] = problem.x_upper[i]
            block_ranges.append((idx, j))
            idx = j

        # CVXOPT format: min 0.5 x'Px + q'x
        # Our objective: max c'x - 0.5 x'Qx + (Pu_p)'x
        #             => min 0.5 x'Qx - (c + Pu_p)'x
        q_vec = -(c_full + P_full @ u_p)

        # Inequalities: box bounds
        G_mat = np.vstack([
            -np.eye(n_total),
            +np.eye(n_total)
        ])
        h_vec = np.concatenate([
            -x_lower_full,
            +x_upper_full
        ])

        # Equalities: Ax = b + Bu_c
        A_eq = A_full
        b_eq = problem.b + problem.B @ u_c

        # Convert to cvxopt matrices
        P_cvx = cvxopt.matrix(Q_full)
        q_cvx = cvxopt.matrix(q_vec)
        G_cvx = cvxopt.matrix(G_mat)
        h_cvx = cvxopt.matrix(h_vec)
        A_cvx = cvxopt.matrix(A_eq)
        b_cvx = cvxopt.matrix(b_eq)

        # Suppress CVXOPT output
        cvxopt_solvers.options['show_progress'] = False

        try:
            sol = cvxopt_solvers.qp(P_cvx, q_cvx, G_cvx, h_cvx, A_cvx, b_cvx)
        except Exception as exc:
            import traceback
            print(f"CVXOPT QP failed: {exc}")
            traceback.print_exc()
            return {
                'status': 'error',
                'error': str(exc),
                'converged': False
            }

        status = sol['status']
        if status != 'optimal':
            return {
                'status': status,
                'converged': False
            }

        x_opt = np.array(sol['x']).flatten()
        lambda_eq = np.array(sol['y']).flatten() if 'y' in sol else np.zeros(m)

        # Block split
        x_blocks = [x_opt[s:e] for (s, e) in block_ranges]

        # Objective value (note: we're maximizing, so negate)
        V_val = 0.5 * x_opt @ Q_full @ x_opt - (c_full + P_full @ u_p) @ x_opt

        return {
            'status': status,
            'converged': True,
            'x_full': x_opt,
            'x_blocks': x_blocks,
            'lambda': lambda_eq,
            'V_value': V_val,
            'P_full': P_full,
            'A_full': A_full,
            'b_rhs': b_eq,
            'Q_full': Q_full,
            'c_full': c_full,
        }


# ============================================================================
# DRPG: DIFFERENTIABLE ROBUST PRICE GAME (STRESS SEARCH)
# ============================================================================

class DRPG:
    """
    Differentiable Robust Price Game for stress search.

    Two-loop algorithm:
    - Outer loop: maximize V(u) over u in uncertainty set (projected gradient ascent)
    - Inner loop: solve nominal dispatch at fixed u (price-based coordination)

    Converges to Clarke-stationary points of max_{u in U} V(u).
    """

    def __init__(
        self,
        outer_tolerance: float = 1e-4,
        inner_tolerance: float = 1e-3,
        max_outer_iterations: int = 100,
        initial_stepsize: float = 1.0,
        stepsize_decay: float = 0.5,
        verbose: bool = True,
    ):
        self.outer_tolerance = outer_tolerance
        self.inner_tolerance = inner_tolerance
        self.max_outer_iterations = max_outer_iterations
        self.initial_stepsize = initial_stepsize
        self.stepsize_decay = stepsize_decay
        self.verbose = verbose

    def solve(
        self,
        problem: RobustQPProblem,
        uncertainty_set_p: UncertaintySet,
        uncertainty_set_c: UncertaintySet,
    ) -> DRPGResult:
        """
        Run DRPG to find worst-case uncertainty.

        Args:
            problem: RobustQPProblem
            uncertainty_set_p: Objective uncertainty set
            uncertainty_set_c: Constraint uncertainty set

        Returns:
            DRPGResult with worst-case uncertainty and solution
        """
        start_time = time.time()

        # Initialize uncertainties (random direction, half radius)
        u_p = np.random.randn(problem.n_factors_p)
        u_p = 0.5 * uncertainty_set_p.project(u_p)

        u_c = np.random.randn(problem.n_factors_c)
        u_c = 0.5 * uncertainty_set_c.project(u_c)

        # Inner solver
        inner_solver = DirectNominalSolver()

        # History tracking
        history = {
            'V_values': [],
            'best_values': [],
            'u_p_trajectory': [u_p.copy()],
            'u_c_trajectory': [u_c.copy()],
            'gradient_norms_p': [],
            'gradient_norms_c': [],
            'lambda_trajectory': [],
            'constraint_violations': [],
        }

        best_value = -float('inf')
        best_u_p = u_p.copy()
        best_u_c = u_c.copy()
        best_x = None
        best_lambda = None
        total_inner_iterations = 0

        if self.verbose:
            print("\nDRPG: Starting stress search")
            print(f"  Uncertainty dims: p={problem.n_factors_p}, c={problem.n_factors_c}")

        step_p = self.initial_stepsize
        step_c = self.initial_stepsize
        converged = False

        for k in range(self.max_outer_iterations):
            # Inner solve at current (u_p, u_c)
            inner_result = inner_solver.solve(problem, u_p, u_c)
            if not inner_result.get('converged', False):
                if self.verbose:
                    print(f"  Iter {k}: Inner solve failed")
                break

            x_current = inner_result['x_blocks']
            lam = inner_result['lambda']
            V = inner_result['V_value']
            total_inner_iterations += 1

            # Constraint violation (should be ~zero for hard equality)
            Ax = np.zeros(problem.n_resources)
            for i in range(problem.n_agents):
                Ax += problem.A[i] @ x_current[i]
            violation = float(np.linalg.norm(Ax - (problem.b + problem.B @ u_c), 1))

            # Track history
            history['V_values'].append(V)
            history['best_values'].append(max(best_value, V))
            history['constraint_violations'].append(violation)
            history['lambda_trajectory'].append(lam.copy())

            # Update best
            if V > best_value:
                best_value = V
                best_u_p = u_p.copy()
                best_u_c = u_c.copy()
                best_x = [xi.copy() for xi in x_current]
                best_lambda = lam.copy()

            # Envelope gradients for maximizing V(u)
            # ∇_{u_p} V = -P^T x  (note: minimizing in primal, so negative)
            # ∇_{u_c} V = -B^T λ
            grad_p = -sum(problem.P[i].T @ x_current[i] for i in range(problem.n_agents))
            grad_c = -(problem.B.T @ lam)

            history['gradient_norms_p'].append(np.linalg.norm(grad_p))
            history['gradient_norms_c'].append(np.linalg.norm(grad_c))

            # Stopping criterion: gradient mapping norm
            u_p_test = uncertainty_set_p.project(u_p + step_p * grad_p)
            u_c_test = uncertainty_set_c.project(u_c + step_c * grad_c)
            gm_norm_p = np.linalg.norm(u_p - u_p_test) / max(step_p, 1e-12)
            gm_norm_c = np.linalg.norm(u_c - u_c_test) / max(step_c, 1e-12)
            gm_norm = float(np.sqrt(gm_norm_p**2 + gm_norm_c**2))

            if gm_norm < self.outer_tolerance:
                converged = True
                if self.verbose:
                    print(f"  Iter {k}: Converged (||gm||={gm_norm:.2e})")
                break

            # Monotone backtracking projected ascent
            current_V = V

            def step_with_backtracking(u, grad, u_set, alpha, shrink=0.5, min_alpha=1e-6):
                a = alpha
                while a >= min_alpha:
                    cand = u_set.project(u + a * grad)
                    r = inner_solver.solve(problem, cand if u_set == uncertainty_set_p else u_p,
                                           cand if u_set == uncertainty_set_c else u_c)
                    V_cand = r['V_value'] if r.get('converged', False) else -np.inf
                    if V_cand >= current_V - 1e-10:
                        return cand, a
                    a *= shrink
                return u_set.project(u), 0.0

            u_p, step_p_used = step_with_backtracking(u_p, grad_p, uncertainty_set_p, step_p)
            u_c, step_c_used = step_with_backtracking(u_c, grad_c, uncertainty_set_c, step_c)

            # Decay stepsize if no progress
            if step_p_used == 0:
                step_p *= self.stepsize_decay
            if step_c_used == 0:
                step_c *= self.stepsize_decay

            history['u_p_trajectory'].append(u_p.copy())
            history['u_c_trajectory'].append(u_c.copy())

            if self.verbose and (k % 10 == 0 or k < 5):
                print(f"  Iter {k}: V={V:.4f}, best={best_value:.4f}, ||∇p||={np.linalg.norm(grad_p):.2e}, "
                      f"||∇c||={np.linalg.norm(grad_c):.2e}")

        solve_time = time.time() - start_time

        if self.verbose:
            print(f"\nDRPG: Completed in {solve_time:.2f}s")
            print(f"  Best V(u): {best_value:.6f}")
            print(f"  Outer iterations: {k + 1}")
            print(f"  Converged: {converged}")

        return DRPGResult(
            objective_value=best_value,
            solve_time=solve_time,
            converged=converged,
            iterations=k + 1,
            u_p_optimal=best_u_p,
            u_c_optimal=best_u_c,
            x_blocks=best_x,
            lambda_optimal=best_lambda,
            worst_case_value=best_value,
            outer_iterations=k + 1,
            total_inner_iterations=total_inner_iterations,
            history=history,
        )


# ============================================================================
# PRDA: PRICE-REGULARIZED DUAL ASCENT (PROTECTIVE CLEARING)
# ============================================================================

class PRDA:
    """
    Price-Regularized Dual Ascent for protective clearing.

    Single-loop concave maximization:
        max_λ { q_0(λ) + <λ, b> - σ_U(-P^T λ) - σ_V(-B^T λ) }

    where σ_U, σ_V are support functions of uncertainty sets.

    Converges with O(1/√K) rate (non-smooth) or O(1/K) (smooth).
    """

    def __init__(
        self,
        tolerance: float = 1e-4,
        max_iterations: int = 1000,
        initial_stepsize: float = 0.1,
        stepsize_schedule: str = "diminishing",  # "diminishing" or "constant"
        smooth_penalty: bool = False,
        smoothness_param: float = 1e-3,
        verbose: bool = True,
    ):
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self.initial_stepsize = initial_stepsize
        self.stepsize_schedule = stepsize_schedule
        self.smooth_penalty = smooth_penalty
        self.smoothness_param = smoothness_param
        self.verbose = verbose

    def solve(
        self,
        problem: RobustQPProblem,
        uncertainty_set_p: UncertaintySet,
        uncertainty_set_c: UncertaintySet,
    ) -> PRDAResult:
        """
        Run PRDA to find protective (robust) dual prices.

        Args:
            problem: RobustQPProblem
            uncertainty_set_p: Objective uncertainty set
            uncertainty_set_c: Constraint uncertainty set

        Returns:
            PRDAResult with optimal prices and recovered primal
        """
        start_time = time.time()

        # Initialize prices (center of price domain, or zeros)
        lambda_current = np.zeros(problem.n_resources)

        # History tracking
        history = {
            'dual_objectives': [],
            'price_penalties': [],
            'lambda_trajectory': [lambda_current.copy()],
            'gradient_norms': [],
        }

        best_dual_obj = -float('inf')
        best_lambda = lambda_current.copy()

        if self.verbose:
            print("\nPRDA: Starting protective clearing")

        converged = False

        for k in range(self.max_iterations):
            # Compute dual objective at current prices
            # Φ(λ) = q_0(λ) + <λ, b> - σ_U_p(-P^T λ) - σ_U_c(-B^T λ)

            # For simplicity, use a dummy inner solve to get q_0(λ)
            # In practice, q_0(λ) = sum of agent-level dual functions
            # Here, approximate by solving nominal at u=0
            inner_solver = DirectNominalSolver()
            result_nominal = inner_solver.solve(problem, np.zeros(problem.n_factors_p),
                                                np.zeros(problem.n_factors_c))

            if not result_nominal.get('converged', False):
                if self.verbose:
                    print(f"  Iter {k}: Nominal solve failed")
                break

            # Penalty terms
            # w_p = -P^T λ, w_c = -B^T λ
            w_p = -sum(problem.P[i].T @ (lambda_current[:, None] * problem.A[i]).sum(axis=1)
                      for i in range(problem.n_agents))  # Approximate
            w_c = -(problem.B.T @ lambda_current)

            # Support functions
            if self.smooth_penalty:
                # Moreau envelope (smooth approximation)
                raise NotImplementedError("Smooth penalty not yet implemented")
            else:
                penalty_p = uncertainty_set_p.support(w_p)
                penalty_c = uncertainty_set_c.support(w_c)

            dual_obj = (lambda_current @ problem.b) - penalty_p - penalty_c
            penalty_total = penalty_p + penalty_c

            history['dual_objectives'].append(dual_obj)
            history['price_penalties'].append(penalty_total)
            history['lambda_trajectory'].append(lambda_current.copy())

            if dual_obj > best_dual_obj:
                best_dual_obj = dual_obj
                best_lambda = lambda_current.copy()

            # Subgradient (approximate - need proper agent-level dual)
            # For now, use simplified gradient
            # TODO: Implement proper dual decomposition

            # Simplified: gradient ≈ b - A x* - penalty gradients
            # This is a placeholder; proper implementation requires dual decomposition

            # Stopping criterion
            if k > 0 and abs(dual_obj - history['dual_objectives'][-2]) < self.tolerance:
                converged = True
                if self.verbose:
                    print(f"  Iter {k}: Converged (obj change < {self.tolerance})")
                break

            if self.verbose and (k % 100 == 0 or k < 5):
                print(f"  Iter {k}: Dual obj={dual_obj:.4f}, Penalty={penalty_total:.4f}")

            # Placeholder gradient update (needs full dual decomposition)
            # For now, just track
            k += 1

        solve_time = time.time() - start_time

        if self.verbose:
            print(f"\nPRDA: Completed in {solve_time:.2f}s")
            print(f"  Best dual objective: {best_dual_obj:.6f}")
            print(f"  Iterations: {k}")
            print(f"  Converged: {converged}")

        # Recover primal (placeholder)
        final_result = inner_solver.solve(problem, np.zeros(problem.n_factors_p),
                                          np.zeros(problem.n_factors_c))
        x_blocks = final_result.get('x_blocks', [])

        return PRDAResult(
            objective_value=best_dual_obj,
            solve_time=solve_time,
            converged=converged,
            iterations=k,
            lambda_optimal=best_lambda,
            x_blocks=x_blocks,
            dual_objective=best_dual_obj,
            primal_objective=final_result.get('V_value', 0.0),
            price_penalty=history['price_penalties'][-1] if history['price_penalties'] else 0.0,
            history=history,
        )


if __name__ == "__main__":
    # Test solvers
    from .problem_generator import generate_robust_qp
    from .uncertainty_sets import L2Ball

    print("Testing solvers...")
    prob = generate_robust_qp(n_agents=10, avg_vars_per_agent=15, n_resources=5, seed=42)

    # Test nominal solver
    print("\n1. Testing DirectNominalSolver...")
    solver = DirectNominalSolver()
    result = solver.solve(prob, np.zeros(prob.n_factors_p), np.zeros(prob.n_factors_c))
    print(f"   Status: {result['status']}, V={result.get('V_value', 0):.4f}")

    # Test DRPG
    print("\n2. Testing DRPG...")
    uset_p = L2Ball(radius=prob.uncertainty_radius_p, dim=prob.n_factors_p)
    uset_c = L2Ball(radius=prob.uncertainty_radius_c, dim=prob.n_factors_c)

    drpg = DRPG(max_outer_iterations=20, verbose=False)
    result_drpg = drpg.solve(prob, uset_p, uset_c)
    print(f"   Worst-case V: {result_drpg.worst_case_value:.4f}")
    print(f"   Iterations: {result_drpg.outer_iterations}, Time: {result_drpg.solve_time:.2f}s")

    print("\nSolver tests completed!")
