// === Scene 06: Dispatch Adjusts ===
// Reserve bars stay visible. Each bar now has two segments:
// Bottom = energy (teal), Top = reserve (ember).
// A cost counter animates upward in the upper right.
// Zone map shown small in upper-left as context.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeOutCubic } from '../engine/timeline.js';
import { supportPoint } from '../math/ellipse.js';

// --- Data ---

const RESERVE_VALUES = [80, 65, 140, 55, 180, 45, 90, 160, 70, 120];
const ENERGY_VALUES  = [400, 350, 500, 300, 600, 200, 420, 550, 380, 450];
const TOTAL_COST = 95471;

// Same exposure configuration as Scene 5
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

// Mini zone-map data from zones.json
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

export function createScene06() {
  // --- Local state ---
  let elapsed = 0;
  let entryTime = 0;
  let opacity = new AnimatedValue(0);

  // Bar animation state
  let energyHeights = new Float64Array(10);
  let reserveHeights = new Float64Array(10);
  let energyTargets = new Float64Array(10);
  let reserveTargets = new Float64Array(10);
  let energyStartTimes = new Float64Array(10);
  let reserveStartTimes = new Float64Array(10);

  // Cost counter
  let costValue = new AnimatedValue(0);

  // Generator brightness animation
  let genBrightness = new Float64Array(10);

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
    return {
      x: 30,
      y: 30,
      w: 160,
      h: 110,
    };
  }

  return {
    enter(state) {
      elapsed = 0;
      entryTime = 0;
      opacity.snap(0);
      opacity.set(1);
      costValue.snap(0);

      // Compute bar targets
      const maxT = maxTotal();
      const maxBarH = 155;

      for (let i = 0; i < 10; i++) {
        const scale = maxBarH / maxT;
        energyTargets[i] = ENERGY_VALUES[i] * scale;
        reserveTargets[i] = RESERVE_VALUES[i] * scale;
        energyHeights[i] = 0;
        reserveHeights[i] = 0;
        // Energy fills first, then reserve
        energyStartTimes[i] = 0.2 + i * 0.05;
        reserveStartTimes[i] = 0.8 + i * 0.05;
        genBrightness[i] = 0;
      }
    },

    exit(state) {
      // no cleanup
    },

    update(dt, state) {
      elapsed += dt;
      entryTime += dt;
      opacity.update(dt);

      // Animate energy bars
      for (let i = 0; i < 10; i++) {
        // Energy portion
        if (entryTime >= energyStartTimes[i]) {
          const localT = Math.min(1, (entryTime - energyStartTimes[i]) / 0.6);
          energyHeights[i] = energyTargets[i] * easeOutCubic(localT);
          // Generator brightness ramps with energy fill
          genBrightness[i] = easeOutCubic(localT);
        }

        // Reserve portion
        if (entryTime >= reserveStartTimes[i]) {
          const localT = Math.min(1, (entryTime - reserveStartTimes[i]) / 0.6);
          reserveHeights[i] = reserveTargets[i] * easeOutCubic(localT);
        }
      }

      // Animate cost counter (starts at 0.5s, reaches target by 2.5s)
      if (entryTime > 0.5) {
        const costT = Math.min(1, (entryTime - 0.5) / 2.0);
        costValue.snap(TOTAL_COST * easeOutCubic(costT));
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      const center = getEllipseCenter(width, height);
      const { startX, baselineY, totalW } = getBarArea(width, height);

      // --- 1. Draw ellipse (slightly dimmed since focus is on bars) ---
      Renderer.drawEllipse(ctx, center.x, center.y, ellipseL, ellipseScale, {
        fillColor: 'rgba(26, 122, 109, 0.04)',
        strokeColor: COLORS.teal,
        lineWidth: 1.5,
        alpha: 0.6,
      });

      // --- 2. Draw exposure vectors (subtle) ---
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

      // --- 3. Draw baseline ---
      Renderer.drawLine(ctx, startX - 10, baselineY, startX + totalW + 10, baselineY, {
        color: COLORS.ink,
        lineWidth: 1,
        alpha: 0.25,
      });

      // --- 4. Draw stacked bars: energy (teal) + reserve (ember) ---
      for (let i = 0; i < 10; i++) {
        const bx = startX + i * (BAR_WIDTH + BAR_GAP);
        const eH = energyHeights[i];
        const rH = reserveHeights[i];
        const totalH = eH + rH;

        // Energy portion (bottom, teal)
        if (eH > 0.5) {
          Renderer.drawBar(ctx, bx, baselineY, BAR_WIDTH, eH, {
            color: COLORS.teal,
            alpha: 0.55,
            radius: rH > 0.5 ? 0 : 3, // No rounded top if reserve is stacked on top
          });
        }

        // Reserve portion (top, ember)
        if (rH > 0.5) {
          // Draw on top of energy
          const reserveBaseY = baselineY - eH;
          Renderer.drawBar(ctx, bx, reserveBaseY, BAR_WIDTH, rH, {
            color: COLORS.ember,
            alpha: 0.75,
            radius: 3,
          });

          // Divider line between energy and reserve
          ctx.beginPath();
          ctx.moveTo(bx, reserveBaseY);
          ctx.lineTo(bx + BAR_WIDTH, reserveBaseY);
          ctx.strokeStyle = 'rgba(250, 246, 240, 0.6)';
          ctx.lineWidth = 1;
          ctx.stroke();
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

      // --- 5. Legend ---
      const legendX = startX + totalW + 25;
      const legendY = baselineY - 80;

      if (entryTime > 1.2) {
        const legendAlpha = Math.min(1, (entryTime - 1.2) * 2);

        // Energy legend
        ctx.fillStyle = COLORS.teal;
        ctx.globalAlpha = alpha * legendAlpha * 0.55;
        ctx.fillRect(legendX, legendY, 12, 12);
        ctx.globalAlpha = alpha * legendAlpha;
        Renderer.drawText(ctx, 'Energy', legendX + 18, legendY + 6, {
          font: '11px Inter, sans-serif',
          color: COLORS.ink,
          align: 'left',
          baseline: 'middle',
          alpha: legendAlpha * 0.7,
        });

        // Reserve legend
        ctx.fillStyle = COLORS.ember;
        ctx.globalAlpha = alpha * legendAlpha * 0.75;
        ctx.fillRect(legendX, legendY + 20, 12, 12);
        ctx.globalAlpha = alpha * legendAlpha;
        Renderer.drawText(ctx, 'Reserve', legendX + 18, legendY + 26, {
          font: '11px Inter, sans-serif',
          color: COLORS.ink,
          align: 'left',
          baseline: 'middle',
          alpha: legendAlpha * 0.7,
        });
      }

      // --- 6. Cost counter in upper right ---
      if (entryTime > 0.5) {
        const costAlpha = Math.min(1, (entryTime - 0.5) * 2);
        const cost = Math.round(costValue.get());
        const costStr = `$${cost.toLocaleString()}/hr`;

        Renderer.drawText(ctx, 'Total Cost', width - 40, 40, {
          font: '12px Inter, sans-serif',
          color: COLORS.inkLight,
          align: 'right',
          baseline: 'bottom',
          alpha: costAlpha * 0.6,
        });

        Renderer.drawText(ctx, costStr, width - 40, 58, {
          font: 'bold 22px Inter, sans-serif',
          color: COLORS.ink,
          align: 'right',
          baseline: 'bottom',
          alpha: costAlpha,
        });
      }

      // --- 7. Mini zone map (upper-left context) ---
      if (entryTime > 0.3) {
        const mapAlpha = Math.min(1, (entryTime - 0.3) * 1.5) * 0.5;
        const mm = getMiniMapRect(width, height);

        ctx.save();
        ctx.globalAlpha = alpha * mapAlpha;

        // Draw mini connections
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

        // Draw mini zone dots
        for (let i = 0; i < 10; i++) {
          const p = ZONE_POSITIONS[i];
          const px = mm.x + p.x * mm.w;
          const py = mm.y + p.y * mm.h;
          const brightness = genBrightness[i];

          // Generator activity brightness
          const dotColor = brightness > 0.5
            ? `rgba(26, 122, 109, ${0.3 + brightness * 0.5})`
            : `rgba(139, 125, 107, ${0.3 + brightness * 0.2})`;

          ctx.beginPath();
          ctx.arc(px, py, 4 + brightness * 2, 0, Math.PI * 2);
          ctx.fillStyle = dotColor;
          ctx.fill();

          // Label
          ctx.font = '8px Inter, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillStyle = `rgba(45, 45, 45, 0.5)`;
          ctx.fillText(`Z${i + 1}`, px, py + 6);
        }

        ctx.restore();
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // No interaction for scene 6
    },
  };
}
