"""
Uncertainty Set Classes for Robust Optimization
================================================

Implements 7 uncertainty set types with projection and linear oracle methods:
1. L2Ball - Euclidean ball (isotropic)
2. L1Ball - L1 ball (sparse deviations)
3. LinfBox - L-infinity box (worst-case per component)
4. TVBudgetSet - Total variation + box (smooth temporal profiles)
5. TopKSet - Top-K (Ky-Fan) norm (sparse spikes)
6. EllipsoidSet - Ellipsoid (correlated errors)
7. HybridSet - Intersection of multiple constraints

All sets implement:
- project(y): Euclidean projection onto set
- linear_oracle(g): argmax_{u in U} g^T u
- support(g): Support function σ_U(g) = max_{u in U} g^T u
- sample(n): Generate n feasible samples
- scale(tau): Return scaled set tau * U
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np
import cvxopt
import cvxopt.solvers as cvxopt_solvers

# Configure cvxopt for silent operation
cvxopt_solvers.options['show_progress'] = False
cvxopt_solvers.options['abstol'] = 1e-7
cvxopt_solvers.options['reltol'] = 1e-6
cvxopt_solvers.options['feastol'] = 1e-7
cvxopt_solvers.options['maxiters'] = 200


# ============================================================================
# BASE CLASS
# ============================================================================

class UncertaintySet(ABC):
    """
    Abstract base class for convex uncertainty sets.

    Attributes:
        dim: Dimension of uncertainty space
        name: Descriptive name
    """

    def __init__(self, dim: int, name: str = "generic"):
        self.dim = dim
        self.name = name

    @abstractmethod
    def project(self, y: np.ndarray) -> np.ndarray:
        """
        Euclidean projection: argmin_{u in U} ||u - y||_2^2

        Args:
            y: Point to project (dim,)

        Returns:
            Projected point u* in U
        """
        pass

    @abstractmethod
    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """
        Linear optimization: argmax_{u in U} g^T u

        Args:
            g: Linear objective (dim,)

        Returns:
            Optimal point s* in U
        """
        pass

    def support(self, g: np.ndarray) -> float:
        """
        Support function: σ_U(g) = max_{u in U} g^T u

        Default uses linear_oracle. Override for efficiency.

        Args:
            g: Direction vector (dim,)

        Returns:
            Support value
        """
        s = self.linear_oracle(g)
        return float(g @ s)

    def sample(self, n: int = 1) -> np.ndarray:
        """
        Generate n feasible samples from U.

        Args:
            n: Number of samples

        Returns:
            Samples array (n, dim)
        """
        raise NotImplementedError(f"{self.name} does not implement sampling")

    def scale(self, tau: float) -> 'UncertaintySet':
        """
        Return scaled set: tau * U

        Args:
            tau: Scaling factor

        Returns:
            New UncertaintySet
        """
        raise NotImplementedError(f"{self.name} does not implement scaling")


# ============================================================================
# L2 BALL
# ============================================================================

class L2Ball(UncertaintySet):
    """
    Euclidean ball: U = {u : ||u - center||_2 <= radius}

    Args:
        radius: Ball radius (ρ >= 0)
        center: Center point (default: origin)
        dim: Dimension (required if center not provided)
    """

    def __init__(self, radius: float, center: Optional[np.ndarray] = None, dim: Optional[int] = None):
        if center is not None:
            self.center = np.asarray(center, dtype=float)
            dim = len(self.center)
        elif dim is not None:
            self.center = np.zeros(dim, dtype=float)
        else:
            raise ValueError("Must provide either center or dim")

        self.radius = float(radius)
        super().__init__(dim=dim, name="L2Ball")

    def project(self, y: np.ndarray) -> np.ndarray:
        """Project onto L2 ball: u* = center + radius * (y - center) / max(||y - center||, radius)"""
        y = np.asarray(y, dtype=float)
        diff = y - self.center
        norm = np.linalg.norm(diff)

        if norm <= self.radius:
            return y.copy()
        else:
            return self.center + self.radius * diff / norm

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Linear oracle: u* = center + radius * g / ||g||"""
        g = np.asarray(g, dtype=float)
        norm = np.linalg.norm(g)

        if norm < 1e-12:
            return self.center.copy()
        else:
            return self.center + self.radius * g / norm

    def support(self, g: np.ndarray) -> float:
        """Support function: σ(g) = <g, center> + radius * ||g||_2"""
        g = np.asarray(g, dtype=float)
        return float(g @ self.center + self.radius * np.linalg.norm(g))

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample uniformly from ball interior"""
        # Generate uniform on sphere, scale by U[0,1]^(1/dim) for uniform volume
        samples = np.random.randn(n, self.dim)
        norms = np.linalg.norm(samples, axis=1, keepdims=True)
        samples = samples / (norms + 1e-12)  # On unit sphere

        # Scale by random radius
        radii = np.random.uniform(0, self.radius, size=(n, 1)) ** (1.0 / self.dim)
        samples = self.center + radii * samples

        return samples if n > 1 else samples[0]

    def scale(self, tau: float) -> 'L2Ball':
        """Scale: tau * (U - center) + center"""
        return L2Ball(radius=tau * self.radius, center=self.center)


# ============================================================================
# L1 BALL
# ============================================================================

class L1Ball(UncertaintySet):
    """
    L1 ball: U = {u : ||u - center||_1 <= radius}

    Promotes sparsity (many components zero or small).

    Args:
        radius: Ball radius (ρ >= 0)
        center: Center point (default: origin)
        dim: Dimension
    """

    def __init__(self, radius: float, center: Optional[np.ndarray] = None, dim: Optional[int] = None):
        if center is not None:
            self.center = np.asarray(center, dtype=float)
            dim = len(self.center)
        elif dim is not None:
            self.center = np.zeros(dim, dtype=float)
        else:
            raise ValueError("Must provide either center or dim")

        self.radius = float(radius)
        super().__init__(dim=dim, name="L1Ball")

    def project(self, y: np.ndarray) -> np.ndarray:
        """Project onto L1 ball using sorting algorithm"""
        y = np.asarray(y, dtype=float)
        v = y - self.center

        if np.sum(np.abs(v)) <= self.radius:
            return y.copy()

        # Projection algorithm (Duchi et al., 2008)
        u = np.abs(v)
        idx = np.argsort(u)[::-1]  # Descending order
        u_sorted = u[idx]

        cumsum = np.cumsum(u_sorted)
        rho_vals = (cumsum - self.radius) / np.arange(1, self.dim + 1)

        rho_idx = np.where(u_sorted > rho_vals)[0]
        if len(rho_idx) == 0:
            theta = 0.0
        else:
            rho = rho_idx[-1]
            theta = rho_vals[rho]

        w = np.sign(v) * np.maximum(u - theta, 0)
        return self.center + w

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Linear oracle: u* = center + radius * sign(g_max) * e_{argmax|g|}"""
        g = np.asarray(g, dtype=float)
        idx = np.argmax(np.abs(g))

        u = self.center.copy()
        u[idx] += self.radius * np.sign(g[idx])
        return u

    def support(self, g: np.ndarray) -> float:
        """Support function: σ(g) = <g, center> + radius * ||g||_inf"""
        g = np.asarray(g, dtype=float)
        return float(g @ self.center + self.radius * np.max(np.abs(g)))

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample using Dirichlet distribution"""
        # Sample from L1 ball using Dirichlet
        samples = np.zeros((n, self.dim))
        for i in range(n):
            # Dirichlet gives points on simplex; extend to full L1 ball
            alpha = np.ones(self.dim)
            w = np.random.dirichlet(alpha)
            signs = np.random.choice([-1, 1], size=self.dim)
            radius_scale = np.random.uniform(0, self.radius)
            samples[i] = self.center + radius_scale * signs * w

        return samples if n > 1 else samples[0]

    def scale(self, tau: float) -> 'L1Ball':
        return L1Ball(radius=tau * self.radius, center=self.center)


# ============================================================================
# LINF BOX
# ============================================================================

class LinfBox(UncertaintySet):
    """
    L-infinity box: U = {u : ||u - center||_inf <= radius}

    Equivalent to box constraints: center_i - radius <= u_i <= center_i + radius
    Most conservative (allows worst-case in every component).

    Args:
        radius: Box half-width (scalar or per-dimension array)
        center: Center point
        dim: Dimension
    """

    def __init__(self, radius: float, center: Optional[np.ndarray] = None, dim: Optional[int] = None):
        if center is not None:
            self.center = np.asarray(center, dtype=float)
            dim = len(self.center)
        elif dim is not None:
            self.center = np.zeros(dim, dtype=float)
        else:
            raise ValueError("Must provide either center or dim")

        # Allow per-dimension radius
        if np.isscalar(radius):
            self.radius = radius * np.ones(dim, dtype=float)
        else:
            self.radius = np.asarray(radius, dtype=float)
            assert len(self.radius) == dim

        super().__init__(dim=dim, name="LinfBox")

    def project(self, y: np.ndarray) -> np.ndarray:
        """Project onto box: elementwise clipping"""
        y = np.asarray(y, dtype=float)
        return np.clip(y, self.center - self.radius, self.center + self.radius)

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Linear oracle: u_i* = center_i + radius_i * sign(g_i)"""
        g = np.asarray(g, dtype=float)
        return self.center + self.radius * np.sign(g)

    def support(self, g: np.ndarray) -> float:
        """Support function: σ(g) = <g, center> + sum_i radius_i * |g_i| = <g, center> + ||diag(radius) g||_1"""
        g = np.asarray(g, dtype=float)
        return float(g @ self.center + np.sum(self.radius * np.abs(g)))

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample uniformly from box"""
        samples = np.random.uniform(-1, 1, size=(n, self.dim))
        samples = self.center + self.radius * samples
        return samples if n > 1 else samples[0]

    def scale(self, tau: float) -> 'LinfBox':
        return LinfBox(radius=tau * self.radius, center=self.center)


# ============================================================================
# TV-BUDGET SET (from double_uncertainty_general.py)
# ============================================================================

class TVBudgetSet(UncertaintySet):
    """
    Total Variation Budget + Box: U = {u: |u - μ| ≤ r, ||D(u - μ)||_1 ≤ Γ}

    Realistic for renewable energy (smooth temporal profiles, limited ramps).
    D is first-difference matrix.

    Args:
        r: Per-element bounds (T,) or scalar
        Gamma: TV budget (total variation limit)
        mu: Center/nominal point (T,), default zeros
    """

    def __init__(self, r: np.ndarray, Gamma: float, mu: Optional[np.ndarray] = None):
        self.r = np.asarray(r, dtype=float) if not np.isscalar(r) else r * np.ones(len(mu) if mu is not None else 1)
        self.T = len(self.r)
        self.D = self._diff_matrix(self.T)
        self.Gamma = float(Gamma)
        self.mu = np.zeros_like(self.r) if mu is None else np.asarray(mu, dtype=float)
        super().__init__(dim=self.T, name="TVBudget")

    @staticmethod
    def _diff_matrix(T: int) -> np.ndarray:
        """First-difference matrix D[t,:] = [-1, +1] at [t, t+1]"""
        D = np.zeros((T - 1, T))
        for t in range(T - 1):
            D[t, t] = -1.0
            D[t, t + 1] = 1.0
        return D

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Solve LP: max g^T u s.t. |u - μ| ≤ r, ||D(u - μ)||_1 ≤ Γ"""
        g = np.asarray(g, dtype=float)
        T = self.T
        m = T - 1

        # Variables: x = [u (T); z (m)] where z bounds |D(u-μ)|
        c = cvxopt.matrix(np.hstack([-g, np.zeros(m)]))

        # Constraints
        G_blocks = []
        h_blocks = []

        # Box: u ≤ μ + r
        G_blocks.append(np.hstack([np.eye(T), np.zeros((T, m))]))
        h_blocks.append(self.mu + self.r)

        # Box: -u ≤ -(μ - r)
        G_blocks.append(np.hstack([-np.eye(T), np.zeros((T, m))]))
        h_blocks.append(-(self.mu - self.r))

        # TV: D u - z ≤ D μ
        G_blocks.append(np.hstack([self.D, -np.eye(m)]))
        h_blocks.append(self.D @ self.mu)

        # TV: -D u - z ≤ -D μ
        G_blocks.append(np.hstack([-self.D, -np.eye(m)]))
        h_blocks.append(-self.D @ self.mu)

        # z ≥ 0
        G_blocks.append(np.hstack([np.zeros((m, T)), -np.eye(m)]))
        h_blocks.append(np.zeros(m))

        # 1^T z ≤ Γ
        G_blocks.append(np.hstack([np.zeros((1, T)), np.ones((1, m))]))
        h_blocks.append(np.array([self.Gamma]))

        G = cvxopt.matrix(np.vstack(G_blocks))
        h = cvxopt.matrix(np.hstack(h_blocks))

        try:
            sol = cvxopt.solvers.lp(c, G, h)
            if sol['status'] != 'optimal':
                return self.mu.copy()
            x = np.array(sol['x']).flatten()
            return x[:T]
        except Exception:
            return self.mu.copy()

    def project(self, y: np.ndarray) -> np.ndarray:
        """QP projection onto TV-budget set"""
        y = np.asarray(y, dtype=float)
        T = self.T
        m = T - 1

        # Variables: x = [u (T); z (m)]
        P = np.zeros((T + m, T + m))
        P[:T, :T] = np.eye(T)
        q = np.hstack([-y, np.zeros(m)])

        P_cvx = cvxopt.matrix(P)
        q_cvx = cvxopt.matrix(q)

        # Same constraints as linear_oracle
        G_blocks = []
        h_blocks = []

        G_blocks.append(np.hstack([np.eye(T), np.zeros((T, m))]))
        h_blocks.append(self.mu + self.r)
        G_blocks.append(np.hstack([-np.eye(T), np.zeros((T, m))]))
        h_blocks.append(-(self.mu - self.r))
        G_blocks.append(np.hstack([self.D, -np.eye(m)]))
        h_blocks.append(self.D @ self.mu)
        G_blocks.append(np.hstack([-self.D, -np.eye(m)]))
        h_blocks.append(-self.D @ self.mu)
        G_blocks.append(np.hstack([np.zeros((m, T)), -np.eye(m)]))
        h_blocks.append(np.zeros(m))
        G_blocks.append(np.hstack([np.zeros((1, T)), np.ones((1, m))]))
        h_blocks.append(np.array([self.Gamma]))

        G = cvxopt.matrix(np.vstack(G_blocks))
        h = cvxopt.matrix(np.hstack(h_blocks))

        try:
            sol = cvxopt.solvers.qp(P_cvx, q_cvx, G, h)
            if sol['status'] != 'optimal':
                return np.clip(y, self.mu - self.r, self.mu + self.r)
            x = np.array(sol['x']).flatten()
            return x[:T]
        except Exception:
            return np.clip(y, self.mu - self.r, self.mu + self.r)

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample using AR(1) + projection"""
        phi = 0.8
        sigma = 0.2 * np.mean(self.r)
        samples = []
        for _ in range(n):
            e = np.zeros(self.T)
            for t in range(1, self.T):
                e[t] = phi * e[t - 1] + np.random.normal(0, sigma)
            y = self.mu + e
            u = self.project(y)
            samples.append(u)
        return np.vstack(samples) if n > 1 else samples[0]

    def scale(self, tau: float) -> 'TVBudgetSet':
        return TVBudgetSet(r=tau * self.r, Gamma=tau * self.Gamma, mu=self.mu)


# ============================================================================
# TOP-K (KY-FAN) SET
# ============================================================================

class TopKSet(UncertaintySet):
    """
    Top-K (Ky-Fan) Norm + Box: U = {u: Σᵢ₌₁ᴷ |u|₍ᵢ₎ ≤ Γ, ||u||_∞ ≤ r}

    Captures sparse spikes (rare extreme events).
    |u|₍ᵢ₎ are order statistics (sorted absolute values).

    Args:
        K: Number of largest components
        Gamma: Budget for top-K sum
        r: Element-wise bound
        dim: Dimension
    """

    def __init__(self, K: int, Gamma: float, r: float, dim: int):
        self.K = int(K)
        self.Gamma = float(Gamma)
        self.r = float(r)
        super().__init__(dim=dim, name="TopK")

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Water-filling algorithm for Top-K + box"""
        g = np.asarray(g, dtype=float)
        u = np.zeros_like(g)

        if self.K <= 0 or self.Gamma <= 0:
            return u

        # Special case: budget allows filling all K entries to capacity
        if self.Gamma >= self.K * self.r:
            return self.r * np.sign(g)

        # Water-filling: sort by |g| descending
        order = np.argsort(-np.abs(g))
        budget = self.Gamma
        limit = min(self.K, len(g))

        for idx in order[:limit]:
            if budget <= 1e-14:
                break
            allocation = min(self.r, budget)
            u[idx] = np.sign(g[idx]) * allocation
            budget -= allocation

        return u

    def project(self, y: np.ndarray) -> np.ndarray:
        """Approximate projection (use box projection as fallback)"""
        # Exact projection for Top-K + box is complex; use iterative method
        # For now, fallback to box projection
        y = np.asarray(y, dtype=float)
        return np.clip(y, -self.r, self.r)

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample with random sparse patterns"""
        samples = []
        for _ in range(n):
            u = np.zeros(self.dim)
            k = np.random.randint(1, self.K + 1)
            indices = np.random.choice(self.dim, k, replace=False)

            # Allocate budget randomly across k indices
            allocations = np.random.dirichlet(np.ones(k)) * self.Gamma
            allocations = np.minimum(allocations, self.r)

            signs = np.random.choice([-1, 1], size=k)
            u[indices] = signs * allocations
            samples.append(u)

        return np.vstack(samples) if n > 1 else samples[0]

    def scale(self, tau: float) -> 'TopKSet':
        return TopKSet(K=self.K, Gamma=tau * self.Gamma, r=tau * self.r, dim=self.dim)


# ============================================================================
# ELLIPSOID SET
# ============================================================================

class EllipsoidSet(UncertaintySet):
    """
    Ellipsoid: U = {u : (u - center)^T Σ^{-1} (u - center) ≤ ρ²}

    Captures correlated errors (principal directions from covariance).

    Args:
        Sigma: Covariance matrix (must be positive definite)
        rho: Ellipsoid radius (Mahalanobis distance)
        center: Center point
    """

    def __init__(self, Sigma: np.ndarray, rho: float, center: Optional[np.ndarray] = None):
        self.Sigma = np.asarray(Sigma, dtype=float)
        self.rho = float(rho)
        dim = len(self.Sigma)
        self.center = np.zeros(dim) if center is None else np.asarray(center, dtype=float)

        # Precompute Cholesky factorization: Σ = L L^T
        try:
            self.L = np.linalg.cholesky(self.Sigma)
            self.L_inv = np.linalg.inv(self.L)
        except np.linalg.LinAlgError:
            # Fallback to eigendecomposition if not positive definite
            eigvals, eigvecs = np.linalg.eigh(self.Sigma)
            eigvals = np.maximum(eigvals, 1e-8)  # Regularize
            self.L = eigvecs @ np.diag(np.sqrt(eigvals))
            self.L_inv = np.diag(1.0 / np.sqrt(eigvals)) @ eigvecs.T

        super().__init__(dim=dim, name="Ellipsoid")

    def project(self, y: np.ndarray) -> np.ndarray:
        """Project onto ellipsoid"""
        y = np.asarray(y, dtype=float)
        v = y - self.center

        # Transform to unit ball: z = L^{-1} v
        z = self.L_inv @ v
        norm_z = np.linalg.norm(z)

        if norm_z <= self.rho:
            return y.copy()
        else:
            # Project z onto ball, transform back
            z_proj = self.rho * z / norm_z
            v_proj = self.L @ z_proj
            return self.center + v_proj

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Linear oracle: u* = center + ρ * Σ^{1/2} g / ||Σ^{1/2} g||"""
        g = np.asarray(g, dtype=float)
        v = self.L @ g  # v = Σ^{1/2} g
        norm_v = np.linalg.norm(v)

        if norm_v < 1e-12:
            return self.center.copy()
        else:
            return self.center + self.rho * v / norm_v

    def support(self, g: np.ndarray) -> float:
        """Support function: σ(g) = <g, center> + ρ * ||Σ^{1/2} g||_2"""
        g = np.asarray(g, dtype=float)
        v = self.L @ g
        return float(g @ self.center + self.rho * np.linalg.norm(v))

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample from ellipsoid interior"""
        # Sample from unit ball, transform
        z = np.random.randn(n, self.dim)
        z = z / (np.linalg.norm(z, axis=1, keepdims=True) + 1e-12)
        radii = np.random.uniform(0, self.rho, size=(n, 1)) ** (1.0 / self.dim)
        z = radii * z

        samples = self.center + (self.L @ z.T).T
        return samples if n > 1 else samples[0]

    def scale(self, tau: float) -> 'EllipsoidSet':
        return EllipsoidSet(Sigma=self.Sigma, rho=tau * self.rho, center=self.center)


# ============================================================================
# HYBRID SET (Intersection)
# ============================================================================

class HybridSet(UncertaintySet):
    """
    Hybrid set: intersection of multiple uncertainty sets.
    U = U1 ∩ U2 ∩ ... ∩ UK

    Example: Ellipsoid ∩ TV-Budget ∩ Box (most realistic for renewables)

    Args:
        sets: List of UncertaintySet objects (must have same dim)
    """

    def __init__(self, sets: list):
        assert len(sets) > 0, "Must provide at least one set"
        assert all(s.dim == sets[0].dim for s in sets), "All sets must have same dimension"

        self.sets = sets
        super().__init__(dim=sets[0].dim, name="Hybrid")

    def project(self, y: np.ndarray) -> np.ndarray:
        """Alternating projections (Dykstra's algorithm)"""
        y = np.asarray(y, dtype=float)
        x = y.copy()

        # Dykstra's alternating projection
        max_iter = 100
        tol = 1e-6
        increments = [np.zeros_like(y) for _ in self.sets]

        for _ in range(max_iter):
            x_old = x.copy()
            for i, uset in enumerate(self.sets):
                y_temp = x + increments[i]
                x = uset.project(y_temp)
                increments[i] = y_temp - x

            if np.linalg.norm(x - x_old) < tol:
                break

        return x

    def linear_oracle(self, g: np.ndarray) -> np.ndarray:
        """Approximate: solve via projection (no closed form in general)"""
        # Use gradient ascent on g^T u, projecting onto intersection
        g = np.asarray(g, dtype=float)
        u = np.zeros(self.dim)

        step = 0.1
        max_iter = 50
        for _ in range(max_iter):
            u_new = u + step * g
            u_new = self.project(u_new)
            if np.linalg.norm(u_new - u) < 1e-6:
                break
            u = u_new
            step *= 0.99

        return u

    def sample(self, n: int = 1) -> np.ndarray:
        """Sample via rejection sampling"""
        samples = []
        attempts = 0
        max_attempts = n * 100

        while len(samples) < n and attempts < max_attempts:
            # Sample from first set, check if in all others
            candidate = self.sets[0].sample(1)

            # Check membership in all other sets (approximate via projection distance)
            valid = True
            for uset in self.sets[1:]:
                proj = uset.project(candidate)
                if np.linalg.norm(proj - candidate) > 1e-6:
                    valid = False
                    break

            if valid:
                samples.append(candidate)
            attempts += 1

        if len(samples) < n:
            # Fallback: return projected samples
            while len(samples) < n:
                candidate = self.sets[0].sample(1)
                samples.append(self.project(candidate))

        return np.vstack(samples) if n > 1 else samples[0]

    def scale(self, tau: float) -> 'HybridSet':
        return HybridSet([s.scale(tau) for s in self.sets])


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_uncertainty_set(set_type: str, **kwargs) -> UncertaintySet:
    """
    Factory function to create uncertainty sets.

    Args:
        set_type: One of ["l2", "l1", "linf", "tv", "topk", "ellipsoid", "hybrid"]
        **kwargs: Parameters for the specific set type

    Returns:
        UncertaintySet instance

    Example:
        >>> uset = create_uncertainty_set("l2", radius=5.0, dim=10)
        >>> uset = create_uncertainty_set("tv", r=1.0, Gamma=5.0, mu=np.zeros(24))
    """
    # Normalize: lowercase and strip common suffixes
    set_type = set_type.lower()
    for suffix in ['ball', 'box', 'set', 'budget']:
        set_type = set_type.replace(suffix, '')

    if set_type in ["l2", ""]:  # Empty after stripping is also l2
        return L2Ball(**kwargs)
    elif set_type == "l1":
        return L1Ball(**kwargs)
    elif set_type in ["linf", "l∞"]:
        return LinfBox(**kwargs)
    elif set_type == "tv":
        return TVBudgetSet(**kwargs)
    elif set_type == "topk":
        return TopKSet(**kwargs)
    elif set_type == "ellipsoid":
        return EllipsoidSet(**kwargs)
    elif set_type == "hybrid":
        return HybridSet(**kwargs)
    else:
        raise ValueError(f"Unknown set type: {set_type}")
