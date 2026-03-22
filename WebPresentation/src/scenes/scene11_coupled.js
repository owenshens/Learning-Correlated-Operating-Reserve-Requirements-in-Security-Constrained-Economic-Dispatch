// === Scene 11: Coupled Transfer Pressure ===
// Shows the full layout (ellipse + bars + zone map) with transfer corridors
// as thick walls between zone groups. Tight zones glow coral.
// Animated decoupled -> coupled toggle.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeInOutCubic } from '../engine/timeline.js';
import { supportPoint } from '../math/ellipse.js';

// --- Data ---
const DEFAULT_L = [[1.8, 0], [0.6, 1.3]];

const RESERVE_VALUES_DECOUPLED = [42.79, 39.97, 55.58, 60.98, 99.01, 27.44, 201.34, 158.62, 126.60, 143.63];
const RESERVE_VALUES_COUPLED =   [52.64, 49.18, 55.55, 60.95, 86.30, 23.92, 203.60, 160.40, 133.44, 151.39];
const ENERGY_VALUES = [400, 350, 500, 300, 600, 200, 420, 550, 380, 450];

const COST_DECOUPLED = 95471;
const COST_COUPLED = 95683;
const RESERVE_COST_DECOUPLED = 4805;
const RESERVE_COST_COUPLED = 4972;

// Dual values (mu for reserve, lambda for transfer)
const MU_DUALS = [0, 0, 0, 0, 7.38, 0, 0, 0, 0, 0];
const LAMBDA_DUALS_COUPLED = [0, 0, 0, 0, 3.2, 0, 0, 1.8, 0, 2.5];

// Tight zones (0-indexed: 4, 7, 9)
const TIGHT_ZONES = [4, 7, 9];

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

// Transfer corridors: edges between zone groups that have transfer limits
// These connect zones that cross region boundaries
const TRANSFER_CORRIDORS = [
  { from: 0, to: 5, pressure: 0.3 },
  { from: 1, to: 6, pressure: 0.5 },
  { from: 2, to: 7, pressure: 0.9 },
  { from: 3, to: 8, pressure: 0.8 },
  { from: 4, to: 9, pressure: 1.0 },
];

const EXPOSURE_ZONES = [0, 2, 4, 7];
const EXPOSURE_DIRS = {
  0: [0.85, -0.53],
  2: [-0.42, -0.91],
  4: [0.71, 0.71],
  7: [-0.87, 0.50],
};

const BAR_WIDTH = 28;
const BAR_GAP = 12;

export function createScene11() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let coupledProgress = new AnimatedValue(0); // 0 = decoupled, 1 = coupled
  let wallFadeIn = new AnimatedValue(0);
  let entryTime = 0;
  let wallsTriggered = false;

  function getEllipseCenter(width, height) {
    return { x: width * 0.5, y: height * 0.35 };
  }

  function getBarArea(width, height) {
    const totalW = 10 * BAR_WIDTH + 9 * BAR_GAP;
    const startX = (width - totalW) / 2;
    const baselineY = height * 0.82;
    return { startX, baselineY, totalW };
  }

  function getMiniMapRect(width, height) {
    return { x: 25, y: 25, w: 180, h: 130 };
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function getCurrentReserves(t) {
    return RESERVE_VALUES_DECOUPLED.map((v, i) =>
      lerp(v, RESERVE_VALUES_COUPLED[i], t)
    );
  }

  function maxTotal() {
    let m = 0;
    for (let i = 0; i < 10; i++) {
      const t = ENERGY_VALUES[i] + Math.max(RESERVE_VALUES_DECOUPLED[i], RESERVE_VALUES_COUPLED[i]);
      if (t > m) m = t;
    }
    return m;
  }

  return {
    enter(state) {
      elapsed = 0;
      entryTime = 0;
      opacity.snap(0);
      opacity.set(1);
      coupledProgress.snap(state.coupled ? 1 : 0);
      wallFadeIn.snap(0);
      wallsTriggered = false;
    },

    exit(state) {},

    update(dt, state) {
      elapsed += dt;
      entryTime += dt;
      opacity.update(dt);
      coupledProgress.update(dt);
      wallFadeIn.update(dt);

      // Animate walls appearing after 1.5s
      if (!wallsTriggered && entryTime > 1.5) {
        wallsTriggered = true;
        wallFadeIn.set(1);
        coupledProgress.set(1);
      }

      // Respond to state.coupled toggle
      if (state.coupled && coupledProgress.target < 0.5) {
        coupledProgress.set(1);
        wallFadeIn.set(1);
      } else if (!state.coupled && coupledProgress.target > 0.5 && wallsTriggered) {
        coupledProgress.set(0);
        wallFadeIn.set(0);
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      const cT = coupledProgress.get();
      const wallAlpha = wallFadeIn.get();

      ctx.save();
      ctx.globalAlpha = alpha;

      const center = getEllipseCenter(width, height);
      const { startX, baselineY, totalW } = getBarArea(width, height);
      const ellipseScale = 110;
      const maxT = maxTotal();
      const maxBarH = 140;

      // ==============================
      // LAYER 1: Mini zone map with transfer walls
      // ==============================
      {
        const mm = getMiniMapRect(width, height);

        ctx.save();
        ctx.globalAlpha = alpha * 0.5;

        // Draw edges
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

        // Transfer corridor walls
        if (wallAlpha > 0.01) {
          for (const corridor of TRANSFER_CORRIDORS) {
            const p1 = ZONE_POSITIONS[corridor.from];
            const p2 = ZONE_POSITIONS[corridor.to];
            const mx = (mm.x + p1.x * mm.w + mm.x + p2.x * mm.w) / 2;
            const my = (mm.y + p1.y * mm.h + mm.y + p2.y * mm.h) / 2;
            const dx = p2.x * mm.w - p1.x * mm.w;
            const dy = p2.y * mm.h - p1.y * mm.h;
            const len = Math.sqrt(dx * dx + dy * dy);
            // Perpendicular direction for the wall
            const nx = -dy / len;
            const ny = dx / len;
            const wallLen = 12 * wallAlpha;

            ctx.beginPath();
            ctx.moveTo(mx - nx * wallLen, my - ny * wallLen);
            ctx.lineTo(mx + nx * wallLen, my + ny * wallLen);
            ctx.strokeStyle = `rgba(217, 79, 79, ${wallAlpha * corridor.pressure * 0.8})`;
            ctx.lineWidth = 2 + corridor.pressure * 2;
            ctx.lineCap = 'round';
            ctx.stroke();
          }
        }

        // Zone dots
        for (let i = 0; i < 10; i++) {
          const p = ZONE_POSITIONS[i];
          const px = mm.x + p.x * mm.w;
          const py = mm.y + p.y * mm.h;
          const isTight = TIGHT_ZONES.includes(i);

          if (isTight && wallAlpha > 0.01) {
            const pulse = 0.8 + 0.2 * Math.sin(elapsed * 2.1 + i * 0.7);
            Renderer.drawGlow(ctx, px, py, 12 + wallAlpha * 8, COLORS.coral, wallAlpha * pulse * 0.6);
          }

          ctx.beginPath();
          ctx.arc(px, py, isTight && wallAlpha > 0.5 ? 5 : 4, 0, Math.PI * 2);
          ctx.fillStyle = isTight && wallAlpha > 0.5
            ? `rgba(217, 79, 79, ${0.5 + wallAlpha * 0.5})`
            : 'rgba(26, 122, 109, 0.4)';
          ctx.fill();
        }

        ctx.restore();
      }

      // ==============================
      // LAYER 2: Ellipse
      // ==============================
      Renderer.drawEllipse(ctx, center.x, center.y, DEFAULT_L, ellipseScale, {
        fillColor: 'rgba(26, 122, 109, 0.06)',
        strokeColor: COLORS.teal,
        lineWidth: 2,
        alpha: 0.8,
      });

      // ==============================
      // LAYER 3: Exposure vectors
      // ==============================
      for (const zi of EXPOSURE_ZONES) {
        const dir = EXPOSURE_DIRS[zi];
        const sp = supportPoint(DEFAULT_L, dir);
        const spScreen = {
          x: center.x + sp.x * ellipseScale,
          y: center.y + sp.y * ellipseScale,
        };
        const arrowLen = 45;
        const fromX = spScreen.x + dir[0] * arrowLen;
        const fromY = spScreen.y + dir[1] * arrowLen;

        Renderer.drawLine(ctx, fromX, fromY, spScreen.x, spScreen.y, {
          color: COLORS.teal,
          lineWidth: 1,
          alpha: 0.2,
        });

        ctx.beginPath();
        ctx.arc(spScreen.x, spScreen.y, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(26, 122, 109, 0.4)`;
        ctx.fill();
      }

      // ==============================
      // LAYER 4: Transfer walls on main view
      // ==============================
      if (wallAlpha > 0.01) {
        for (const corridor of TRANSFER_CORRIDORS) {
          const margin = 80;
          const usableW = width - margin * 2;
          const usableH = height - margin * 2;
          const p1 = ZONE_POSITIONS[corridor.from];
          const p2 = ZONE_POSITIONS[corridor.to];
          const x1 = margin + p1.x * usableW;
          const y1 = margin + p1.y * usableH;
          const x2 = margin + p2.x * usableW;
          const y2 = margin + p2.y * usableH;

          const mx = (x1 + x2) / 2;
          const my = (y1 + y2) / 2;
          const dx = x2 - x1;
          const dy = y2 - y1;
          const len = Math.sqrt(dx * dx + dy * dy);
          const nx = -dy / len;
          const ny = dx / len;
          const wallLen = 18 * wallAlpha;

          // Draw wall
          ctx.save();
          ctx.globalAlpha = alpha * wallAlpha * corridor.pressure * 0.35;
          ctx.beginPath();
          ctx.moveTo(mx - nx * wallLen, my - ny * wallLen);
          ctx.lineTo(mx + nx * wallLen, my + ny * wallLen);
          ctx.strokeStyle = COLORS.coral;
          ctx.lineWidth = 3 + corridor.pressure * 3;
          ctx.lineCap = 'round';
          ctx.stroke();

          // Glow
          if (corridor.pressure > 0.5) {
            Renderer.drawGlow(ctx, mx, my, 15 + corridor.pressure * 10, COLORS.coral, wallAlpha * corridor.pressure * 0.3);
          }
          ctx.restore();
        }
      }

      // ==============================
      // LAYER 5: Reserve bars
      // ==============================
      const reserves = getCurrentReserves(cT);

      // Baseline
      Renderer.drawLine(ctx, startX - 10, baselineY, startX + totalW + 10, baselineY, {
        color: COLORS.ink, lineWidth: 1, alpha: 0.25,
      });

      for (let i = 0; i < 10; i++) {
        const bx = startX + i * (BAR_WIDTH + BAR_GAP);
        const scale = maxBarH / maxT;
        const eH = ENERGY_VALUES[i] * scale;
        const rH = reserves[i] * scale;
        const isTight = TIGHT_ZONES.includes(i);

        // Tight zone glow
        if (isTight && wallAlpha > 0.01) {
          const pulse = 0.7 + 0.3 * Math.sin(elapsed * 2 + i * 0.8);
          const glowCx = bx + BAR_WIDTH / 2;
          const glowCy = baselineY - (eH + rH) / 2;
          Renderer.drawGlow(ctx, glowCx, glowCy, 25, COLORS.coral, wallAlpha * pulse * 0.4);
        }

        // Energy bar
        if (eH > 0.5) {
          Renderer.drawBar(ctx, bx, baselineY, BAR_WIDTH, eH, {
            color: COLORS.teal,
            alpha: 0.55,
            radius: rH > 0.5 ? 0 : 3,
          });
        }

        // Reserve bar
        if (rH > 0.5) {
          const reserveBaseY = baselineY - eH;
          Renderer.drawBar(ctx, bx, reserveBaseY, BAR_WIDTH, rH, {
            color: isTight && wallAlpha > 0.3 ? COLORS.coral : COLORS.ember,
            alpha: 0.75,
            radius: 3,
            glowColor: isTight && wallAlpha > 0.3 ? COLORS.coral : null,
            glowIntensity: isTight ? wallAlpha * 0.5 : 0,
          });

          // Divider
          ctx.beginPath();
          ctx.moveTo(bx, reserveBaseY);
          ctx.lineTo(bx + BAR_WIDTH, reserveBaseY);
          ctx.strokeStyle = 'rgba(250, 246, 240, 0.6)';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Mu duals
        if (MU_DUALS[i] > 0.01) {
          const labelY = baselineY - eH - rH - 12;
          Renderer.drawText(ctx, `\u03BC=${MU_DUALS[i].toFixed(1)}`, bx + BAR_WIDTH / 2, labelY, {
            font: '9px Inter, sans-serif',
            color: COLORS.ember,
            align: 'center',
            baseline: 'bottom',
            alpha: 0.7,
          });
        }

        // Lambda duals (only when coupled)
        if (wallAlpha > 0.1 && LAMBDA_DUALS_COUPLED[i] > 0.01) {
          const labelY = baselineY - eH - rH - (MU_DUALS[i] > 0 ? 24 : 12);
          Renderer.drawText(ctx, `\u03BB=${LAMBDA_DUALS_COUPLED[i].toFixed(1)}`, bx + BAR_WIDTH / 2, labelY, {
            font: '9px Inter, sans-serif',
            color: COLORS.coral,
            align: 'center',
            baseline: 'bottom',
            alpha: wallAlpha * 0.7,
          });
        }

        // Zone labels
        Renderer.drawText(ctx, `Z${i + 1}`, bx + BAR_WIDTH / 2, baselineY + 8, {
          font: '11px Inter, sans-serif',
          color: COLORS.ink,
          align: 'center',
          baseline: 'top',
          alpha: 0.5,
        });
      }

      // ==============================
      // LAYER 6: Cost comparison
      // ==============================
      {
        const costY = height * 0.05;
        const currentCost = Math.round(lerp(COST_DECOUPLED, COST_COUPLED, cT));
        const currentReserveCost = Math.round(lerp(RESERVE_COST_DECOUPLED, RESERVE_COST_COUPLED, cT));

        const label = cT > 0.5 ? 'Coupled' : 'Decoupled';
        const labelColor = cT > 0.5 ? COLORS.coral : COLORS.teal;

        Renderer.drawText(ctx, label, width - 40, costY, {
          font: '11px Inter, sans-serif',
          color: labelColor,
          align: 'right',
          baseline: 'top',
          alpha: 0.6,
        });

        Renderer.drawText(ctx, `$${currentCost.toLocaleString()}/hr`, width - 40, costY + 16, {
          font: 'bold 20px Inter, sans-serif',
          color: COLORS.ink,
          align: 'right',
          baseline: 'top',
          alpha: 0.9,
        });

        Renderer.drawText(ctx, `Reserve: $${currentReserveCost.toLocaleString()}`, width - 40, costY + 40, {
          font: '12px Inter, sans-serif',
          color: COLORS.inkLight,
          align: 'right',
          baseline: 'top',
          alpha: 0.55,
        });
      }

      // ==============================
      // LAYER 7: Legend
      // ==============================
      if (wallAlpha > 0.1) {
        const legendX = width - 40;
        const legendY = height * 0.55;

        // mu legend
        ctx.save();
        ctx.globalAlpha = alpha * 0.6;
        ctx.fillStyle = COLORS.ember;
        ctx.beginPath();
        ctx.arc(legendX - 50, legendY, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        Renderer.drawText(ctx, '\u03BC  reserve dual', legendX - 40, legendY, {
          font: '10px Inter, sans-serif',
          color: COLORS.ember,
          align: 'left',
          baseline: 'middle',
          alpha: 0.5,
        });

        // lambda legend
        ctx.save();
        ctx.globalAlpha = alpha * wallAlpha * 0.6;
        ctx.fillStyle = COLORS.coral;
        ctx.beginPath();
        ctx.arc(legendX - 50, legendY + 18, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        Renderer.drawText(ctx, '\u03BB  transfer dual', legendX - 40, legendY + 18, {
          font: '10px Inter, sans-serif',
          color: COLORS.coral,
          align: 'left',
          baseline: 'middle',
          alpha: wallAlpha * 0.5,
        });
      }

      // ==============================
      // LAYER 8: Toggle hint
      // ==============================
      {
        const hintAlpha = 0.25 + 0.1 * Math.sin(elapsed * 2);
        Renderer.drawText(ctx, 'Toggle "Coupled" to compare', width / 2, height * 0.96, {
          font: '11px Inter, sans-serif',
          color: COLORS.inkLight,
          align: 'center',
          baseline: 'middle',
          alpha: hintAlpha,
        });
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // Toggle coupled on click
      if (event.type === 'click') {
        state.coupled = !state.coupled;
        if (state.coupled) {
          coupledProgress.set(1);
          wallFadeIn.set(1);
        } else {
          coupledProgress.set(0);
          wallFadeIn.set(0);
        }
      }
    },
  };
}
