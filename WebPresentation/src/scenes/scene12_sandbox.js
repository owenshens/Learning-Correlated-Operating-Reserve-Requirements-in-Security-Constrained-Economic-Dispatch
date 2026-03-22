// === Scene 12: Live Sandbox ===
// Interactive exploration scene. User controls context sliders (load/solar/wind/time)
// and method selection. Everything updates live: zone map, ellipse, reserve bars, costs.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';
import { supportPoint, interpolateL } from '../math/ellipse.js';

// --- Constants ---

const NUM_ZONES = 10;

// Zone adjacency for the network topology lines
const ZONE_ADJACENCY = [
  [1, 5], [0, 2, 6], [1, 3, 7], [2, 4, 8], [3, 9],
  [0, 6], [1, 5, 7], [2, 6, 8], [3, 7, 9], [4, 8],
];

// 2D projection directions for exposure vectors (one per zone)
const EXPOSURE_DIRS = [
  [ 0.85, -0.53],  // Z1
  [ 0.42, -0.91],  // Z2
  [-0.42, -0.91],  // Z3
  [-0.85, -0.53],  // Z4
  [ 0.71,  0.71],  // Z5
  [-0.99,  0.10],  // Z6
  [ 0.31, -0.95],  // Z7
  [-0.87,  0.50],  // Z8
  [ 0.95,  0.31],  // Z9
  [-0.59,  0.81],  // Z10
];

// A "low uncertainty" L for contextual interpolation (more circular)
const L_LOW = [[1.2, 0], [0.15, 1.1]];

// A "high uncertainty" L for contextual interpolation (more eccentric)
const L_HIGH = [[2.6, 0], [1.2, 0.7]];

// Static method L matrices for visualization (2D projections)
const METHOD_L_2D = {
  box:       [[1.8, 0], [0.0, 1.8]],
  samplecov: [[1.8, 0], [0.3, 1.6]],
  staticl:   [[1.8, 0], [0.6, 1.3]],
  contextual: null,
};

// Map from app state method names to scenario keys
const METHOD_KEY_MAP = {
  box: 'box',
  samplecov: 'samplecov',
  staticl: 'staticl',
  contextual: 'nn',
};

// Throttle: minimum ms between SCED recomputations
const RECOMPUTE_INTERVAL_MS = 100;

export function createScene12() {
  // --- Local state ---
  let elapsed = 0;
  let opacity = new AnimatedValue(0);

  // Data loaded async
  let scenarios = null;
  let zonesData = null;

  // Animated values for smooth transitions
  let animReserves = [];
  let animDuals = [];
  let animTotalCost = new AnimatedValue(0);
  let animEnergyCost = new AnimatedValue(0);
  let animReserveCost = new AnimatedValue(0);
  let animReserveTotal = new AnimatedValue(0);

  // Current computed values
  let currentL2D = [[1.8, 0], [0.6, 1.3]];

  // Previous context + method for change detection
  let prevContext = null;
  let prevMethod = '';
  let prevCoupled = false;

  // SCED recompute throttle
  let timeSinceLastCompute = 0;
  let needsRecompute = true;

  // Selected zone for highlighting
  let highlightedZone = -1;

  // Initialize animated values
  for (let z = 0; z < NUM_ZONES; z++) {
    animReserves.push(new AnimatedValue(0));
    animDuals.push(new AnimatedValue(0));
  }

  // ===================================================================
  // Data loading
  // ===================================================================

  function loadScenarios() {
    return fetch('data/precomputed/scenarios.json')
      .then(resp => resp.json())
      .then(data => { scenarios = data; })
      .catch(err => { console.warn('Failed to load scenarios:', err); scenarios = null; });
  }

  // ===================================================================
  // Computation helpers
  // ===================================================================

  function interpolateScenarios(context, methodKey, coupled) {
    if (!scenarios || scenarios.length < 2) {
      if (!scenarios || scenarios.length === 0) return null;
      const m = scenarios[0].methods[methodKey];
      if (!m) return null;
      return buildResult(m, coupled);
    }

    const loadVal = 0.7 + context.load * 0.6;
    const solarVal = context.solar * 2.0;
    const windVal = context.wind * 2.5;

    // Find two closest scenarios
    let dists = scenarios.map((s, i) => {
      const dl = (loadVal - s.load_scale) * 2;
      const ds = solarVal - s.solar_scale;
      const dw = windVal - s.wind_scale;
      return { idx: i, dist: dl * dl + ds * ds + dw * dw };
    });
    dists.sort((a, b) => a.dist - b.dist);

    const s0 = scenarios[dists[0].idx];
    const s1 = scenarios[dists[1].idx];
    const d0 = dists[0].dist;
    const d1 = dists[1].dist;
    const totalDist = d0 + d1;

    if (totalDist < 1e-10) {
      return buildResult(s0.methods[methodKey], coupled);
    }

    const t = d0 / totalDist;

    const m0 = s0.methods[methodKey];
    const m1 = s1.methods[methodKey];
    if (!m0 && !m1) return null;
    if (!m0) return buildResult(m1, coupled);
    if (!m1) return buildResult(m0, coupled);

    const rpz0 = coupled ? (m0.coupled_reserves_per_zone || m0.reserves_per_zone) : m0.reserves_per_zone;
    const rpz1 = coupled ? (m1.coupled_reserves_per_zone || m1.reserves_per_zone) : m1.reserves_per_zone;

    const result = {
      cost: m0.cost * (1 - t) + m1.cost * t,
      reserve_cost: m0.reserve_cost * (1 - t) + m1.reserve_cost * t,
      energy_cost: m0.energy_cost * (1 - t) + m1.energy_cost * t,
      reserves_per_zone: new Array(NUM_ZONES),
      reserve_total: m0.reserve_total * (1 - t) + m1.reserve_total * t,
      duals_per_zone: new Array(NUM_ZONES),
    };

    for (let z = 0; z < NUM_ZONES; z++) {
      result.reserves_per_zone[z] = (rpz0[z] || 0) * (1 - t) + (rpz1[z] || 0) * t;
      result.duals_per_zone[z] = (m0.duals_per_zone[z] || 0) * (1 - t) + (m1.duals_per_zone[z] || 0) * t;
    }

    return result;
  }

  function buildResult(m, coupled) {
    if (!m) return null;
    const rpz = coupled ? (m.coupled_reserves_per_zone || m.reserves_per_zone) : m.reserves_per_zone;
    return {
      cost: m.cost,
      reserve_cost: m.reserve_cost,
      energy_cost: m.energy_cost,
      reserves_per_zone: rpz,
      reserve_total: m.reserve_total,
      duals_per_zone: m.duals_per_zone,
    };
  }

  function computeL2D(method, context) {
    if (method === 'contextual') {
      const uncertainty = 0.3 * context.load + 0.35 * context.solar + 0.35 * context.wind;
      return interpolateL(L_LOW, L_HIGH, uncertainty);
    }
    return METHOD_L_2D[method] || METHOD_L_2D.staticl;
  }

  function recompute(state) {
    const method = state.method || 'staticl';
    const context = state.context || { load: 0.5, solar: 0.5, wind: 0.5, timeOfDay: 12 };
    const coupled = state.coupled || false;
    const methodKey = METHOD_KEY_MAP[method] || method;

    currentL2D = computeL2D(method, context);

    const result = interpolateScenarios(context, methodKey, coupled);

    if (result) {
      for (let z = 0; z < NUM_ZONES; z++) {
        animReserves[z].set(result.reserves_per_zone[z] || 0);
        animDuals[z].set(result.duals_per_zone[z] || 0);
      }
      animTotalCost.set(result.cost);
      animEnergyCost.set(result.energy_cost);
      animReserveCost.set(result.reserve_cost);
      animReserveTotal.set(result.reserve_total);
    } else {
      // Fallback synthetic values
      const loadScale = 0.7 + context.load * 0.6;
      for (let z = 0; z < NUM_ZONES; z++) {
        animReserves[z].set((40 + z * 15) * loadScale);
        animDuals[z].set(z === 4 ? 5.0 * loadScale : 0);
      }
      animTotalCost.set(95000 + context.load * 5000);
      animEnergyCost.set(90000 + context.load * 1000);
      animReserveCost.set(5000 + context.load * 4000);
      animReserveTotal.set(900 + context.load * 600);
    }
  }

  function hasChanged(state) {
    const ctx = state.context;
    if (state.method !== prevMethod) return true;
    if (state.coupled !== prevCoupled) return true;
    if (!prevContext) return true;
    if (Math.abs(ctx.load - prevContext.load) > 0.005) return true;
    if (Math.abs(ctx.solar - prevContext.solar) > 0.005) return true;
    if (Math.abs(ctx.wind - prevContext.wind) > 0.005) return true;
    if (Math.abs((ctx.timeOfDay || 12) - (prevContext.timeOfDay || 12)) > 0.5) return true;
    return false;
  }

  function saveContext(state) {
    prevContext = { ...state.context };
    prevMethod = state.method;
    prevCoupled = state.coupled;
  }

  // ===================================================================
  // Layout helpers
  // ===================================================================

  function getZoneMapRect(width, height) {
    return { x: 30, y: 80, w: width * 0.27, h: height * 0.65 };
  }

  function getEllipseCenter(width, height) {
    return { x: width * 0.5, y: height * 0.42 };
  }

  function getEllipseScale(width, height) {
    return Math.min(width * 0.10, height * 0.16, 120);
  }

  function getBarArea(width, height) {
    const barAreaWidth = width * 0.25;
    const barW = Math.max(12, Math.min(20, (barAreaWidth - 9 * 6) / 10));
    const barGap = Math.max(3, Math.min(6, barW * 0.3));
    const totalW = NUM_ZONES * barW + (NUM_ZONES - 1) * barGap;
    const startX = width * 0.72 - totalW / 2 + width * 0.01;
    const baselineY = height * 0.78;
    return { startX, baselineY, totalW, barW, barGap };
  }

  function getCostArea(width, height) {
    return { x: width * 0.72, y: height * 0.12 };
  }

  function formatCost(val) {
    if (val === 0 || isNaN(val)) return '$0';
    return '$' + Math.round(val).toLocaleString();
  }

  function hitTestZone(mx, my, width, height) {
    if (!zonesData) return -1;
    const rect = getZoneMapRect(width, height);
    for (let z = 0; z < NUM_ZONES; z++) {
      const zd = zonesData[z];
      const px = rect.x + zd.x * rect.w;
      const py = rect.y + zd.y * rect.h;
      const radius = 12 + (zd.load_mw / 900) * 8;
      const dx = mx - px;
      const dy = my - py;
      if (dx * dx + dy * dy < (radius + 5) * (radius + 5)) {
        return z;
      }
    }
    return -1;
  }

  // ===================================================================
  // Render sub-functions
  // ===================================================================

  function renderZoneMap(ctx, width, height, maxDual) {
    const rect = getZoneMapRect(width, height);
    if (!zonesData) return;

    ctx.save();

    // Panel label
    Renderer.drawText(ctx, 'Zone Map', rect.x + rect.w / 2, rect.y - 16, {
      font: 'bold 12px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'bottom',
      alpha: 0.6,
    });

    // Draw connections between adjacent zones
    const drawnEdges = new Set();
    for (let i = 0; i < NUM_ZONES; i++) {
      for (const j of ZONE_ADJACENCY[i]) {
        const key = Math.min(i, j) + '-' + Math.max(i, j);
        if (drawnEdges.has(key)) continue;
        drawnEdges.add(key);

        const z1 = zonesData[i];
        const z2 = zonesData[j];
        const x1 = rect.x + z1.x * rect.w;
        const y1 = rect.y + z1.y * rect.h;
        const x2 = rect.x + z2.x * rect.w;
        const y2 = rect.y + z2.y * rect.h;

        Renderer.drawLine(ctx, x1, y1, x2, y2, {
          color: COLORS.ink,
          lineWidth: 0.8,
          alpha: 0.12,
        });
      }
    }

    // Draw zone circles
    for (let z = 0; z < NUM_ZONES; z++) {
      const zd = zonesData[z];
      const px = rect.x + zd.x * rect.w;
      const py = rect.y + zd.y * rect.h;
      const dualVal = animDuals[z].get();
      const dualNorm = Math.min(1, dualVal / maxDual);
      const reserveVal = animReserves[z].get();

      // Zone radius proportional to load
      const baseRadius = 10 + (zd.load_mw / 900) * 10;
      const isHighlighted = (highlightedZone === z);

      // Glow for zones with shadow prices
      if (dualNorm > 0.02) {
        const pulse = 0.8 + 0.2 * Math.sin(elapsed * 2.5 + z * 0.9);
        const glowRadius = baseRadius * 2.5 + dualNorm * 15;
        Renderer.drawGlow(ctx, px, py, glowRadius, COLORS.ember, dualNorm * pulse * 0.55);
      }

      // Highlight ring for selected zone
      if (isHighlighted) {
        ctx.save();
        ctx.strokeStyle = COLORS.teal;
        ctx.lineWidth = 2.5;
        ctx.globalAlpha = 0.8;
        ctx.beginPath();
        ctx.arc(px, py, baseRadius + 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      // Zone circle fill
      ctx.save();
      if (dualNorm > 0.02) {
        ctx.fillStyle = `rgba(232, 118, 58, ${0.35 + dualNorm * 0.45})`;
      } else {
        ctx.fillStyle = 'rgba(26, 122, 109, 0.25)';
      }
      ctx.beginPath();
      ctx.arc(px, py, baseRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Zone label
      Renderer.drawText(ctx, `Z${z + 1}`, px, py + baseRadius + 10, {
        font: '9px Inter, sans-serif',
        color: COLORS.ink,
        align: 'center',
        baseline: 'top',
        alpha: 0.5,
      });

      // Show reserve value inside circle for highlighted zone
      if (isHighlighted) {
        Renderer.drawText(ctx, `${Math.round(reserveVal)}`, px, py - 2, {
          font: 'bold 10px Inter, sans-serif',
          color: COLORS.ink,
          align: 'center',
          baseline: 'middle',
          alpha: 0.8,
        });
        Renderer.drawText(ctx, 'MW', px, py + 9, {
          font: '8px Inter, sans-serif',
          color: COLORS.inkLight,
          align: 'center',
          baseline: 'middle',
          alpha: 0.5,
        });
      }

      // Mu label for constrained zones
      if (dualNorm > 0.05) {
        Renderer.drawText(ctx, `\u03BC=${dualVal.toFixed(1)}`, px, py - baseRadius - 8, {
          font: '9px Inter, sans-serif',
          color: COLORS.ember,
          align: 'center',
          baseline: 'bottom',
          alpha: 0.7 * dualNorm + 0.3,
        });
      }
    }

    ctx.restore();
  }

  function renderEllipse(ctx, width, height, maxDual) {
    const center = getEllipseCenter(width, height);
    const scale = getEllipseScale(width, height);

    ctx.save();

    // Panel label
    Renderer.drawText(ctx, 'Uncertainty Set', center.x, center.y - scale * 2.0 - 10, {
      font: 'bold 12px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'bottom',
      alpha: 0.6,
    });

    // Faint reference crosshair
    ctx.save();
    ctx.globalAlpha = 0.04;
    ctx.strokeStyle = COLORS.ink;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(center.x - scale * 2.2, center.y);
    ctx.lineTo(center.x + scale * 2.2, center.y);
    ctx.moveTo(center.x, center.y - scale * 2.2);
    ctx.lineTo(center.x, center.y + scale * 2.2);
    ctx.stroke();
    ctx.restore();

    // Draw ellipse
    Renderer.drawEllipse(ctx, center.x, center.y, currentL2D, scale, {
      fillColor: 'rgba(26, 122, 109, 0.06)',
      strokeColor: COLORS.teal,
      lineWidth: 2.5,
      alpha: 0.85,
    });

    // Find top 3 zones by dual value for exposure vector display
    let zonesByDual = [];
    for (let z = 0; z < NUM_ZONES; z++) {
      zonesByDual.push({ zone: z, dual: animDuals[z].get() });
    }
    zonesByDual.sort((a, b) => b.dual - a.dual);

    // Always show at least 3 exposure vectors
    const vectorZones = new Set();
    if (highlightedZone >= 0) {
      vectorZones.add(highlightedZone);
    }
    for (const zd of zonesByDual) {
      if (vectorZones.size >= 3) break;
      if (zd.dual > 0.01 || vectorZones.size < 3) {
        vectorZones.add(zd.zone);
      }
    }

    // Draw exposure vectors
    for (const z of vectorZones) {
      const dir = EXPOSURE_DIRS[z];
      const sp = supportPoint(currentL2D, dir);
      const spScreen = {
        x: center.x + sp.x * scale,
        y: center.y + sp.y * scale,
      };

      const dualVal = animDuals[z].get();
      const dualNorm = Math.min(1, dualVal / maxDual);
      const isHl = (highlightedZone === z);
      const isConstrained = dualNorm > 0.02;

      const arrowLen = isHl ? 65 : 50;
      const fromX = spScreen.x + dir[0] * arrowLen;
      const fromY = spScreen.y + dir[1] * arrowLen;

      const vecColor = isConstrained ? COLORS.ember : COLORS.teal;
      const vecAlpha = isHl ? 0.7 : (isConstrained ? 0.4 : 0.2);
      const vecWidth = isHl ? 2 : 1.5;

      Renderer.drawArrow(ctx, fromX, fromY, spScreen.x, spScreen.y, {
        color: vecColor,
        lineWidth: vecWidth,
        headSize: isHl ? 8 : 6,
        alpha: vecAlpha,
      });

      // Support point dot
      const dotRadius = isHl ? 5 : 3;
      const dotPulse = isHl ? (0.7 + 0.3 * Math.sin(elapsed * 4)) : 1;
      ctx.save();
      ctx.globalAlpha = vecAlpha * dotPulse;
      ctx.fillStyle = vecColor;
      ctx.beginPath();
      ctx.arc(spScreen.x, spScreen.y, dotRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Zone label at arrow tip
      Renderer.drawText(ctx, `Z${z + 1}`, fromX + dir[0] * 12, fromY + dir[1] * 12, {
        font: `${isHl ? 'bold ' : ''}10px Inter, sans-serif`,
        color: vecColor,
        align: 'center',
        baseline: 'middle',
        alpha: vecAlpha + 0.2,
      });
    }

    // Formula beneath ellipse
    Renderer.drawText(ctx, 'R_z = \u03C1 \u00B7 ||L\u1D40 w_z||', center.x, center.y + scale * 1.8 + 12, {
      font: 'italic 12px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'top',
      alpha: 0.4,
    });

    ctx.restore();
  }

  function renderCostBreakdown(ctx, width, height) {
    const cost = getCostArea(width, height);

    ctx.save();

    Renderer.drawText(ctx, 'Total', cost.x, cost.y, {
      font: '11px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'bottom',
      alpha: 0.6,
    });

    Renderer.drawText(ctx, `${formatCost(animTotalCost.get())}/hr`, cost.x, cost.y + 16, {
      font: 'bold 20px Inter, sans-serif',
      color: COLORS.ink,
      align: 'center',
      baseline: 'bottom',
      alpha: 1,
    });

    const subY = cost.y + 34;
    Renderer.drawText(ctx, `Energy: ${formatCost(animEnergyCost.get())}`, cost.x, subY, {
      font: '11px Inter, sans-serif',
      color: COLORS.teal,
      align: 'center',
      baseline: 'top',
      alpha: 0.65,
    });

    Renderer.drawText(ctx, `Reserve: ${formatCost(animReserveCost.get())}`, cost.x, subY + 16, {
      font: '11px Inter, sans-serif',
      color: COLORS.ember,
      align: 'center',
      baseline: 'top',
      alpha: 0.65,
    });

    Renderer.drawText(ctx, `Total Reserve: ${Math.round(animReserveTotal.get())} MW`, cost.x, subY + 32, {
      font: '10px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'top',
      alpha: 0.45,
    });

    ctx.restore();
  }

  function renderReserveBars(ctx, width, height, maxDual) {
    const { startX, baselineY, totalW, barW, barGap } = getBarArea(width, height);

    ctx.save();

    // Panel label
    Renderer.drawText(ctx, 'Zonal Reserves', startX + totalW / 2, baselineY - height * 0.42, {
      font: 'bold 12px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'bottom',
      alpha: 0.6,
    });

    // Find max reserve for bar scaling
    let maxReserve = 50;
    for (let z = 0; z < NUM_ZONES; z++) {
      const r = animReserves[z].get();
      if (r > maxReserve) maxReserve = r;
    }
    const maxBarH = height * 0.35;

    // Baseline
    Renderer.drawLine(ctx, startX - 5, baselineY, startX + totalW + 5, baselineY, {
      color: COLORS.ink,
      lineWidth: 1,
      alpha: 0.2,
    });

    // Draw bars
    for (let z = 0; z < NUM_ZONES; z++) {
      const reserveVal = animReserves[z].get();
      const dualVal = animDuals[z].get();
      const dualNorm = Math.min(1, dualVal / maxDual);
      const isHl = (highlightedZone === z);

      const bx = startX + z * (barW + barGap);
      const bh = (reserveVal / maxReserve) * maxBarH;

      // Glow for constrained zones
      if (dualNorm > 0.02) {
        const pulse = 0.8 + 0.2 * Math.sin(elapsed * 2.5 + z * 0.8);
        Renderer.drawGlow(
          ctx, bx + barW / 2, baselineY - bh / 2,
          18 + dualNorm * 15, COLORS.ember, dualNorm * pulse * 0.4
        );
      }

      // Bar
      if (bh > 0.5) {
        const barAlpha = 0.5 + dualNorm * 0.35;
        const barColor = dualNorm > 0.3 ? COLORS.coral : COLORS.ember;

        Renderer.drawBar(ctx, bx, baselineY, barW, bh, {
          color: barColor,
          alpha: isHl ? Math.min(1, barAlpha + 0.2) : barAlpha,
          radius: 2,
          glowColor: dualNorm > 0.1 ? COLORS.ember : null,
          glowIntensity: dualNorm > 0.1 ? dualNorm * 0.5 : 0,
        });

        // Highlight border
        if (isHl) {
          ctx.save();
          ctx.strokeStyle = COLORS.teal;
          ctx.lineWidth = 1.5;
          ctx.globalAlpha = 0.8;
          ctx.strokeRect(bx - 1, baselineY - bh - 1, barW + 2, bh + 2);
          ctx.restore();
        }

        // Reserve value above notable bars
        if (dualNorm > 0.1 || isHl || reserveVal > maxReserve * 0.6) {
          Renderer.drawText(ctx, Math.round(reserveVal).toString(), bx + barW / 2, baselineY - bh - 5, {
            font: '9px Inter, sans-serif',
            color: isHl ? COLORS.ink : COLORS.ember,
            align: 'center',
            baseline: 'bottom',
            alpha: isHl ? 0.8 : 0.6,
          });
        }
      }

      // Zone labels below bars
      Renderer.drawText(ctx, `Z${z + 1}`, bx + barW / 2, baselineY + 5, {
        font: '9px Inter, sans-serif',
        color: isHl ? COLORS.teal : COLORS.ink,
        align: 'center',
        baseline: 'top',
        alpha: isHl ? 0.8 : 0.45,
      });
    }

    ctx.restore();
  }

  function renderMethodLabel(ctx, width, height, method) {
    const labels = {
      box: 'Box (Diagonal)',
      samplecov: 'Sample Covariance',
      staticl: 'Learned (Static L)',
      contextual: 'Learned (Contextual)',
    };

    const label = labels[method] || method;
    const center = getEllipseCenter(width, height);
    const scale = getEllipseScale(width, height);

    ctx.save();

    const chipX = center.x;
    const chipY = center.y - scale * 2.0 - 28;

    ctx.font = '11px Inter, sans-serif';
    const textWidth = ctx.measureText(label).width;
    const chipW = textWidth + 16;
    const chipH = 20;

    // Chip background
    ctx.globalAlpha = 0.08;
    ctx.fillStyle = method === 'contextual' ? COLORS.teal : COLORS.ink;
    const rx = chipX - chipW / 2;
    const ry = chipY - chipH / 2;
    ctx.beginPath();
    ctx.moveTo(rx + 4, ry);
    ctx.lineTo(rx + chipW - 4, ry);
    ctx.quadraticCurveTo(rx + chipW, ry, rx + chipW, ry + 4);
    ctx.lineTo(rx + chipW, ry + chipH - 4);
    ctx.quadraticCurveTo(rx + chipW, ry + chipH, rx + chipW - 4, ry + chipH);
    ctx.lineTo(rx + 4, ry + chipH);
    ctx.quadraticCurveTo(rx, ry + chipH, rx, ry + chipH - 4);
    ctx.lineTo(rx, ry + 4);
    ctx.quadraticCurveTo(rx, ry, rx + 4, ry);
    ctx.closePath();
    ctx.fill();

    // Chip text
    Renderer.drawText(ctx, label, chipX, chipY, {
      font: '11px Inter, sans-serif',
      color: method === 'contextual' ? COLORS.teal : COLORS.ink,
      align: 'center',
      baseline: 'middle',
      alpha: 0.65,
    });

    // Contextual indicator: pulsing dot
    if (method === 'contextual') {
      const dotAlpha = 0.5 + 0.3 * Math.sin(elapsed * 3);
      ctx.globalAlpha = dotAlpha;
      ctx.fillStyle = COLORS.teal;
      ctx.beginPath();
      ctx.arc(chipX - chipW / 2 + 8, chipY, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  // ===================================================================
  // Scene interface (returned object)
  // ===================================================================

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);
      highlightedZone = -1;
      prevContext = null;
      prevMethod = '';
      prevCoupled = false;
      needsRecompute = true;
      timeSinceLastCompute = RECOMPUTE_INTERVAL_MS;

      zonesData = state.zones || null;

      // Load scenario data
      loadScenarios().then(() => {
        needsRecompute = true;
      });

      // Snap animated values to reasonable defaults before first compute
      animTotalCost.snap(95000);
      animEnergyCost.snap(90000);
      animReserveCost.snap(5000);
      animReserveTotal.snap(950);
      for (let z = 0; z < NUM_ZONES; z++) {
        animReserves[z].snap(50);
        animDuals[z].snap(0);
      }

      // Initial computation
      if (state.zones) {
        zonesData = state.zones;
      }
      recompute(state);
      saveContext(state);
    },

    exit(state) {
      // no cleanup needed
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);

      // Ensure we have zones data from state
      if (!zonesData && state.zones) {
        zonesData = state.zones;
      }

      // Check for context/method changes (throttled)
      timeSinceLastCompute += dt * 1000;
      if (hasChanged(state) || needsRecompute) {
        if (timeSinceLastCompute >= RECOMPUTE_INTERVAL_MS) {
          recompute(state);
          saveContext(state);
          timeSinceLastCompute = 0;
          needsRecompute = false;
        }
      }

      // Update all animated values
      animTotalCost.update(dt);
      animEnergyCost.update(dt);
      animReserveCost.update(dt);
      animReserveTotal.update(dt);
      for (let z = 0; z < NUM_ZONES; z++) {
        animReserves[z].update(dt);
        animDuals[z].update(dt);
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      // Get max dual for normalization
      let maxDual = 0.1;
      for (let z = 0; z < NUM_ZONES; z++) {
        const d = animDuals[z].get();
        if (d > maxDual) maxDual = d;
      }

      // PANEL 1: Zone Map (left ~30%)
      renderZoneMap(ctx, width, height, maxDual);

      // PANEL 2: Uncertainty Ellipse (center ~40%)
      renderEllipse(ctx, width, height, maxDual);

      // PANEL 3: Reserve Bars + Cost (right ~30%)
      renderCostBreakdown(ctx, width, height);
      renderReserveBars(ctx, width, height, maxDual);

      // Method label chip above ellipse
      renderMethodLabel(ctx, width, height, state.method);

      ctx.restore();
    },

    onInteraction(event, state) {
      if (event.type === 'click') {
        const canvasEl = document.getElementById('main-canvas');
        const w = canvasEl ? canvasEl.clientWidth : 1200;
        const h = canvasEl ? canvasEl.clientHeight : 800;

        const zone = hitTestZone(event.x, event.y, w, h);
        if (zone >= 0) {
          highlightedZone = (highlightedZone === zone) ? -1 : zone;
          state.selectedZone = highlightedZone >= 0 ? highlightedZone : null;
        } else {
          highlightedZone = -1;
          state.selectedZone = null;
        }
      }
    },
  };
}
