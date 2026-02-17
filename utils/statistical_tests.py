"""
Statistical Testing Utilities
==============================

Provides statistical tests and effect size calculations for experiments:
- Hypothesis testing (t-tests, Mann-Whitney)
- Effect sizes (Cohen's d, eta-squared)
- Confidence intervals
- Multiple comparison corrections (Bonferroni, Holm)
"""

import numpy as np
from scipy import stats
from typing import Tuple, Optional, Dict, List


def paired_t_test(
    sample1: np.ndarray,
    sample2: np.ndarray,
    alpha: float = 0.05,
) -> Dict[str, float]:
    """
    Paired t-test for comparing two related samples.

    Args:
        sample1: First sample
        sample2: Second sample
        alpha: Significance level

    Returns:
        Dictionary with test results
    """
    t_stat, p_value = stats.ttest_rel(sample1, sample2)

    return {
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'significant': bool(p_value < alpha),
        'alpha': alpha,
        'n': len(sample1),
        'mean_diff': float(np.mean(sample1 - sample2)),
        'std_diff': float(np.std(sample1 - sample2, ddof=1)),
    }


def independent_t_test(
    sample1: np.ndarray,
    sample2: np.ndarray,
    alpha: float = 0.05,
    equal_var: bool = True,
) -> Dict[str, float]:
    """
    Independent t-test for comparing two unrelated samples.

    Args:
        sample1: First sample
        sample2: Second sample
        alpha: Significance level
        equal_var: Assume equal variances (True = Student's, False = Welch's)

    Returns:
        Dictionary with test results
    """
    t_stat, p_value = stats.ttest_ind(sample1, sample2, equal_var=equal_var)

    return {
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'significant': bool(p_value < alpha),
        'alpha': alpha,
        'n1': len(sample1),
        'n2': len(sample2),
        'mean1': float(np.mean(sample1)),
        'mean2': float(np.mean(sample2)),
        'std1': float(np.std(sample1, ddof=1)),
        'std2': float(np.std(sample2, ddof=1)),
    }


def mann_whitney_test(
    sample1: np.ndarray,
    sample2: np.ndarray,
    alpha: float = 0.05,
) -> Dict[str, float]:
    """
    Mann-Whitney U test (non-parametric alternative to t-test).

    Args:
        sample1: First sample
        sample2: Second sample
        alpha: Significance level

    Returns:
        Dictionary with test results
    """
    u_stat, p_value = stats.mannwhitneyu(sample1, sample2, alternative='two-sided')

    return {
        'u_statistic': float(u_stat),
        'p_value': float(p_value),
        'significant': bool(p_value < alpha),
        'alpha': alpha,
        'n1': len(sample1),
        'n2': len(sample2),
        'median1': float(np.median(sample1)),
        'median2': float(np.median(sample2)),
    }


def cohens_d(sample1: np.ndarray, sample2: np.ndarray, paired: bool = False) -> float:
    """
    Calculate Cohen's d effect size.

    Args:
        sample1: First sample
        sample2: Second sample
        paired: Whether samples are paired

    Returns:
        Cohen's d value
    """
    if paired:
        # Cohen's d for paired samples
        diff = sample1 - sample2
        return float(np.mean(diff) / np.std(diff, ddof=1))
    else:
        # Cohen's d for independent samples
        n1, n2 = len(sample1), len(sample2)
        s1, s2 = np.var(sample1, ddof=1), np.var(sample2, ddof=1)
        pooled_std = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
        return float((np.mean(sample1) - np.mean(sample2)) / pooled_std)


def confidence_interval(
    data: np.ndarray,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Calculate confidence interval for mean.

    Args:
        data: Sample data
        confidence: Confidence level (e.g., 0.95 for 95%)

    Returns:
        (lower_bound, upper_bound)
    """
    n = len(data)
    mean = np.mean(data)
    sem = stats.sem(data)  # Standard error of mean
    margin = sem * stats.t.ppf((1 + confidence) / 2, n - 1)

    return (float(mean - margin), float(mean + margin))


def bonferroni_correction(p_values: List[float], alpha: float = 0.05) -> Dict:
    """
    Bonferroni correction for multiple comparisons.

    Args:
        p_values: List of p-values
        alpha: Family-wise error rate

    Returns:
        Dictionary with corrected results
    """
    n_tests = len(p_values)
    alpha_corrected = alpha / n_tests
    significant = [p < alpha_corrected for p in p_values]

    return {
        'alpha_original': alpha,
        'alpha_corrected': alpha_corrected,
        'n_tests': n_tests,
        'p_values': p_values,
        'significant': significant,
        'n_significant': sum(significant),
    }


def holm_correction(p_values: List[float], alpha: float = 0.05) -> Dict:
    """
    Holm-Bonferroni correction (less conservative than Bonferroni).

    Args:
        p_values: List of p-values
        alpha: Family-wise error rate

    Returns:
        Dictionary with corrected results
    """
    n_tests = len(p_values)
    sorted_indices = np.argsort(p_values)
    sorted_p = [p_values[i] for i in sorted_indices]

    significant = [False] * n_tests
    for rank, (idx, p) in enumerate(zip(sorted_indices, sorted_p)):
        alpha_adjusted = alpha / (n_tests - rank)
        if p < alpha_adjusted:
            significant[idx] = True
        else:
            break  # Stop at first non-significant

    return {
        'alpha': alpha,
        'n_tests': n_tests,
        'p_values': p_values,
        'significant': significant,
        'n_significant': sum(significant),
    }


def bootstrap_confidence_interval(
    data: np.ndarray,
    statistic_func=np.mean,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Bootstrap confidence interval for any statistic.

    Args:
        data: Sample data
        statistic_func: Function to compute statistic (default: mean)
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level

    Returns:
        (lower_bound, upper_bound)
    """
    n = len(data)
    bootstrap_stats = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        sample = np.random.choice(data, size=n, replace=True)
        bootstrap_stats[i] = statistic_func(sample)

    alpha = (1 - confidence) / 2
    lower = np.percentile(bootstrap_stats, alpha * 100)
    upper = np.percentile(bootstrap_stats, (1 - alpha) * 100)

    return (float(lower), float(upper))


def convergence_rate_estimate(
    errors: np.ndarray,
    iterations: np.ndarray,
) -> Dict[str, float]:
    """
    Estimate convergence rate from error trajectory.

    Fits: log(error) ≈ a + b * log(iteration)
    Rate is -b (e.g., b=-0.5 means O(1/sqrt(K)) convergence)

    Args:
        errors: Error values at each iteration
        iterations: Iteration counts

    Returns:
        Dictionary with rate estimate and fit quality
    """
    # Filter out zero/negative errors
    mask = errors > 0
    log_errors = np.log(errors[mask])
    log_iters = np.log(iterations[mask])

    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_iters, log_errors)

    return {
        'rate_exponent': float(-slope),  # Convergence rate
        'intercept': float(intercept),
        'r_squared': float(r_value**2),
        'p_value': float(p_value),
        'std_err': float(std_err),
        'interpretation': interpret_convergence_rate(-slope),
    }


def interpret_convergence_rate(rate: float) -> str:
    """Interpret convergence rate exponent."""
    if abs(rate - 0.5) < 0.1:
        return "O(1/sqrt(K)) - sublinear (typical for non-smooth)"
    elif abs(rate - 1.0) < 0.1:
        return "O(1/K) - linear (typical for smooth convex)"
    elif abs(rate - 2.0) < 0.1:
        return "O(1/K^2) - quadratic (Newton-like)"
    elif rate > 1.5:
        return "superlinear convergence"
    elif rate < 0.3:
        return "very slow convergence"
    else:
        return f"O(1/K^{rate:.2f})"


def normality_test(data: np.ndarray, alpha: float = 0.05) -> Dict:
    """
    Test if data is normally distributed (Shapiro-Wilk test).

    Args:
        data: Sample data
        alpha: Significance level

    Returns:
        Dictionary with test results
    """
    stat, p_value = stats.shapiro(data)

    return {
        'statistic': float(stat),
        'p_value': float(p_value),
        'is_normal': bool(p_value > alpha),  # Fail to reject H0 => normal
        'alpha': alpha,
        'n': len(data),
    }


def levene_test(sample1: np.ndarray, sample2: np.ndarray, alpha: float = 0.05) -> Dict:
    """
    Test equality of variances (Levene's test).

    Args:
        sample1: First sample
        sample2: Second sample
        alpha: Significance level

    Returns:
        Dictionary with test results
    """
    stat, p_value = stats.levene(sample1, sample2)

    return {
        'statistic': float(stat),
        'p_value': float(p_value),
        'equal_variance': bool(p_value > alpha),  # Fail to reject H0 => equal variance
        'alpha': alpha,
    }


def summary_statistics(data: np.ndarray) -> Dict[str, float]:
    """
    Compute comprehensive summary statistics.

    Args:
        data: Sample data

    Returns:
        Dictionary with statistics
    """
    return {
        'n': len(data),
        'mean': float(np.mean(data)),
        'std': float(np.std(data, ddof=1)),
        'sem': float(stats.sem(data)),
        'median': float(np.median(data)),
        'min': float(np.min(data)),
        'max': float(np.max(data)),
        'q25': float(np.percentile(data, 25)),
        'q75': float(np.percentile(data, 75)),
        'iqr': float(np.percentile(data, 75) - np.percentile(data, 25)),
        'skewness': float(stats.skew(data)),
        'kurtosis': float(stats.kurtosis(data)),
    }
