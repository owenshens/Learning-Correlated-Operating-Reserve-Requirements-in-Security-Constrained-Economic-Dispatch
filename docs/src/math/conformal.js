/**
 * conformal.js — Conformal calibration utilities for robust optimization.
 *
 * Split conformal prediction provides distribution-free coverage guarantees.
 * Given gauge scores s_i = ||L^{-1} u_i|| for calibration residuals u_i,
 * the conformal radius rho is chosen so that a fraction >= tau of future
 * residuals will fall inside the ellipsoid { u : ||L^{-1} u|| <= rho }.
 *
 * Key formula:
 *   rho = Q_{ceil((n+1)*tau)/n}(s_1, ..., s_n)
 * i.e., the ceil((n+1)*tau)-th smallest score among n calibration scores.
 */

const EPSILON = 1e-10;

/**
 * Compute the conformal radius for a given target coverage level.
 *
 * Uses the split conformal prediction quantile:
 *   rho = s_{(k)}  where k = ceil((n+1) * tau)
 * and s_{(k)} is the k-th order statistic (1-indexed).
 *
 * If k > n, returns Infinity (cannot achieve that coverage with this sample).
 * If k < 1, returns the minimum score.
 *
 * @param {number[]} scores - array of gauge scores s_i = ||L^{-1} u_i||
 * @param {number} tau - target coverage probability in (0, 1), e.g. 0.9 for 90%
 * @returns {number} the conformal radius rho
 */
export function calibrateRadius(scores, tau) {
  const n = scores.length;
  if (n === 0) return Infinity;

  const k = Math.ceil((n + 1) * tau);

  if (k > n) {
    // Cannot achieve this coverage level; return infinity
    return Infinity;
  }
  if (k < 1) {
    // Edge case: very low tau
    return Math.min(...scores);
  }

  // Sort scores ascending and pick the k-th order statistic (1-indexed)
  const sorted = [...scores].sort((a, b) => a - b);
  return sorted[k - 1];
}

/**
 * Compute empirical coverage: fraction of scores that fall within the radius.
 *
 * coverage = |{i : s_i <= radius}| / n
 *
 * @param {number[]} scores - array of gauge scores
 * @param {number} radius - the threshold radius rho
 * @returns {number} coverage fraction in [0, 1]
 */
export function computeCoverage(scores, radius) {
  const n = scores.length;
  if (n === 0) return 1;

  let count = 0;
  for (let i = 0; i < n; i++) {
    if (scores[i] <= radius + EPSILON) {
      count++;
    }
  }
  return count / n;
}

/**
 * Compute a smoothed quantile using a sigmoid kernel.
 *
 * The hard empirical CDF F(r) = (1/n) sum I(s_i <= r) is not differentiable.
 * The smoothed CDF replaces the indicator with a sigmoid:
 *
 *   F_eps(r) = (1/n) * sum sigmoid((r - s_i) / epsilon)
 *
 * where sigmoid(x) = 1 / (1 + exp(-x)).
 *
 * We then find r such that F_eps(r) = tau via bisection.
 *
 * @param {number[]} scores - array of gauge scores
 * @param {number} tau - target coverage in (0, 1)
 * @param {number} [epsilon=0.1] - smoothing bandwidth (smaller = closer to hard quantile)
 * @param {number} [maxBisect=100] - maximum bisection iterations
 * @returns {number} the smoothed radius
 */
export function smoothQuantile(scores, tau, epsilon = 0.1, maxBisect = 100) {
  const n = scores.length;
  if (n === 0) return Infinity;

  // Find search bounds from the score range
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);

  // Extend bounds to ensure we can bracket the quantile
  const margin = 5 * epsilon + (maxScore - minScore) * 0.1;
  let lo = minScore - margin;
  let hi = maxScore + margin;

  /**
   * Smoothed CDF at point r.
   * @param {number} r
   * @returns {number}
   */
  function smoothCDF(r) {
    let sum = 0;
    for (let i = 0; i < n; i++) {
      const z = (r - scores[i]) / epsilon;
      // Numerically stable sigmoid
      if (z > 20) {
        sum += 1;
      } else if (z < -20) {
        sum += 0;
      } else {
        sum += 1 / (1 + Math.exp(-z));
      }
    }
    return sum / n;
  }

  // Check bracket validity
  if (smoothCDF(lo) >= tau) {
    return lo;
  }
  if (smoothCDF(hi) <= tau) {
    return hi;
  }

  // Bisection to find r such that smoothCDF(r) = tau
  for (let iter = 0; iter < maxBisect; iter++) {
    const mid = (lo + hi) / 2;
    const fMid = smoothCDF(mid);

    if (Math.abs(fMid - tau) < 1e-12) {
      return mid;
    }

    if (fMid < tau) {
      lo = mid;
    } else {
      hi = mid;
    }

    // Convergence check on interval width
    if (hi - lo < 1e-14) {
      return (lo + hi) / 2;
    }
  }

  return (lo + hi) / 2;
}

// === SELF TEST ===
// // Synthetic scores: 20 samples from ~ Uniform[0.5, 2.5]
// const scores = [0.6, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.35, 1.4, 1.5,
//                 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.15, 2.2, 2.3, 2.4];
//
// console.log('n =', scores.length);
//
// // Calibrate at 90% coverage
// const rho90 = calibrateRadius(scores, 0.9);
// console.log('rho (tau=0.9):', rho90);
// // k = ceil(21 * 0.9) = ceil(18.9) = 19, so rho = sorted[18] = 2.3
// console.log('Expected: 2.3');
//
// // Verify coverage
// const cov90 = computeCoverage(scores, rho90);
// console.log('Coverage at rho90:', cov90);
// // 19 out of 20 scores <= 2.3, so coverage = 0.95
// console.log('Expected: 0.95');
//
// // 50% coverage
// const rho50 = calibrateRadius(scores, 0.5);
// console.log('rho (tau=0.5):', rho50);
// // k = ceil(21 * 0.5) = ceil(10.5) = 11, so rho = sorted[10] = 1.6
// console.log('Expected: 1.6');
//
// const cov50 = computeCoverage(scores, rho50);
// console.log('Coverage at rho50:', cov50);
//
// // Smooth quantile
// const smooth90 = smoothQuantile(scores, 0.9, 0.05);
// console.log('Smooth rho (tau=0.9, eps=0.05):', smooth90);
// console.log('Should be close to 2.3');
//
// const smooth90_wide = smoothQuantile(scores, 0.9, 0.5);
// console.log('Smooth rho (tau=0.9, eps=0.5):', smooth90_wide);
// console.log('Should be smoother / slightly different');
//
// // Edge cases
// console.log('Empty scores:', calibrateRadius([], 0.9)); // Infinity
// console.log('tau=1.0 with n=20:', calibrateRadius(scores, 1.0)); // Infinity (k=21 > 20)
// console.log('Coverage at Infinity:', computeCoverage(scores, Infinity)); // 1.0
