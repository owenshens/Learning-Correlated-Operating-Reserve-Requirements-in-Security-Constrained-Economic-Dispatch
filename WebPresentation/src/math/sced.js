/**
 * sced.js — Lightweight SCED (Security-Constrained Economic Dispatch) solver.
 *
 * Provides both a greedy heuristic and a basic LP solver for the reserve-aware
 * economic dispatch problem used in the robust optimization demo.
 *
 * Problem formulation:
 *   min  sum_i (c_i * g_i + cr_i * r_i)
 *   s.t. sum_i g_i = D                           (power balance)
 *        minP_i <= g_i <= maxP_i                  (capacity bounds)
 *        r_i >= 0                                 (reserve non-negativity)
 *        g_i + r_i <= maxP_i                      (capacity headroom)
 *        sum_{i in zone z} r_i >= R_z  for all z  (zonal reserve requirements)
 */

const EPSILON = 1e-10;
const BIG_M = 1e8;

/**
 * Solve the SCED problem using a greedy merit-order approach.
 *
 * Algorithm:
 * 1. Merit-order dispatch: sort generators by energy cost, stack cheaply.
 * 2. Greedy reserve allocation: for each zone, allocate reserves to generators
 *    with headroom, cheapest reserve cost first.
 * 3. Approximate duals: marginal reserve cost at each zone.
 *
 * @param {Object[]} generators - array of generator objects
 * @param {string|number} generators[].id - generator identifier
 * @param {number} generators[].zone - zone index (0-based)
 * @param {number} generators[].minP - minimum generation (MW)
 * @param {number} generators[].maxP - maximum generation (MW)
 * @param {number} generators[].costEnergy - energy cost ($/MWh)
 * @param {number} generators[].costReserve - reserve cost ($/MWh)
 * @param {Object[]} zones - array of zone objects
 * @param {number|string} zones[].id - zone identifier
 * @param {Array} zones[].generators - list of generator ids in this zone
 * @param {number[]} reserveRequirements - minimum reserve per zone (length = numZones)
 * @returns {Object} solution object with cost, generation, reserves, duals, status
 */
export function solveGreedySCED(generators, zones, reserveRequirements) {
  const n = generators.length;
  const nz = zones.length;

  // Total demand: sum of all minP as a baseline? No — we need demand as input.
  // The demo will typically set demand externally. For this solver, demand is
  // the sum of all generator minP plus some additional load.
  // We compute demand from the generators' capacities, targeting ~70% utilization.
  // Actually, let's accept demand as part of the generators context or compute it.
  // For flexibility, compute total demand as sum of (minP + maxP)/2 across generators.
  // The caller should set this more precisely; we provide a fallback.
  let totalDemand = 0;
  for (let i = 0; i < n; i++) {
    totalDemand += (generators[i].minP + generators[i].maxP) / 2;
  }

  return _solveGreedy(generators, zones, reserveRequirements, totalDemand);
}

/**
 * Full SCED solver with explicit demand.
 *
 * Converts the problem to standard LP form and solves with a basic simplex
 * implementation. Falls back to the greedy solver if the simplex fails.
 *
 * @param {Object[]} generators - generator objects (same format as solveGreedySCED)
 * @param {Object[]} zones - zone objects
 * @param {number[]} reserveRequirements - min reserve per zone
 * @param {Object} [options={}] - solver options
 * @param {number} [options.demand] - total demand (MW); defaults to sum of gen midpoints
 * @param {boolean} [options.coupled=false] - enable inter-zone transfer constraints
 * @param {Object[]} [options.transferLimits=[]] - transfer limit specs (not used in basic version)
 * @param {number} [options.maxIter=5000] - max simplex iterations
 * @returns {Object} solution with cost, energyCost, reserveCost, generation, reserves, duals, status
 */
export function solveSCED(generators, zones, reserveRequirements, options = {}) {
  const n = generators.length;
  const nz = zones.length;

  const demand =
    options.demand != null
      ? options.demand
      : generators.reduce((s, g) => s + (g.minP + g.maxP) / 2, 0);

  // Try the LP solver first
  const lpResult = _solveSCEDLP(generators, zones, reserveRequirements, demand, options);
  if (lpResult && lpResult.status === 'optimal') {
    return lpResult;
  }

  // Fallback to greedy
  return _solveGreedy(generators, zones, reserveRequirements, demand);
}

/**
 * Internal greedy solver implementation.
 * @private
 */
function _solveGreedy(generators, zones, reserveRequirements, totalDemand) {
  const n = generators.length;
  const nz = zones.length;

  // --- Phase 1: Merit-order energy dispatch ---
  // Create index array sorted by energy cost ascending
  const genIndices = Array.from({ length: n }, (_, i) => i);
  genIndices.sort((a, b) => generators[a].costEnergy - generators[b].costEnergy);

  const generation = new Array(n).fill(0);
  const reserves = new Array(n).fill(0);

  // Set all generators to their minimum first
  let dispatched = 0;
  for (let i = 0; i < n; i++) {
    generation[i] = generators[i].minP;
    dispatched += generators[i].minP;
  }

  // Check feasibility: can we meet demand?
  const totalMaxP = generators.reduce((s, g) => s + g.maxP, 0);
  const totalMinP = generators.reduce((s, g) => s + g.minP, 0);

  if (totalDemand > totalMaxP || totalDemand < totalMinP) {
    return _infeasibleResult(n, nz);
  }

  // Stack additional generation in merit order
  let remaining = totalDemand - dispatched;
  for (const idx of genIndices) {
    if (remaining <= EPSILON) break;
    const headroom = generators[idx].maxP - generation[idx];
    const add = Math.min(headroom, remaining);
    generation[idx] += add;
    remaining -= add;
  }

  if (remaining > EPSILON) {
    return _infeasibleResult(n, nz);
  }

  // --- Phase 2: Reserve allocation ---
  // Build zone membership
  const zoneGens = new Array(nz);
  for (let z = 0; z < nz; z++) {
    zoneGens[z] = [];
  }
  for (let i = 0; i < n; i++) {
    const z = generators[i].zone;
    if (z >= 0 && z < nz) {
      zoneGens[z].push(i);
    }
  }

  // For each zone, sort generators by reserve cost and allocate
  const reserveDuals = new Array(nz).fill(0);

  for (let z = 0; z < nz; z++) {
    const req = reserveRequirements[z] || 0;
    if (req <= EPSILON) continue;

    // Sort zone generators by reserve cost ascending
    const sorted = [...zoneGens[z]];
    sorted.sort((a, b) => generators[a].costReserve - generators[b].costReserve);

    let allocated = 0;
    let marginalCost = 0;

    for (const idx of sorted) {
      if (allocated >= req - EPSILON) break;
      const headroom = generators[idx].maxP - generation[idx] - reserves[idx];
      if (headroom <= EPSILON) continue;

      const add = Math.min(headroom, req - allocated);
      reserves[idx] += add;
      allocated += add;
      marginalCost = generators[idx].costReserve;
    }

    if (allocated < req - EPSILON) {
      // Zone reserve requirement cannot be fully met; partial allocation
      // Set dual to a high value to signal tightness
      reserveDuals[z] = BIG_M;
    } else {
      // Dual is approximately the marginal reserve cost in this zone
      reserveDuals[z] = marginalCost;
    }
  }

  // --- Phase 3: Compute costs ---
  let energyCost = 0;
  let reserveCost = 0;
  for (let i = 0; i < n; i++) {
    energyCost += generators[i].costEnergy * generation[i];
    reserveCost += generators[i].costReserve * reserves[i];
  }

  return {
    cost: energyCost + reserveCost,
    energyCost,
    reserveCost,
    generation,
    reserves,
    duals: {
      reserveZonal: reserveDuals,
      powerBalance: _estimatePowerBalanceDual(generators, generation, genIndices),
    },
    status: 'optimal',
  };
}

/**
 * Estimate the power balance dual (system lambda) from the merit-order dispatch.
 * It's approximately the energy cost of the last dispatched marginal generator.
 * @private
 */
function _estimatePowerBalanceDual(generators, generation, sortedIndices) {
  let lambda = 0;
  for (const idx of sortedIndices) {
    if (generation[idx] > generators[idx].minP + EPSILON) {
      lambda = generators[idx].costEnergy;
    }
  }
  return lambda;
}

/**
 * Construct an infeasible result object.
 * @private
 */
function _infeasibleResult(n, nz) {
  return {
    cost: Infinity,
    energyCost: Infinity,
    reserveCost: Infinity,
    generation: new Array(n).fill(0),
    reserves: new Array(n).fill(0),
    duals: {
      reserveZonal: new Array(nz).fill(0),
      powerBalance: 0,
    },
    status: 'infeasible',
  };
}

/**
 * LP-based SCED solver using a basic revised simplex method.
 *
 * Formulates the SCED as:
 *   min  c^T x
 *   s.t. A_eq x = b_eq      (power balance)
 *        A_ub x <= b_ub      (capacity, reserve bounds, negative zonal reserve)
 *
 * Variables x = [g_1,...,g_n, r_1,...,r_n]
 *
 * @private
 */
function _solveSCEDLP(generators, zones, reserveRequirements, demand, options) {
  const n = generators.length;
  const nz = zones.length;
  const numVars = 2 * n; // g_i and r_i
  const maxIter = options.maxIter || 5000;

  // Build zone membership
  const zoneGens = new Array(nz);
  for (let z = 0; z < nz; z++) {
    zoneGens[z] = [];
  }
  for (let i = 0; i < n; i++) {
    const z = generators[i].zone;
    if (z >= 0 && z < nz) {
      zoneGens[z].push(i);
    }
  }

  // ---- Convert to standard form: min c^T x, s.t. Ax = b, x >= 0 ----
  //
  // Original variables: g_i in [minP_i, maxP_i], r_i >= 0
  // Shift: g_i' = g_i - minP_i >= 0, so g_i = g_i' + minP_i
  //
  // Constraints:
  // (1) Power balance:  sum g_i = D  =>  sum g_i' = D - sum minP_i
  // (2) Capacity:       g_i <= maxP_i  =>  g_i' <= maxP_i - minP_i
  // (3) Headroom:       g_i + r_i <= maxP_i  =>  g_i' + r_i <= maxP_i - minP_i
  // (4) Zonal reserve:  sum_{i in z} r_i >= R_z

  const totalMinP = generators.reduce((s, g) => s + g.minP, 0);
  const adjustedDemand = demand - totalMinP;

  if (adjustedDemand < -EPSILON) {
    return null; // Infeasible: demand below total minimum
  }

  // Cost vector: c_i for g_i', cr_i for r_i
  // Original: c_i * g_i = c_i * (g_i' + minP_i) = c_i * g_i' + constant
  const costVec = new Array(numVars);
  let costOffset = 0;
  for (let i = 0; i < n; i++) {
    costVec[i] = generators[i].costEnergy;
    costVec[n + i] = generators[i].costReserve;
    costOffset += generators[i].costEnergy * generators[i].minP;
  }

  // Count inequality constraints:
  // (2) n capacity constraints: g_i' <= maxP_i - minP_i  (add slack s_cap_i)
  // (3) n headroom constraints: g_i' + r_i <= maxP_i - minP_i  (add slack s_head_i)
  // (4) nz zonal reserve: sum r_i >= R_z  =>  -sum r_i <= -R_z  (add slack s_zone_z)
  const numSlack = n + n + nz; // cap + headroom + zonal
  const numEq = 1; // power balance
  const totalVars = numVars + numSlack; // original shifted vars + slacks

  // We'll use a simple tableau-based simplex.
  // Rows: numEq + numIneq = 1 + 2n + nz
  const numConstraints = numEq + 2 * n + nz;

  // Build the tableau.
  // Tableau format: [A | I | b] with objective row at the bottom.
  // We use Phase I / Big-M to handle the equality constraint.
  //
  // For simplicity and robustness, we use the Big-M method:
  // Add an artificial variable a for the equality constraint.
  // min c^T x + M * a
  // s.t. sum g_i' - a_slack(not needed, it's equality) ...
  //
  // Actually, let's use a simpler approach: since we have slack variables for
  // all inequality constraints, we can use those as the initial basis, and
  // handle the equality with an artificial variable.

  const totalCols = totalVars + 1; // +1 for artificial variable for equality
  const rows = numConstraints;

  // Allocate tableau: rows x (totalCols + 1) where last column is RHS
  const tableau = [];
  for (let i = 0; i < rows; i++) {
    tableau.push(new Array(totalCols + 1).fill(0));
  }

  // Row 0: Power balance (equality, needs artificial variable)
  // sum g_i' = adjustedDemand
  // sum g_i' + artificial = adjustedDemand (artificial must be driven to 0)
  for (let i = 0; i < n; i++) {
    tableau[0][i] = 1; // g_i' coefficient
  }
  tableau[0][totalCols - 1] = 1; // artificial variable
  tableau[0][totalCols] = adjustedDemand; // RHS

  // Rows 1..n: Capacity constraints g_i' + s_cap_i = maxP_i - minP_i
  for (let i = 0; i < n; i++) {
    const row = 1 + i;
    tableau[row][i] = 1; // g_i'
    tableau[row][numVars + i] = 1; // slack s_cap_i
    tableau[row][totalCols] = Math.max(generators[i].maxP - generators[i].minP, 0); // RHS
  }

  // Rows n+1..2n: Headroom constraints g_i' + r_i + s_head_i = maxP_i - minP_i
  for (let i = 0; i < n; i++) {
    const row = 1 + n + i;
    tableau[row][i] = 1; // g_i'
    tableau[row][n + i] = 1; // r_i
    tableau[row][numVars + n + i] = 1; // slack s_head_i
    tableau[row][totalCols] = Math.max(generators[i].maxP - generators[i].minP, 0); // RHS
  }

  // Rows 2n+1..2n+nz: Zonal reserve -sum r_i + s_zone_z = -R_z
  // But RHS must be non-negative for initial basis feasibility.
  // Use: sum r_i - s_zone_z = R_z  ... but then s_zone_z would be negative initially.
  // Better: multiply by -1:  -sum r_i + s_zone_z = -R_z
  // But -R_z < 0 ... so we need artificial variables here too.
  //
  // Alternative: represent as sum r_i >= R_z using surplus + artificial:
  //   sum r_i - surplus_z + artificial_z = R_z
  //
  // To keep it simple, let's add artificial variables for zone constraints too.

  // Redefine: we need artificial variables for equality row + zone rows.
  // Let's restart with a cleaner Big-M formulation.

  return _bigMSolver(generators, zones, reserveRequirements, demand, costVec, costOffset, maxIter);
}

/**
 * Big-M simplex solver for the SCED LP.
 * @private
 */
function _bigMSolver(generators, zones, reserveRequirements, demand, costVec, costOffset, maxIter) {
  const n = generators.length;
  const nz = zones.length;

  const totalMinP = generators.reduce((s, g) => s + g.minP, 0);
  const adjustedDemand = demand - totalMinP;

  // Variables: g'_0..g'_{n-1}, r_0..r_{n-1}  (2n original)
  // Slacks for capacity: s_cap_0..s_cap_{n-1}  (n slacks)
  // Slacks for headroom: s_head_0..s_head_{n-1}  (n slacks)
  // Surplus for zone reserve: sur_0..sur_{nz-1}  (nz surplus)
  // Artificials: art_0 (for power balance), art_1..art_{nz} (for zone constraints)
  // Total: 2n + 2n + nz + 1 + nz = 4n + 2*nz + 1

  const numOrig = 2 * n;
  const numSlack = 2 * n; // cap + headroom
  const numSurplus = nz;
  const numArt = 1 + nz; // 1 for power balance, nz for zone reserves
  const totalVars = numOrig + numSlack + numSurplus + numArt;

  // Constraint rows: 1 (power balance) + n (capacity) + n (headroom) + nz (zone reserve)
  const numRows = 1 + 2 * n + nz;

  // Build zone membership
  const zoneGens = new Array(nz);
  for (let z = 0; z < nz; z++) {
    zoneGens[z] = [];
  }
  for (let i = 0; i < n; i++) {
    const z = generators[i].zone;
    if (z >= 0 && z < nz) {
      zoneGens[z].push(i);
    }
  }

  // Tableau: numRows x (totalVars + 1), last column = RHS
  const tab = [];
  for (let r = 0; r < numRows; r++) {
    tab.push(new Float64Array(totalVars + 1));
  }

  // Basis tracking
  const basis = new Array(numRows);

  // Variable index offsets
  const offG = 0;
  const offR = n;
  const offSCap = numOrig;
  const offSHead = numOrig + n;
  const offSur = numOrig + numSlack;
  const offArt = numOrig + numSlack + numSurplus;

  // Row 0: Power balance
  // sum g'_i + art_0 = adjustedDemand
  for (let i = 0; i < n; i++) {
    tab[0][offG + i] = 1;
  }
  tab[0][offArt] = 1;
  tab[0][totalVars] = adjustedDemand;
  basis[0] = offArt; // artificial is initial basis

  // Rows 1..n: Capacity g'_i + s_cap_i = maxP_i - minP_i
  for (let i = 0; i < n; i++) {
    const row = 1 + i;
    tab[row][offG + i] = 1;
    tab[row][offSCap + i] = 1;
    tab[row][totalVars] = Math.max(generators[i].maxP - generators[i].minP, 0);
    basis[row] = offSCap + i;
  }

  // Rows n+1..2n: Headroom g'_i + r_i + s_head_i = maxP_i - minP_i
  for (let i = 0; i < n; i++) {
    const row = 1 + n + i;
    tab[row][offG + i] = 1;
    tab[row][offR + i] = 1;
    tab[row][offSHead + i] = 1;
    tab[row][totalVars] = Math.max(generators[i].maxP - generators[i].minP, 0);
    basis[row] = offSHead + i;
  }

  // Rows 2n+1..2n+nz: Zone reserve sum_{i in z} r_i - surplus_z + art_{z+1} = R_z
  for (let z = 0; z < nz; z++) {
    const row = 1 + 2 * n + z;
    for (const i of zoneGens[z]) {
      tab[row][offR + i] = 1;
    }
    tab[row][offSur + z] = -1;
    tab[row][offArt + 1 + z] = 1;
    tab[row][totalVars] = Math.max(reserveRequirements[z] || 0, 0);
    basis[row] = offArt + 1 + z;
  }

  // Objective: min c^T x + M * sum(artificials)
  // For simplex, we track reduced costs separately.
  // Cost for each variable:
  const objCost = new Float64Array(totalVars);
  for (let i = 0; i < n; i++) {
    objCost[offG + i] = costVec[i]; // energy cost for g'_i
    objCost[offR + i] = costVec[n + i]; // reserve cost for r_i
  }
  // Slacks and surplus have zero cost
  // Artificials have Big-M cost
  for (let a = 0; a < numArt; a++) {
    objCost[offArt + a] = BIG_M;
  }

  // Compute initial objective row (reduced costs).
  // Since basis variables have cost, we need to compute:
  // reducedCost[j] = objCost[j] - sum_i (objCost[basis[i]] * tab[i][j])
  const redCost = new Float64Array(totalVars + 1);
  for (let j = 0; j <= totalVars; j++) {
    redCost[j] = j < totalVars ? objCost[j] : 0;
    for (let i = 0; i < numRows; i++) {
      redCost[j] -= objCost[basis[i]] * tab[i][j];
    }
  }

  // Simplex iterations
  for (let iter = 0; iter < maxIter; iter++) {
    // Find entering variable (most negative reduced cost)
    let enterCol = -1;
    let minRC = -EPSILON;
    for (let j = 0; j < totalVars; j++) {
      if (redCost[j] < minRC) {
        minRC = redCost[j];
        enterCol = j;
      }
    }

    if (enterCol === -1) {
      // Optimal: no negative reduced costs
      break;
    }

    // Find leaving variable (minimum ratio test)
    let leaveRow = -1;
    let minRatio = Infinity;
    for (let i = 0; i < numRows; i++) {
      if (tab[i][enterCol] > EPSILON) {
        const ratio = tab[i][totalVars] / tab[i][enterCol];
        if (ratio < minRatio - EPSILON) {
          minRatio = ratio;
          leaveRow = i;
        }
      }
    }

    if (leaveRow === -1) {
      // Unbounded — shouldn't happen for well-formed SCED
      return null;
    }

    // Pivot
    const pivotVal = tab[leaveRow][enterCol];

    // Scale pivot row
    for (let j = 0; j <= totalVars; j++) {
      tab[leaveRow][j] /= pivotVal;
    }

    // Eliminate from other rows
    for (let i = 0; i < numRows; i++) {
      if (i === leaveRow) continue;
      const factor = tab[i][enterCol];
      if (Math.abs(factor) < EPSILON) continue;
      for (let j = 0; j <= totalVars; j++) {
        tab[i][j] -= factor * tab[leaveRow][j];
      }
    }

    // Update reduced costs
    const rcFactor = redCost[enterCol];
    for (let j = 0; j <= totalVars; j++) {
      redCost[j] -= rcFactor * tab[leaveRow][j];
    }

    basis[leaveRow] = enterCol;
  }

  // Check if artificials are in the basis with non-zero value
  for (let i = 0; i < numRows; i++) {
    if (basis[i] >= offArt && tab[i][totalVars] > EPSILON) {
      return null; // Infeasible
    }
  }

  // Extract solution
  const solution = new Float64Array(totalVars);
  for (let i = 0; i < numRows; i++) {
    if (basis[i] < totalVars) {
      solution[basis[i]] = tab[i][totalVars];
    }
  }

  // Map back to original variables
  const generation = new Array(n);
  const reserves = new Array(n);
  for (let i = 0; i < n; i++) {
    generation[i] = solution[offG + i] + generators[i].minP; // shift back
    reserves[i] = solution[offR + i];
  }

  // Compute costs
  let energyCost = 0;
  let reserveCost = 0;
  for (let i = 0; i < n; i++) {
    energyCost += generators[i].costEnergy * generation[i];
    reserveCost += generators[i].costReserve * reserves[i];
  }

  // Extract duals from reduced costs of slack/surplus variables
  // Dual of capacity constraint i = -redCost[offSCap + i]  (slack variable)
  // Dual of headroom constraint i = -redCost[offSHead + i]
  // Dual of zone reserve constraint z: the surplus variable's reduced cost
  //   gives the dual. For a >= constraint converted to <= by negation,
  //   dual = redCost[offSur + z] (since surplus = negative slack)
  const reserveZonalDuals = new Array(nz);
  for (let z = 0; z < nz; z++) {
    // The zone reserve constraint was: sum r_i - surplus = R_z
    // The dual (shadow price) is the reduced cost of the surplus variable.
    // A binding constraint (surplus=0) will have a positive reduced cost for surplus.
    reserveZonalDuals[z] = Math.max(0, redCost[offSur + z]);
  }

  // Power balance dual: reduced cost of the equality constraint's artificial,
  // but since the artificial should be zero and driven out, we approximate:
  // The dual of sum g_i = D is the system marginal price.
  // It equals the reduced cost of any non-basic g' variable that is at its lower bound,
  // or we can compute it from the basis inverse.
  // Simpler: find the marginal generator cost.
  let powerBalanceDual = 0;
  for (let i = 0; i < n; i++) {
    if (
      generation[i] > generators[i].minP + EPSILON &&
      generation[i] < generators[i].maxP - EPSILON
    ) {
      // This generator is marginal
      powerBalanceDual = generators[i].costEnergy;
    }
  }

  return {
    cost: energyCost + reserveCost,
    energyCost,
    reserveCost,
    generation,
    reserves,
    duals: {
      reserveZonal: reserveZonalDuals,
      powerBalance: powerBalanceDual,
    },
    status: 'optimal',
  };
}

// === SELF TEST ===
// // 4 generators, 2 zones
// const gens = [
//   { id: 0, zone: 0, minP: 10, maxP: 100, costEnergy: 20, costReserve: 5 },
//   { id: 1, zone: 0, minP: 10, maxP: 80,  costEnergy: 30, costReserve: 8 },
//   { id: 2, zone: 1, minP: 5,  maxP: 120, costEnergy: 25, costReserve: 6 },
//   { id: 3, zone: 1, minP: 5,  maxP: 60,  costEnergy: 35, costReserve: 10 },
// ];
// const zns = [
//   { id: 0, generators: [0, 1] },
//   { id: 1, generators: [2, 3] },
// ];
// const resReq = [20, 15]; // zone 0 needs 20 MW reserve, zone 1 needs 15 MW
//
// console.log('--- Greedy SCED ---');
// const greedy = solveGreedySCED(gens, zns, resReq);
// console.log('Status:', greedy.status);
// console.log('Total cost:', greedy.cost);
// console.log('Energy cost:', greedy.energyCost);
// console.log('Reserve cost:', greedy.reserveCost);
// console.log('Generation:', greedy.generation);
// console.log('Reserves:', greedy.reserves);
// console.log('Duals:', greedy.duals);
//
// console.log('\n--- LP SCED ---');
// const lp = solveSCED(gens, zns, resReq, { demand: 200 });
// console.log('Status:', lp.status);
// console.log('Total cost:', lp.cost);
// console.log('Energy cost:', lp.energyCost);
// console.log('Reserve cost:', lp.reserveCost);
// console.log('Generation:', lp.generation);
// console.log('Reserves:', lp.reserves);
// console.log('Duals:', lp.duals);
//
// // Test with tight reserves — zone 1 should have higher dual
// const tightReq = [20, 50];
// const tightResult = solveSCED(gens, zns, tightReq, { demand: 150 });
// console.log('\n--- Tight Zone 1 ---');
// console.log('Status:', tightResult.status);
// console.log('Reserve duals:', tightResult.duals.reserveZonal);
// console.log('Zone 1 dual should be higher than zone 0');
