"""
Mathematical Utilities
======================

Additional mathematical functions for robust optimization:
- Projection operators
- Distance functions
- Gradient estimation
- Matrix utilities
"""

import numpy as np
from typing import Tuple, Optional, Callable


def project_simplex(y: np.ndarray) -> np.ndarray:
    """
    Project vector onto probability simplex: {x : x >= 0, sum(x) = 1}

    Uses efficient O(n log n) algorithm.

    Args:
        y: Input vector

    Returns:
        Projection onto simplex
    """
    n = len(y)
    if n == 0:
        return y

    # Sort in descending order
    u = np.sort(y)[::-1]
    cumsum = np.cumsum(u)

    # Find rho (largest index where condition holds)
    rho = np.where(u > (cumsum - 1) / np.arange(1, n + 1))[0][-1]

    # Compute threshold
    theta = (cumsum[rho] - 1) / (rho + 1)

    # Project
    return np.maximum(y - theta, 0)


def project_box(y: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """
    Project vector onto box constraints.

    Args:
        y: Input vector
        lower: Lower bounds
        upper: Upper bounds

    Returns:
        Clipped vector
    """
    return np.clip(y, lower, upper)


def mahalanobis_distance(x: np.ndarray, y: np.ndarray, Sigma_inv: np.ndarray) -> float:
    """
    Compute Mahalanobis distance: sqrt((x-y)' Σ^{-1} (x-y))

    Args:
        x: First vector
        y: Second vector
        Sigma_inv: Inverse covariance matrix

    Returns:
        Mahalanobis distance
    """
    diff = x - y
    return float(np.sqrt(diff @ Sigma_inv @ diff))


def numerical_gradient(
    f: Callable[[np.ndarray], float],
    x: np.ndarray,
    epsilon: float = 1e-6,
) -> np.ndarray:
    """
    Compute numerical gradient using finite differences.

    Args:
        f: Scalar function
        x: Point to evaluate gradient
        epsilon: Step size

    Returns:
        Gradient approximation
    """
    n = len(x)
    grad = np.zeros(n)

    for i in range(n):
        x_plus = x.copy()
        x_plus[i] += epsilon
        x_minus = x.copy()
        x_minus[i] -= epsilon

        grad[i] = (f(x_plus) - f(x_minus)) / (2 * epsilon)

    return grad


def check_psd(A: np.ndarray, tol: float = 1e-8) -> bool:
    """
    Check if matrix is positive semi-definite.

    Args:
        A: Matrix to check
        tol: Tolerance for eigenvalues

    Returns:
        True if PSD
    """
    if not np.allclose(A, A.T):
        return False  # Not symmetric

    eigenvalues = np.linalg.eigvalsh(A)
    return np.all(eigenvalues >= -tol)


def make_psd(A: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
    """
    Make matrix positive semi-definite by zeroing negative eigenvalues.

    Args:
        A: Input matrix
        epsilon: Minimum eigenvalue

    Returns:
        PSD matrix
    """
    # Symmetrize
    A_sym = (A + A.T) / 2

    # Eigenvalue decomposition
    eigenvalues, eigenvectors = np.linalg.eigh(A_sym)

    # Clip eigenvalues
    eigenvalues = np.maximum(eigenvalues, epsilon)

    # Reconstruct
    return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T


def matrix_norm(A: np.ndarray, ord: str = 'fro') -> float:
    """
    Compute matrix norm.

    Args:
        A: Matrix
        ord: Norm type ('fro', 'nuc', 2, -2, 1, -1, inf, -inf)

    Returns:
        Norm value
    """
    return float(np.linalg.norm(A, ord=ord))


def condition_number(A: np.ndarray) -> float:
    """
    Compute condition number of matrix (ratio of largest to smallest singular value).

    Args:
        A: Matrix

    Returns:
        Condition number
    """
    return float(np.linalg.cond(A))


def relative_error(x_true: np.ndarray, x_approx: np.ndarray, norm_ord: int = 2) -> float:
    """
    Compute relative error: ||x_true - x_approx|| / ||x_true||

    Args:
        x_true: True value
        x_approx: Approximate value
        norm_ord: Norm order (1, 2, inf)

    Returns:
        Relative error
    """
    numerator = np.linalg.norm(x_true - x_approx, ord=norm_ord)
    denominator = np.linalg.norm(x_true, ord=norm_ord)

    if denominator < 1e-12:
        return float(np.linalg.norm(x_true - x_approx, ord=norm_ord))
    else:
        return float(numerator / denominator)


def subgradient_mapping(
    x: np.ndarray,
    grad: np.ndarray,
    stepsize: float,
    projection_func: Callable[[np.ndarray], np.ndarray],
) -> np.ndarray:
    """
    Compute projected gradient (gradient mapping).

    g_α(x) = (x - proj(x + α * grad)) / α

    This is zero at stationary points of constrained problems.

    Args:
        x: Current point
        grad: Gradient/subgradient
        stepsize: Step size α
        projection_func: Projection onto feasible set

    Returns:
        Gradient mapping
    """
    x_test = projection_func(x + stepsize * grad)
    return (x - x_test) / stepsize


def armijo_backtracking(
    f: Callable[[np.ndarray], float],
    grad: np.ndarray,
    x: np.ndarray,
    direction: np.ndarray,
    initial_stepsize: float = 1.0,
    shrink_factor: float = 0.5,
    c1: float = 1e-4,
    max_backtracks: int = 50,
) -> float:
    """
    Armijo backtracking line search.

    Finds stepsize α such that:
        f(x + α d) <= f(x) + c1 * α * grad' d

    Args:
        f: Objective function
        grad: Gradient at x
        x: Current point
        direction: Search direction
        initial_stepsize: Initial α
        shrink_factor: Multiplicative decrease
        c1: Armijo constant
        max_backtracks: Maximum iterations

    Returns:
        Stepsize α
    """
    alpha = initial_stepsize
    f_x = f(x)
    grad_dot_d = grad @ direction

    for _ in range(max_backtracks):
        x_new = x + alpha * direction
        f_new = f(x_new)

        # Armijo condition
        if f_new <= f_x + c1 * alpha * grad_dot_d:
            return alpha

        alpha *= shrink_factor

    return alpha  # Return last stepsize even if not satisfied


def bfgs_update(
    H: np.ndarray,
    s: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """
    BFGS inverse Hessian update.

    H_{k+1} = (I - ρ s y') H_k (I - ρ y s') + ρ s s'

    where ρ = 1/(y' s), s = x_{k+1} - x_k, y = grad_{k+1} - grad_k

    Args:
        H: Current inverse Hessian approximation
        s: Step x_{k+1} - x_k
        y: Gradient difference

    Returns:
        Updated inverse Hessian
    """
    rho = 1.0 / (y @ s)
    I = np.eye(len(s))
    V = I - rho * np.outer(s, y)

    return V @ H @ V.T + rho * np.outer(s, s)


def sparse_random_matrix(
    m: int,
    n: int,
    density: float = 0.1,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Generate sparse random matrix.

    Args:
        m: Number of rows
        n: Number of columns
        density: Fraction of nonzero entries
        seed: Random seed

    Returns:
        Sparse matrix (dense format)
    """
    if seed is not None:
        np.random.seed(seed)

    A = np.zeros((m, n))
    n_nonzero = int(m * n * density)

    for _ in range(n_nonzero):
        i = np.random.randint(m)
        j = np.random.randint(n)
        A[i, j] = np.random.randn()

    return A


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """
    Compute KL divergence: D(p || q) = sum p_i log(p_i / q_i)

    Args:
        p: Probability distribution
        q: Reference distribution

    Returns:
        KL divergence
    """
    # Avoid log(0)
    mask = (p > 0) & (q > 0)
    return float(np.sum(p[mask] * np.log(p[mask] / q[mask])))


def wasserstein_distance_1d(p: np.ndarray, q: np.ndarray) -> float:
    """
    Compute 1-Wasserstein distance for 1D distributions (using CDFs).

    Args:
        p: First distribution (samples)
        q: Second distribution (samples)

    Returns:
        W1 distance
    """
    p_sorted = np.sort(p)
    q_sorted = np.sort(q)

    # Make equal length by interpolation
    n = max(len(p_sorted), len(q_sorted))
    p_interp = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(p_sorted)), p_sorted)
    q_interp = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(q_sorted)), q_sorted)

    return float(np.mean(np.abs(p_interp - q_interp)))
