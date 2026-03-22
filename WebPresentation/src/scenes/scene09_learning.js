// === Scene 09: Learning Reshapes Uncertainty ===
// Shows the ellipse shrinking through 5 training snapshots with 200 residual dots,
// cost curve, and reserve bars. Uses real projected data.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';
import { drawResidualDots, drawProjectedEllipse, interpolateInsideMask } from '../components/residualDots.js';
import { interpolateEllipse, computeViewport } from '../math/projection.js';

// Hardcoded snapshot metadata (cost/reserves from training_snapshots.json)
const SNAPSHOTS = [
  { pct: 0, cost: 99944, reserveCost: 9115, coverage: 0.986,
    reserves: [51.81, 48.40, 59.65, 65.45, 140.18, 38.85, 375.31, 295.68, 228.68, 259.43] },
  { pct: 25, cost: 98377, reserveCost: 7604, coverage: 0.979,
    reserves: [48.64, 45.45, 58.22, 63.88, 125.75, 34.85, 314.34, 247.64, 192.90, 218.85] },
  { pct: 50, cost: 97053, reserveCost: 6329, coverage: 0.974,
    reserves: [45.97, 42.95, 57.02, 62.56, 113.57, 31.48, 262.85, 207.08, 162.69, 184.57] },
  { pct: 75, cost: 96030, reserveCost: 5344, coverage: 0.969,
    reserves: [43.91, 41.03, 56.09, 61.54, 104.16, 28.87, 223.09, 175.75, 139.36, 158.10] },
  { pct: 100, cost: 95471, reserveCost: 4805, coverage: 0.967,
    reserves: [42.79, 39.97, 55.58, 60.98, 99.01, 27.44, 201.34, 158.62, 126.60, 143.63] },
];

const NUM_SNAPSHOTS = SNAPSHOTS.length;
const STEP_DURATION = 2.0;

export function createScene09() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let iterProgress = new AnimatedValue(0);
  let autoPlaying = false;
  let autoTimer = 0;
  let currentStep = 0;

  // Data from state.residualData
  let samples = null;
  let trainingEllipses = null;

  // Cost range
  const minCost = SNAPSHOTS[NUM_SNAPSHOTS - 1].cost;
  const maxCost = SNAPSHOTS[0].cost;

  function getCurrentCost(progress) {
    const idx = Math.floor(progress);
    const frac = progress - idx;
    if (idx >= NUM_SNAPSHOTS - 1) return SNAPSHOTS[NUM_SNAPSHOTS - 1].cost;
    return SNAPSHOTS[idx].cost + (SNAPSHOTS[idx + 1].cost - SNAPSHOTS[idx].cost) * frac;
  }

  function getCurrentReserves(progress) {
    const idx = Math.floor(progress);
    const frac = progress - idx;
    if (idx >= NUM_SNAPSHOTS - 1) return SNAPSHOTS[NUM_SNAPSHOTS - 1].reserves;
    const r0 = SNAPSHOTS[idx].reserves;
    const r1 = SNAPSHOTS[idx + 1].reserves;
    return r0.map((v, i) => v + (r1[i] - v) * frac);
  }

  function getCurrentEllipseParams(progress) {
    if (!trainingEllipses) return { semi_a: 140, semi_b: 375, coverage: 0.986, insideMask: null };
    const idx = Math.floor(progress);
    const frac = progress - idx;
    if (idx >= NUM_SNAPSHOTS - 1) {
      const last = trainingEllipses[NUM_SNAPSHOTS - 1];
      return { semi_a: last.semi_a, semi_b: last.semi_b, coverage: last.coverage, insideMask: last.inside_mask };
    }
    const snap1 = trainingEllipses[idx];
    const snap2 = trainingEllipses[idx + 1];
    const interp = interpolateEllipse(snap1, snap2, frac);
    const mask = interpolateInsideMask(snap1.inside_mask, snap2.inside_mask, frac);
    return { semi_a: interp.semi_a, semi_b: interp.semi_b, coverage: interp.coverage, insideMask: mask };
  }

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);
      iterProgress.snap(0);
      currentStep = 0;
      autoTimer = 0;

      if (state.residualData) {
        samples = state.residualData.samples;
        trainingEllipses = state.residualData.training_ellipses;
      }

      autoPlaying = (state.mode === 'guided');
    },

    exit(state) {
      autoPlaying = false;
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);
      iterProgress.update(dt);

      if (!samples && state.residualData) {
        samples = state.residualData.samples;
        trainingEllipses = state.residualData.training_ellipses;
      }

      if (autoPlaying && state.mode === 'guided') {
        autoTimer += dt;
        if (autoTimer >= STEP_DURATION && currentStep < NUM_SNAPSHOTS - 1) {
          autoTimer = 0;
          currentStep++;
          iterProgress.set(currentStep);
        }
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      const progress = iterProgress.get();
      const pct = Math.round(progress / (NUM_SNAPSHOTS - 1) * 100);

      // ==============================
      // LAYOUT: ellipse top, cost chart middle, bars bottom
      // ==============================
      const plotCx = width * 0.5;
      const plotCy = height * 0.28;
      const plotW = width * 0.45;
      const plotH = height * 0.38;

      // ==============================
      // LAYER 1: Iteration label + coverage
      // ==============================
      Renderer.drawText(ctx, `Training: ${pct}%`, plotCx, height * 0.05, {
        font: 'bold 18px Inter, sans-serif',
        color: COLORS.teal,
        align: 'center',
        baseline: 'middle',
        alpha: 0.9,
      });

      const ellipseParams = getCurrentEllipseParams(progress);

      // Coverage label
      Renderer.drawText(ctx, `Coverage: ${(ellipseParams.coverage * 100).toFixed(1)}%`, plotCx, height * 0.09, {
        font: '13px Inter, sans-serif',
        color: COLORS.inkLight,
        align: 'center',
        baseline: 'middle',
        alpha: 0.7,
      });

      // ==============================
      // LAYER 2: Ellipse with dots
      // ==============================
      // Compute viewport based on largest ellipse (pct=0)
      const maxSemiA = trainingEllipses ? trainingEllipses[0].semi_a : 150;
      const maxSemiB = trainingEllipses ? trainingEllipses[0].semi_b : 400;
      const viewport = computeViewport(plotCx, plotCy, plotW, plotH, maxSemiA, maxSemiB, 1.35);

      // Draw ghost ellipses for previous steps
      if (trainingEllipses) {
        const currentIdx = Math.floor(progress);
        for (let i = 0; i < currentIdx; i++) {
          const snap = trainingEllipses[i];
          drawProjectedEllipse(ctx, snap.semi_a, snap.semi_b, viewport, {
            fillColor: null,
            strokeColor: COLORS.teal,
            lineWidth: 1,
            alpha: alpha * (0.08 + 0.04 * (i / NUM_SNAPSHOTS)),
            dash: [3, 5],
          });
        }
      }

      // Draw residual dots
      if (samples && ellipseParams.insideMask) {
        drawResidualDots(ctx, samples, ellipseParams.insideMask, viewport, {
          alpha: alpha * 0.85,
          dotRadius: 2.5,
        });
      }

      // Draw current ellipse
      drawProjectedEllipse(ctx, ellipseParams.semi_a, ellipseParams.semi_b, viewport, {
        fillColor: 'rgba(26, 122, 109, 0.04)',
        strokeColor: COLORS.teal,
        lineWidth: 2.5,
        alpha: alpha * 0.9,
      });

      // ==============================
      // LAYER 3: Cost curve
      // ==============================
      const chartW = Math.min(420, width * 0.45);
      const chartH = 80;
      const chart = {
        x: (width - chartW) / 2,
        y: height * 0.54,
        w: chartW,
        h: chartH,
      };

      Renderer.drawText(ctx, 'Total Operating Cost', chart.x + chart.w / 2, chart.y - 14, {
        font: '12px Inter, sans-serif',
        color: COLORS.inkLight,
        align: 'center',
        baseline: 'bottom',
        alpha: 0.6,
      });

      // Chart background
      ctx.save();
      ctx.globalAlpha = alpha * 0.04;
      ctx.fillStyle = COLORS.ink;
      ctx.fillRect(chart.x, chart.y, chart.w, chart.h);
      ctx.restore();

      // Axes
      Renderer.drawLine(ctx, chart.x, chart.y + chart.h, chart.x + chart.w, chart.y + chart.h, {
        color: COLORS.ink, lineWidth: 1, alpha: 0.15,
      });
      Renderer.drawLine(ctx, chart.x, chart.y, chart.x, chart.y + chart.h, {
        color: COLORS.ink, lineWidth: 1, alpha: 0.15,
      });

      // Cost line
      ctx.save();
      ctx.globalAlpha = alpha * 0.7;
      ctx.beginPath();
      for (let i = 0; i < NUM_SNAPSHOTS; i++) {
        const x = chart.x + (i / (NUM_SNAPSHOTS - 1)) * chart.w;
        const costNorm = (SNAPSHOTS[i].cost - minCost) / (maxCost - minCost);
        const y = chart.y + chart.h - costNorm * (chart.h * 0.85) - chart.h * 0.05;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = COLORS.teal;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();

      // Snapshot dots on curve
      const currentIdx = Math.floor(progress);
      for (let i = 0; i < NUM_SNAPSHOTS; i++) {
        const x = chart.x + (i / (NUM_SNAPSHOTS - 1)) * chart.w;
        const costNorm = (SNAPSHOTS[i].cost - minCost) / (maxCost - minCost);
        const y = chart.y + chart.h - costNorm * (chart.h * 0.85) - chart.h * 0.05;
        Renderer.drawParticle(ctx, x, y, 3, COLORS.teal, alpha * (i <= currentIdx ? 0.7 : 0.2));

        Renderer.drawText(ctx, `${SNAPSHOTS[i].pct}%`, x, chart.y + chart.h + 10, {
          font: '10px Inter, sans-serif',
          color: COLORS.inkLight,
          align: 'center',
          baseline: 'top',
          alpha: 0.5,
        });
      }

      // Moving dot
      {
        const xPos = chart.x + (progress / (NUM_SNAPSHOTS - 1)) * chart.w;
        const currentCost = getCurrentCost(progress);
        const costNorm = (currentCost - minCost) / (maxCost - minCost);
        const yPos = chart.y + chart.h - costNorm * (chart.h * 0.85) - chart.h * 0.05;

        Renderer.drawGlow(ctx, xPos, yPos, 12, COLORS.ember, 0.5);
        Renderer.drawParticle(ctx, xPos, yPos, 5, COLORS.ember, alpha * 0.9);

        Renderer.drawText(ctx, `$${Math.round(currentCost).toLocaleString()}/hr`, xPos, yPos - 14, {
          font: 'bold 12px Inter, sans-serif',
          color: COLORS.ember,
          align: 'center',
          baseline: 'bottom',
          alpha: 0.9,
        });
      }

      // Y-axis labels
      Renderer.drawText(ctx, `$${maxCost.toLocaleString()}`, chart.x - 6, chart.y + chart.h * 0.1, {
        font: '9px Inter, sans-serif', color: COLORS.inkLight, align: 'right', baseline: 'middle', alpha: 0.4,
      });
      Renderer.drawText(ctx, `$${minCost.toLocaleString()}`, chart.x - 6, chart.y + chart.h * 0.9, {
        font: '9px Inter, sans-serif', color: COLORS.inkLight, align: 'right', baseline: 'middle', alpha: 0.4,
      });

      // ==============================
      // LAYER 4: Reserve bars
      // ==============================
      const barW = 18;
      const gap = 6;
      const totalBarsW = 10 * barW + 9 * gap;
      const bars = {
        startX: (width - totalBarsW) / 2,
        baselineY: height * 0.87,
        barW, gap,
        maxBarH: 65,
      };

      Renderer.drawText(ctx, 'Reserve Requirements (MW)', bars.startX + totalBarsW / 2, bars.baselineY - bars.maxBarH - 12, {
        font: '12px Inter, sans-serif', color: COLORS.inkLight, align: 'center', baseline: 'bottom', alpha: 0.6,
      });

      Renderer.drawLine(ctx, bars.startX - 5, bars.baselineY, bars.startX + totalBarsW + 5, bars.baselineY, {
        color: COLORS.ink, lineWidth: 1, alpha: 0.2,
      });

      const currentReserves = getCurrentReserves(progress);
      const maxReserve = Math.max(...SNAPSHOTS[0].reserves);

      for (let i = 0; i < 10; i++) {
        const bx = bars.startX + i * (barW + gap);
        const h = (currentReserves[i] / maxReserve) * bars.maxBarH;

        Renderer.drawBar(ctx, bx, bars.baselineY, barW, h, {
          color: COLORS.ember, alpha: 0.6, radius: 2,
        });

        Renderer.drawText(ctx, `Z${i + 1}`, bx + barW / 2, bars.baselineY + 5, {
          font: '9px Inter, sans-serif', color: COLORS.ink, align: 'center', baseline: 'top', alpha: 0.45,
        });
      }

      // ==============================
      // Scrub hint
      // ==============================
      if (state.mode === 'explore') {
        const hintAlpha = 0.3 + 0.12 * Math.sin(elapsed * 2);
        Renderer.drawText(ctx, 'Click to step through iterations', width * 0.5, height * 0.96, {
          font: '12px Inter, sans-serif', color: COLORS.inkLight, align: 'center', baseline: 'middle', alpha: hintAlpha,
        });
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      if (event.type === 'click') {
        if (state.mode === 'explore') {
          currentStep = (currentStep + 1) % NUM_SNAPSHOTS;
          iterProgress.set(currentStep);
        } else {
          if (currentStep < NUM_SNAPSHOTS - 1) {
            currentStep++;
            iterProgress.set(currentStep);
            autoTimer = 0;
          }
        }
      }
    },
  };
}
