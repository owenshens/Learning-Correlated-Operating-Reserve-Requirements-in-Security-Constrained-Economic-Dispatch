/**
 * ellipse.js — Pure 2D ellipse math for robust optimization visualization.
 *
 * Ellipsoidal uncertainty sets are parameterized by a lower-triangular
 * Cholesky factor L (2x2 for visualization). The set is:
 *    U = { u : ||L^{-1} u||_2 <= 1 }
 * which is the image of the unit ball under the linear map L.
 *
 * All 2x2 matrices are represented as [[a, b], [c, d]] (row-major nested arrays).
 */

const EPSILON = 1e-12;

/**
 * Multiply two 2x2 matrices.
 * @param {number[][]} A - 2x2 matrix [[a11,a12],[a21,a22]]
 * @param {number[][]} B - 2x2 matrix
 * @returns {number[][]} A * B
 */
export function matMul2x2(A, B) {
  return [
    [A[0][0] * B[0][0] + A[0][1] * B[1][0], A[0][0] * B[0][1] + A[0][1] * B[1][1]],
    [A[1][0] * B[0][0] + A[1][1] * B[1][0], A[1][0] * B[0][1] + A[1][1] * B[1][1]],
  ];
}

/**
 * Transpose a 2x2 matrix.
 * @param {number[][]} A - 2x2 matrix
 * @returns {number[][]} A^T
 */
export function transpose2x2(A) {
  return [
    [A[0][0], A[1][0]],
    [A[0][1], A[1][1]],
  ];
}

/**
 * Invert a 2x2 matrix. Returns null if the matrix is singular (|det| < EPSILON).
 * @param {number[][]} A - 2x2 matrix
 * @returns {number[][]|null} A^{-1}, or null if singular
 */
export function invert2x2(A) {
  const det = A[0][0] * A[1][1] - A[0][1] * A[1][0];
  if (Math.abs(det) < EPSILON) {
    return null;
  }
  const invDet = 1 / det;
  return [
    [A[1][1] * invDet, -A[0][1] * invDet],
    [-A[1][0] * invDet, A[0][0] * invDet],
  ];
}

/**
 * Compute boundary points of the ellipse { u : ||L^{-1} u|| <= 1 }.
 *
 * The boundary is the image of the unit circle under L:
 *   u(t) = L * [cos(t), sin(t)]^T   for t in [0, 2*pi)
 *
 * @param {number[][]} L_2x2 - 2x2 lower-triangular Cholesky factor
 * @param {number} [numPoints=64] - number of boundary points
 * @returns {{x: number, y: number}[]} array of boundary points
 */
export function choleskyToEllipsePoints(L_2x2, numPoints = 64) {
  const L = L_2x2;
  const points = [];
  for (let i = 0; i < numPoints; i++) {
    const t = (2 * Math.PI * i) / numPoints;
    const ct = Math.cos(t);
    const st = Math.sin(t);
    points.push({
      x: L[0][0] * ct + L[0][1] * st,
      y: L[1][0] * ct + L[1][1] * st,
    });
  }
  return points;
}

/**
 * Find the support point: the point on the ellipse boundary that maximises w^T u.
 *
 * For U = { u : ||L^{-1} u|| <= 1 }, the maximiser is:
 *   u* = L L^T w / ||L^T w||
 * and the support function value (maximum) is:
 *   sigma(w) = ||L^T w||
 *
 * @param {number[][]} L_2x2 - 2x2 lower-triangular Cholesky factor
 * @param {number[]} direction - direction vector [wx, wy]
 * @returns {{x: number, y: number, value: number}} support point and support value
 */
export function supportPoint(L_2x2, direction) {
  const L = L_2x2;
  const LT = transpose2x2(L);
  const w = direction;

  // L^T w
  const LTw = [
    LT[0][0] * w[0] + LT[0][1] * w[1],
    LT[1][0] * w[0] + LT[1][1] * w[1],
  ];

  const normLTw = Math.sqrt(LTw[0] * LTw[0] + LTw[1] * LTw[1]);

  if (normLTw < EPSILON) {
    // Degenerate: w is in the null space of L^T (shouldn't happen for valid L)
    return { x: 0, y: 0, value: 0 };
  }

  // L L^T w
  const LLTw = [
    L[0][0] * LTw[0] + L[0][1] * LTw[1],
    L[1][0] * LTw[0] + L[1][1] * LTw[1],
  ];

  // u* = L L^T w / ||L^T w||
  const x = LLTw[0] / normLTw;
  const y = LLTw[1] / normLTw;

  return { x, y, value: normLTw };
}

/**
 * Compute the scalar support function value: sigma_L(w) = ||L^T w||_2.
 *
 * @param {number[][]} L_2x2 - 2x2 lower-triangular Cholesky factor
 * @param {number[]} direction - direction vector [wx, wy]
 * @returns {number} the support function value
 */
export function supportFunction(L_2x2, direction) {
  const LT = transpose2x2(L_2x2);
  const w = direction;
  const LTw0 = LT[0][0] * w[0] + LT[0][1] * w[1];
  const LTw1 = LT[1][0] * w[0] + LT[1][1] * w[1];
  return Math.sqrt(LTw0 * LTw0 + LTw1 * LTw1);
}

/**
 * Linearly interpolate between two Cholesky factors.
 *
 * Computes (1-t)*L1 + t*L2, then projects to a valid lower-triangular matrix
 * with positive diagonal entries (clamped above EPSILON).
 *
 * @param {number[][]} L1 - start Cholesky factor (2x2)
 * @param {number[][]} L2 - end Cholesky factor (2x2)
 * @param {number} t - interpolation parameter in [0, 1]
 * @returns {number[][]} interpolated Cholesky factor
 */
export function interpolateL(L1, L2, t) {
  const M = [
    [(1 - t) * L1[0][0] + t * L2[0][0], (1 - t) * L1[0][1] + t * L2[0][1]],
    [(1 - t) * L1[1][0] + t * L2[1][0], (1 - t) * L1[1][1] + t * L2[1][1]],
  ];
  return projectToCholesky(M);
}

/**
 * Project a 2x2 matrix to a valid lower-triangular Cholesky factor.
 *
 * - Zeroes out the upper-triangular entry M[0][1].
 * - Clamps diagonal entries to be >= EPSILON.
 *
 * @param {number[][]} M - 2x2 matrix
 * @returns {number[][]} valid lower-triangular matrix with positive diagonal
 */
export function projectToCholesky(M) {
  return [
    [Math.max(M[0][0], EPSILON), 0],
    [M[1][0], Math.max(M[1][1], EPSILON)],
  ];
}

/**
 * Normalize L so that tr(L L^T) = targetTrace.
 *
 * tr(L L^T) = sum of squares of all entries of L.
 * We scale L by sqrt(targetTrace / currentTrace).
 *
 * @param {number[][]} L - 2x2 lower-triangular Cholesky factor
 * @param {number} targetTrace - desired trace of L L^T
 * @returns {number[][]} rescaled L
 */
export function traceNormalize(L, targetTrace) {
  // tr(L L^T) = L[0][0]^2 + L[0][1]^2 + L[1][0]^2 + L[1][1]^2
  // For lower-triangular L, L[0][1] = 0, so:
  // tr = L[0][0]^2 + L[1][0]^2 + L[1][1]^2
  const currentTrace =
    L[0][0] * L[0][0] + L[0][1] * L[0][1] + L[1][0] * L[1][0] + L[1][1] * L[1][1];

  if (currentTrace < EPSILON) {
    // Degenerate L; return identity scaled to target
    const s = Math.sqrt(targetTrace / 2);
    return [
      [s, 0],
      [0, s],
    ];
  }

  const scale = Math.sqrt(targetTrace / currentTrace);
  return [
    [L[0][0] * scale, L[0][1] * scale],
    [L[1][0] * scale, L[1][1] * scale],
  ];
}

// === SELF TEST ===
// const L = [[2, 0], [1, 1.5]];
// console.log('Ellipse points (8):', choleskyToEllipsePoints(L, 8));
// console.log('Support at [1,0]:', supportPoint(L, [1, 0]));
// console.log('Support at [0,1]:', supportPoint(L, [0, 1]));
// console.log('Support function [1,0]:', supportFunction(L, [1, 0]));
// console.log('Support function [0,1]:', supportFunction(L, [0, 1]));
//
// // Verify support point lies on ellipse: ||L^{-1} u*|| should equal 1
// const Linv = invert2x2(L);
// const sp = supportPoint(L, [1, 0]);
// const mapped = [Linv[0][0]*sp.x + Linv[0][1]*sp.y, Linv[1][0]*sp.x + Linv[1][1]*sp.y];
// console.log('||L^{-1} u*|| (should be 1):', Math.sqrt(mapped[0]**2 + mapped[1]**2));
//
// // Interpolation
// const L2 = [[3, 0], [-0.5, 2]];
// console.log('Interp t=0:', interpolateL(L, L2, 0));
// console.log('Interp t=1:', interpolateL(L, L2, 1));
// console.log('Interp t=0.5:', interpolateL(L, L2, 0.5));
//
// // Matrix ops
// console.log('L * L^T:', matMul2x2(L, transpose2x2(L)));
// console.log('L * L^{-1} (should be I):', matMul2x2(L, invert2x2(L)));
//
// // Trace normalize
// const Ln = traceNormalize(L, 10);
// const trLLT = Ln[0][0]**2 + Ln[1][0]**2 + Ln[1][1]**2;
// console.log('tr(L_n L_n^T) (should be 10):', trLLT);
