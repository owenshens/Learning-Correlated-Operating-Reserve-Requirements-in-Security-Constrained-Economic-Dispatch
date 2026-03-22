/**
 * support.js — Higher-level support function operations for the visualization.
 *
 * Bridges the low-level 2D ellipse math (ellipse.js) with the power systems
 * context: zonal reserves, exposure directions, and shape gradients.
 *
 * Key relationship:
 *   Reserve for zone z = rho * ||L^T * A[z,:]||_2
 * where A is the zone-allocation matrix and L is the Cholesky factor.
 */

const EPSILON = 1e-12;

/**
 * Compute reserve requirements for all zones.
 *
 * For each zone z:
 *   R_z = rho * ||L^T * A[z, :]||_2
 *
 * @param {number[][]} L_full - d x d Cholesky factor (nested array, lower-triangular)
 * @param {number[][]} A - (numZones x d) allocation matrix
 * @param {number} rho - conformal radius (scalar)
 * @returns {number[]} reserve requirement per zone
 */
export function computeReserves(L_full, A, rho) {
  const numZones = A.length;
  const d = L_full.length;
  const reserves = new Array(numZones);

  // L^T is d x d
  // For each zone z, compute L^T * A[z,:] then take its 2-norm.
  for (let z = 0; z < numZones; z++) {
    const w = A[z]; // length d
    let normSq = 0;

    // Compute L^T * w component by component:
    // (L^T * w)[i] = sum_j L[j][i] * w[j]  (column i of L dotted with w)
    for (let i = 0; i < d; i++) {
      let val = 0;
      for (let j = 0; j < d; j++) {
        val += L_full[j][i] * w[j];
      }
      normSq += val * val;
    }

    reserves[z] = rho * Math.sqrt(normSq);
  }

  return reserves;
}

/**
 * Extract the exposure direction for a specific zone from the allocation matrix.
 *
 * Returns A[zoneIndex, :] normalized to unit length. If the row is zero,
 * returns the zero vector.
 *
 * @param {number[][]} A - (numZones x d) allocation matrix
 * @param {number} zoneIndex - which zone's exposure direction to extract
 * @returns {number[]} unit-length exposure vector (length d)
 */
export function computeExposureVector(A, zoneIndex) {
  const row = A[zoneIndex];
  let normSq = 0;
  for (let i = 0; i < row.length; i++) {
    normSq += row[i] * row[i];
  }
  const norm = Math.sqrt(normSq);
  if (norm < EPSILON) {
    return new Array(row.length).fill(0);
  }
  return row.map((v) => v / norm);
}

/**
 * Compute the shape gradient contribution from one zone's reserve constraint.
 *
 * The gradient of the reserve cost w.r.t. L (for a single zone z with dual mu_z) is:
 *   g_z = mu_z * rho * L * w * w^T / ||L^T w||_2
 *
 * where w = A[z, :] is the exposure direction.
 *
 * For visualization purposes, this returns the 2x2 gradient matrix (assuming
 * we are working in the projected 2D space).
 *
 * @param {number[][]} L_2x2 - 2x2 lower-triangular Cholesky factor
 * @param {number[]} direction - 2D exposure direction [w1, w2]
 * @param {number} mu - dual multiplier for this zone's reserve constraint
 * @param {number} [rho=1] - conformal radius
 * @returns {number[][]} 2x2 gradient matrix
 */
export function computeGradient(L_2x2, direction, mu, rho = 1) {
  const L = L_2x2;
  const w = direction;

  // Compute L^T w
  const LTw = [
    L[0][0] * w[0] + L[1][0] * w[1], // L^T row 0
    L[0][1] * w[0] + L[1][1] * w[1], // L^T row 1
  ];

  const normLTw = Math.sqrt(LTw[0] * LTw[0] + LTw[1] * LTw[1]);

  if (normLTw < EPSILON) {
    return [
      [0, 0],
      [0, 0],
    ];
  }

  // Compute L * w (matrix-vector product)
  const Lw = [L[0][0] * w[0] + L[0][1] * w[1], L[1][0] * w[0] + L[1][1] * w[1]];

  // Gradient = mu * rho * (L w) * w^T / ||L^T w||
  // This is a rank-1 outer product scaled by mu * rho / ||L^T w||
  const scale = (mu * rho) / normLTw;

  return [
    [scale * Lw[0] * w[0], scale * Lw[0] * w[1]],
    [scale * Lw[1] * w[0], scale * Lw[1] * w[1]],
  ];
}

/**
 * Project a full d x d Cholesky factor down to 2D by extracting a 2x2 submatrix.
 *
 * Given dimension indices [i, j], extracts the 2x2 block:
 *   [[L[i][i], L[i][j]],
 *    [L[j][i], L[j][j]]]
 *
 * Note: for a lower-triangular L with i < j, L[i][j] = 0, so the result
 * is lower-triangular when i < j.
 *
 * @param {number[][]} L_full - d x d Cholesky factor (nested array)
 * @param {number[]} dims - [i, j] indices of the two dimensions to project onto
 * @returns {number[][]} 2x2 submatrix
 */
export function projectTo2D(L_full, dims) {
  const [i, j] = dims;
  return [
    [L_full[i][i], L_full[i][j]],
    [L_full[j][i], L_full[j][j]],
  ];
}

// === SELF TEST ===
// // Simple 3x3 lower-triangular L
// const L3 = [
//   [2, 0, 0],
//   [1, 1.5, 0],
//   [0.5, -0.3, 1],
// ];
//
// // Allocation matrix: 2 zones, 3 dimensions
// const A = [
//   [1, 0, 0],    // zone 0: exposed only to dimension 0
//   [0, 0.6, 0.8], // zone 1: exposed to dims 1 and 2
// ];
//
// const rho = 1.5;
// const reserves = computeReserves(L3, A, rho);
// console.log('Reserves:', reserves);
// // Zone 0: rho * ||L^T * [1,0,0]|| = rho * ||[L[0][0], L[1][0], L[2][0]]||
// //       = 1.5 * ||(2, 1, 0.5)|| = 1.5 * sqrt(4+1+0.25) = 1.5 * sqrt(5.25)
// console.log('Expected zone 0:', 1.5 * Math.sqrt(5.25));
//
// const expVec = computeExposureVector(A, 1);
// console.log('Exposure vector zone 1:', expVec);
// // [0, 0.6, 0.8] normalized: norm=1, so [0, 0.6, 0.8]
//
// // 2D gradient test
// const L2 = [[2, 0], [1, 1.5]];
// const grad = computeGradient(L2, [1, 0], 0.5, 1.0);
// console.log('Gradient:', grad);
//
// // Project 3x3 to 2D (dims 0,1)
// const L2proj = projectTo2D(L3, [0, 1]);
// console.log('Projected L (dims 0,1):', L2proj);
// // Should be [[2, 0], [1, 1.5]]
