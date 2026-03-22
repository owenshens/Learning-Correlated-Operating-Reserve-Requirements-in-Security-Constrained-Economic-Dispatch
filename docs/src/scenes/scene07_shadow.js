// === Scene 07: Shadow Prices Ignite ===
// Everything from Scene 6 persists. Constrained zones begin to glow.
// Zones with binding reserve constraints get ember/coral glow.
// Pressure gauge arcs and mu labels appear near glowing zones.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeOutCubic } from '../engine/timeline.js';
import { supportPoint } from '../math/ellipse.js';

// --- Data ---

const RESERVE_VALUES = [80, 65, 140, 55, 180, 45, 90, 160, 70, 120];
const ENERGY_VALUES  = [400, 350, 500, 300, 600, 200, 420, 550, 380, 450];
const TOTAL_COST = 95471;

const DUAL_VALUES = [0, 0, 3.2, 0, 4.8, 0, 0.5, 4.1, 0, 2.0];
const MAX_DUAL = 4.8;

const EXPOSURE_ZONES = [0, 2, 4, 7];
const EXPOSURE_DIRS = [
  [0.85, -0.53],
  [-0.42, -0.91],
  [0.71, 0.71],
  [-0.87, 0.50],
];

const DEFAULT_L = [[1.8, 0], [0.6, 1.3]];

const BAR_WIDTH = 30;
const BAR_GAP = 15;

const ZONE_POSITIONS = [
  { x: 0.15, y: 0.75 }, { x: 0.35, y: 0.80 }, { x: 0.55, y: 0.78 },
  { x: 0.75, y: 0.72 }, { x: 0.90, y: 0.60 }, { x: 0.10, y: 0.35 },
  { x: 0.30, y: 0.25 }, { x: 0.50, y: 0.22 }, { x: 0.70, y: 0.28 },
  { x: 0.88, y: 0.38 },
];

const ZONE_ADJACENCY = [
  [1, 5], [0, 2, 6], [1, 3, 7], [2, 4, 8], [3, 9],
  [0, 6], [1, 5, 7], [2, 6, 8], [3, 7, 9], [4, 8],
];

export function createScene07() {
  // --- Local state ---
  let elapsed = 0;
  let entryTime = 0;
  let opacity = new AnimatedValue(0);

  // Stacked bar heights (pre-computed, no entry animation since carried from Scene 6)
  let energyHeights = new Float64Array(10);
  let reserveHeights = new Float64Array(10);

  // Dual animation values (animate from 0 to target on entry)
  let dualAnimValues = new Float64Array(10);
  let dualTargets = new Float64Array(10);
  let dualsIgnited = false;

  let ellipseL = DEFAULT_L;
  let ellipseScale = 120;

  // --- Helpers ---

  function getEllipseCenter(width, height) {
    return { x: width * 0.5, y: height * 0.38 };
  }

  function getBarArea(width, height) {
    const totalW = 10 * BAR_WIDTH + 9 * BAR_GAP;
    const startX = (width - totalW) / 2;
    const baselineY = height * 0.82;
    return { startX, baselineY, totalW };
  }

  function maxTotal() {
    let m = 0;
    for (let i = 0; i < 10; i++) {
      const t = ENERGY_VALUES[i] + RESERVE_VALUES[i];
      if (t > m) m = t;
    }
    return m;
  }

  function getMiniMapRect(width, height) {
    return { x: 30, y: 30, w: 160, h: 110 };
  }

  return {
    enter(state) {
      elapsed = 0;
      entryTime = 0;
      opacity.snap(0);
      opacity.set(1);
      dualsIgnited = false;

      // Pre-compute bar heights (instant, carried forward from Scene 6)
      const maxT = maxTotal();
      const maxBarH = 155;
      for (let i = 0; i < 10; i++) {
        const scale = maxBarH / maxT;
        energyHeights[i] = ENERGY_VALUES[i] * scale;
        reserveHeights[i] = RESERVE_VALUES[i] * scale;
        dualAnimValues[i] = 0;
        dualTargets[i] = DUAL_VALUES[i];
      }
    },

    exit(state) {},

    update(dt, state) {
      elapsed += dt;
      entryTime += dt;
      opacity.update(dt);

      // Ignite duals after 0.5s delay
      if (entryTime > 0.5 && !dualsIgnited) {
        dualsIgnited = true;
      }

      // Animate duals from 0 to target
      if (dualsIgnited) {
        const igniteT = Math.min(1, (entryTime - 0.5) / 1.0);
        const ease = easeOutCubic(igniteT);
        for (let i = 0; i < 10; i++) {
          dualAnimValues[i] = dualTargets[i] * ease;
        }
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      const center = getEllipseCenter(width, height);
      const { startX, baselineY, totalW } = getBarArea(width, height);

      // --- 1. Ellipse (slightly dimmed) ---
      Renderer.drawEllipse(ctx, center.x, center.y, ellipseL, ellipseScale, {
        fillColor: 'rgba(26, 122, 109, 0.04)',
        strokeColor: COLORS.teal,
        lineWidth: 1.5,
        alpha: 0.5,
      });

      // --- 2. Exposure vectors (subtle) ---
      for (let ei = 0; ei < EXPOSURE_ZONES.length; ei++) {
        const dir = EXPOSURE_DIRS[ei];
        const sp = supportPoint(ellipseL, dir);
        const spScreen = {
          x: center.x + sp.x * ellipseScale,
          y: center.y + sp.y * ellipseScale,
        };
        const arrowLen = 55;
        const fromX = spScreen.x + dir[0] * arrowLen;
        const fromY = spScreen.y + dir[1] * arrowLen;

        Renderer.drawLine(ctx, fromX, fromY, spScreen.x, spScreen.y, {
          color: COLORS.teal,
          lineWidth: 1,
          alpha: 0.2,
        });
      }

      // --- 3. Baseline ---
      Renderer.drawLine(ctx, startX - 10, baselineY, startX + totalW + 10, baselineY, {
        color: COLORS.ink,
        lineWidth: 1,
        alpha: 0.25,
      });

      // --- 4. Stacked bars with shadow-price glow ---
      for (let i = 0; i < 10; i++) {
        const bx = startX + i * (BAR_WIDTH + BAR_GAP);
        const eH = energyHeights[i];
        const rH = reserveHeights[i];
        const dualVal = dualAnimValues[i];
        const dualNorm = dualVal / MAX_DUAL;

        // Glow behind bar for high-dual zones
        if (dualNorm > 0.01) {
          const pulseFactor = 0.8 + 0.2 * Math.sin(elapsed * (2 * Math.PI / 3) + i * 0.8);
          const glowIntensity = dualNorm * pulseFactor;
          const glowCenterX = bx + BAR_WIDTH / 2;
          const glowCenterY = baselineY - (eH + rH) / 2;
          const glowRadius = 30 + dualNorm * 25;

          Renderer.drawGlow(ctx, glowCenterX, glowCenterY, glowRadius, COLORS.ember, glowIntensity * 0.5);
        }

        // Energy portion (teal)
        if (eH > 0.5) {
          Renderer.drawBar(ctx, bx, baselineY, BAR_WIDTH, eH, {
            color: COLORS.teal,
            alpha: 0.55,
            radius: rH > 0.5 ? 0 : 3,
          });
        }

        // Reserve portion (ember) with glow for constrained zones
        if (rH > 0.5) {
          const reserveBaseY = baselineY - eH;
          const glowColor = dualNorm > 0.3 ? COLORS.ember : null;
          const glowI = dualNorm > 0.3 ? dualNorm * (0.8 + 0.2 * Math.sin(elapsed * 2.1 + i)) : 0;

          Renderer.drawBar(ctx, bx, reserveBaseY, BAR_WIDTH, rH, {
            color: COLORS.ember,
            alpha: 0.75,
            radius: 3,
            glowColor: glowColor,
            glowIntensity: glowI,
          });

          // Divider
          ctx.beginPath();
          ctx.moveTo(bx, reserveBaseY);
          ctx.lineTo(bx + BAR_WIDTH, reserveBaseY);
          ctx.strokeStyle = 'rgba(250, 246, 240, 0.6)';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // --- 5. Pressure gauge arcs for constrained zones ---
        if (dualNorm > 0.05) {
          const arcCenterX = bx + BAR_WIDTH / 2;
          const arcCenterY = baselineY - eH - rH - 15;
          const arcRadius = 18;
          const startAngle = -Math.PI;
          const sweepAngle = Math.PI * dualNorm; // proportional to dual
          const pulseFactor = 0.85 + 0.15 * Math.sin(elapsed * (2 * Math.PI / 3) + i * 0.8);
          const arcAlpha = dualNorm * pulseFactor * 0.8;

          ctx.save();
          ctx.beginPath();
          ctx.arc(arcCenterX, arcCenterY, arcRadius, startAngle, startAngle + sweepAngle);
          ctx.strokeStyle = `rgba(232, 118, 58, ${arcAlpha})`;
          ctx.lineWidth = 3;
          ctx.lineCap = 'round';
          ctx.stroke();

          // Background arc track
          ctx.beginPath();
          ctx.arc(arcCenterX, arcCenterY, arcRadius, startAngle, 0);
          ctx.strokeStyle = `rgba(45, 45, 45, 0.08)`;
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.restore();

          // Mu label
          const muText = `\u03BC = ${dualVal.toFixed(1)}`;
          Renderer.drawText(ctx, muText, arcCenterX, arcCenterY - arcRadius - 6, {
            font: '10px Inter, sans-serif',
            color: COLORS.ember,
            align: 'center',
            baseline: 'bottom',
            alpha: arcAlpha,
          });
        }

        // Zone labels
        Renderer.drawText(ctx, `Z${i + 1}`, bx + BAR_WIDTH / 2, baselineY + 8, {
          font: '11px Inter, sans-serif',
          color: COLORS.ink,
          align: 'center',
          baseline: 'top',
          alpha: 0.55,
        });
      }

      // --- 6. Mini zone map with glow ---
      {
        const mm = getMiniMapRect(width, height);
        ctx.save();
        ctx.globalAlpha = alpha * 0.55;

        // Connections
        const drawnEdges = new Set();
        for (let i = 0; i < 10; i++) {
          for (const j of ZONE_ADJACENCY[i]) {
            const key = Math.min(i, j) + '-' + Math.max(i, j);
            if (drawnEdges.has(key)) continue;
            drawnEdges.add(key);
            const p1 = ZONE_POSITIONS[i];
            const p2 = ZONE_POSITIONS[j];
            ctx.beginPath();
            ctx.moveTo(mm.x + p1.x * mm.w, mm.y + p1.y * mm.h);
            ctx.lineTo(mm.x + p2.x * mm.w, mm.y + p2.y * mm.h);
            ctx.strokeStyle = 'rgba(45, 45, 45, 0.1)';
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }

        // Zone dots with glow for constrained zones
        for (let i = 0; i < 10; i++) {
          const p = ZONE_POSITIONS[i];
          const px = mm.x + p.x * mm.w;
          const py = mm.y + p.y * mm.h;
          const dualNorm = dualAnimValues[i] / MAX_DUAL;

          // Glow for constrained zones
          if (dualNorm > 0.05) {
            const pulse = 0.8 + 0.2 * Math.sin(elapsed * 2.1 + i * 0.8);
            Renderer.drawGlow(ctx, px, py, 15 + dualNorm * 10, COLORS.ember, dualNorm * pulse * 0.7);
          }

          ctx.beginPath();
          ctx.arc(px, py, dualNorm > 0.05 ? 5 : 4, 0, Math.PI * 2);
          ctx.fillStyle = dualNorm > 0.05
            ? `rgba(232, 118, 58, ${0.5 + dualNorm * 0.5})`
            : `rgba(26, 122, 109, 0.4)`;
          ctx.fill();

          // Zone label
          ctx.font = '8px Inter, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillStyle = `rgba(45, 45, 45, 0.5)`;
          ctx.fillText(`Z${i + 1}`, px, py + 7);
        }

        ctx.restore();
      }

      // --- 7. Cost counter ---
      Renderer.drawText(ctx, 'Total Cost', width - 40, 40, {
        font: '12px Inter, sans-serif',
        color: COLORS.inkLight,
        align: 'right',
        baseline: 'bottom',
        alpha: 0.6,
      });

      Renderer.drawText(ctx, `$${TOTAL_COST.toLocaleString()}/hr`, width - 40, 58, {
        font: 'bold 22px Inter, sans-serif',
        color: COLORS.ink,
        align: 'right',
        baseline: 'bottom',
        alpha: 1,
      });

      // --- 8. Title text ---
      if (dualsIgnited) {
        const titleT = Math.min(1, (entryTime - 1.5) * 1.5);
        if (titleT > 0) {
          Renderer.drawText(ctx, 'Binding constraints create pressure', width * 0.5, height * 0.58, {
            font: 'italic 14px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'center',
            baseline: 'middle',
            alpha: titleT * 0.5,
          });
        }
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // No interaction for scene 7
    },
  };
}
