// === Scene 05: Reserve Requirements Materialize ===
// The ellipse stays visible. Below it, reserve bars rise from a baseline.
// Exposure vectors connect zones to the ellipse boundary.
// Each bar height is proportional to R_z = rho * ||L^T w_z||.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeOutCubic } from '../engine/timeline.js';
import { supportPoint } from '../math/ellipse.js';

// --- Constants ---

const RESERVE_VALUES = [80, 65, 140, 55, 180, 45, 90, 160, 70, 120];

// Exposure directions for the 4 visible zones (unit vectors, 2D projected)
// Zones 1, 3, 5, 8 (0-indexed: 0, 2, 4, 7)
const EXPOSURE_ZONES = [0, 2, 4, 7];
const EXPOSURE_DIRS = [
  [0.85, -0.53],   // Z1: upper-right tendency
  [-0.42, -0.91],  // Z3: upward-left
  [0.71, 0.71],    // Z5: lower-right
  [-0.87, 0.50],   // Z8: left-downward
];

// Default L matrix for ellipse (2x2 Cholesky factor)
const DEFAULT_L = [[1.8, 0], [0.6, 1.3]];

const BAR_WIDTH = 30;
const BAR_GAP = 15;

export function createScene05() {
  // --- Local state ---
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let barHeights = new Float64Array(10); // current animated heights
  let barTargets = new Float64Array(10);
  let barStartTimes = new Float64Array(10);
  let barsAnimating = false;
  let barsComplete = false;
  let entryTime = 0;

  // Ellipse state
  let ellipseL = DEFAULT_L;
  let ellipseScale = 120;

  // Pulse connections: animated dots from support points to bars
  let pulseParticles = [];
  const MAX_PULSES = 20;
  for (let i = 0; i < MAX_PULSES; i++) {
    pulseParticles.push({
      active: false,
      zoneIndex: -1,
      progress: 0,
      speed: 0,
      fromX: 0, fromY: 0,
      toX: 0, toY: 0,
    });
  }
  let pulseSpawnTimer = 0;

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

  function getBarRect(index, width, height) {
    const { startX, baselineY } = getBarArea(width, height);
    const x = startX + index * (BAR_WIDTH + BAR_GAP);
    const h = barHeights[index];
    return { x, y: baselineY - h, w: BAR_WIDTH, h, baselineY };
  }

  function getSupportPointScreen(dirIndex, width, height) {
    const center = getEllipseCenter(width, height);
    const dir = EXPOSURE_DIRS[dirIndex];
    const sp = supportPoint(ellipseL, dir);
    return {
      x: center.x + sp.x * ellipseScale,
      y: center.y + sp.y * ellipseScale,
    };
  }

  function maxReserve() {
    let m = 0;
    for (let i = 0; i < 10; i++) {
      if (RESERVE_VALUES[i] > m) m = RESERVE_VALUES[i];
    }
    return m;
  }

  function spawnPulse(zoneIndex, fromX, fromY, toX, toY) {
    for (let i = 0; i < MAX_PULSES; i++) {
      if (!pulseParticles[i].active) {
        pulseParticles[i].active = true;
        pulseParticles[i].zoneIndex = zoneIndex;
        pulseParticles[i].progress = 0;
        pulseParticles[i].speed = 0.6 + Math.random() * 0.4;
        pulseParticles[i].fromX = fromX;
        pulseParticles[i].fromY = fromY;
        pulseParticles[i].toX = toX;
        pulseParticles[i].toY = toY;
        return;
      }
    }
  }

  return {
    enter(state) {
      elapsed = 0;
      entryTime = 0;
      opacity.snap(0);
      opacity.set(1);
      barsAnimating = true;
      barsComplete = false;
      pulseSpawnTimer = 0;

      // Use method data if available
      if (state.data && state.data.staticl) {
        // We'll use the synthetic values for clearer visualization
      }

      // Set up bar targets (scaled to a max pixel height of ~140px)
      const maxR = maxReserve();
      const maxBarH = 140;
      for (let i = 0; i < 10; i++) {
        barHeights[i] = 0;
        barTargets[i] = (RESERVE_VALUES[i] / maxR) * maxBarH;
        // Stagger start: 100ms per zone
        barStartTimes[i] = 0.3 + i * 0.1;
      }
    },

    exit(state) {
      // no cleanup needed
    },

    update(dt, state) {
      elapsed += dt;
      entryTime += dt;
      opacity.update(dt);

      // Animate bars rising
      if (barsAnimating) {
        let allDone = true;
        for (let i = 0; i < 10; i++) {
          if (entryTime < barStartTimes[i]) {
            allDone = false;
            continue;
          }
          const localT = (entryTime - barStartTimes[i]) / 0.8; // 800ms animation
          if (localT >= 1) {
            barHeights[i] = barTargets[i];
          } else {
            allDone = false;
            barHeights[i] = barTargets[i] * easeOutCubic(localT);
          }
        }
        if (allDone) {
          barsAnimating = false;
          barsComplete = true;
        }
      }

      // Spawn pulse particles after bars have started rising
      if (entryTime > 1.0) {
        pulseSpawnTimer -= dt;
        if (pulseSpawnTimer <= 0) {
          pulseSpawnTimer = 1.2 + Math.random() * 0.5;
          // Pick a random exposure zone
          const idx = Math.floor(Math.random() * EXPOSURE_ZONES.length);
          const zi = EXPOSURE_ZONES[idx];
          // We'll compute positions in render since we need width/height
          // Store zone index, positions will be computed in render
          for (let j = 0; j < MAX_PULSES; j++) {
            if (!pulseParticles[j].active) {
              pulseParticles[j].active = true;
              pulseParticles[j].zoneIndex = zi;
              pulseParticles[j].progress = 0;
              pulseParticles[j].speed = 0.5 + Math.random() * 0.3;
              pulseParticles[j].needsPositionUpdate = true;
              break;
            }
          }
        }
      }

      // Update pulse particles
      for (let i = 0; i < MAX_PULSES; i++) {
        const p = pulseParticles[i];
        if (!p.active) continue;
        p.progress += p.speed * dt;
        if (p.progress >= 1) {
          p.active = false;
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

      // --- 1. Draw ellipse ---
      Renderer.drawEllipse(ctx, center.x, center.y, ellipseL, ellipseScale, {
        fillColor: 'rgba(26, 122, 109, 0.06)',
        strokeColor: COLORS.teal,
        lineWidth: 2,
        alpha: 1,
      });

      // Principal axes (subtle dashed)
      ctx.save();
      ctx.translate(center.x, center.y);
      // We just draw the L-transformed axes
      const axisLen = ellipseScale;
      ctx.setLineDash([4, 6]);
      ctx.strokeStyle = 'rgba(26, 122, 109, 0.12)';
      ctx.lineWidth = 1;

      // Major axis direction from L
      ctx.beginPath();
      ctx.moveTo(-ellipseL[0][0] * axisLen / 1.8, -ellipseL[1][0] * axisLen / 1.8);
      ctx.lineTo(ellipseL[0][0] * axisLen / 1.8, ellipseL[1][0] * axisLen / 1.8);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-ellipseL[0][1] * axisLen / 1.3, -ellipseL[1][1] * axisLen / 1.3);
      ctx.lineTo(ellipseL[0][1] * axisLen / 1.3, ellipseL[1][1] * axisLen / 1.3);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.restore();

      // --- 2. Draw exposure vectors (3-4 zones) ---
      for (let ei = 0; ei < EXPOSURE_ZONES.length; ei++) {
        const zi = EXPOSURE_ZONES[ei];
        const dir = EXPOSURE_DIRS[ei];
        const sp = supportPoint(ellipseL, dir);

        const spScreen = {
          x: center.x + sp.x * ellipseScale,
          y: center.y + sp.y * ellipseScale,
        };

        // Arrow from outside toward support point
        const arrowLen = 70;
        const fromX = spScreen.x + dir[0] * arrowLen;
        const fromY = spScreen.y + dir[1] * arrowLen;

        // Draw the vector line
        ctx.beginPath();
        ctx.moveTo(fromX, fromY);
        ctx.lineTo(spScreen.x, spScreen.y);
        ctx.strokeStyle = `rgba(26, 122, 109, 0.35)`;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Support point dot
        const pulseFactor = 0.6 + 0.4 * Math.sin(elapsed * 3 + ei * 1.5);
        ctx.beginPath();
        ctx.arc(spScreen.x, spScreen.y, 3 + pulseFactor, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(26, 122, 109, ${0.5 + pulseFactor * 0.3})`;
        ctx.fill();

        // Zone label near arrow start
        Renderer.drawText(ctx, `Z${zi + 1}`, fromX + dir[0] * 12, fromY + dir[1] * 12, {
          font: 'bold 11px Inter, sans-serif',
          color: COLORS.teal,
          align: 'center',
          baseline: 'middle',
          alpha: 0.7,
        });
      }

      // --- 3. Draw baseline ---
      ctx.beginPath();
      ctx.moveTo(startX - 10, baselineY);
      ctx.lineTo(startX + totalW + 10, baselineY);
      ctx.strokeStyle = COLORS.ink;
      ctx.lineWidth = 1;
      ctx.globalAlpha = alpha * 0.25;
      ctx.stroke();
      ctx.globalAlpha = alpha;

      // --- 4. Draw reserve bars ---
      const maxR = maxReserve();
      for (let i = 0; i < 10; i++) {
        const bx = startX + i * (BAR_WIDTH + BAR_GAP);
        const bh = barHeights[i];
        const by = baselineY - bh;

        if (bh > 0.5) {
          // Bar color: ember orange with opacity based on relative size
          const relSize = RESERVE_VALUES[i] / maxR;
          const barAlpha = 0.5 + relSize * 0.4;

          // Determine if this is an "expensive" zone (3, 5, 8 -> indices 2, 4, 7)
          const isExpensive = (i === 2 || i === 4 || i === 7);

          if (isExpensive) {
            // Slightly brighter for expensive zones
            Renderer.drawBar(ctx, bx, baselineY, BAR_WIDTH, bh, {
              color: COLORS.ember,
              alpha: barAlpha + 0.1,
              radius: 3,
            });
          } else {
            Renderer.drawBar(ctx, bx, baselineY, BAR_WIDTH, bh, {
              color: COLORS.ember,
              alpha: barAlpha,
              radius: 3,
            });
          }

          // Reserve value label above tall bars
          if (isExpensive && barsComplete) {
            Renderer.drawText(ctx, RESERVE_VALUES[i].toString(), bx + BAR_WIDTH / 2, by - 8, {
              font: '10px Inter, sans-serif',
              color: COLORS.ember,
              align: 'center',
              baseline: 'bottom',
              alpha: 0.75,
            });
          }
        }

        // Zone labels below bars
        Renderer.drawText(ctx, `Z${i + 1}`, bx + BAR_WIDTH / 2, baselineY + 8, {
          font: '11px Inter, sans-serif',
          color: COLORS.ink,
          align: 'center',
          baseline: 'top',
          alpha: 0.55,
        });
      }

      // --- 5. Draw pulse connections (support point -> bar) ---
      for (let pi = 0; pi < MAX_PULSES; pi++) {
        const p = pulseParticles[pi];
        if (!p.active) continue;

        // Compute positions if needed
        const zi = p.zoneIndex;
        const eiIdx = EXPOSURE_ZONES.indexOf(zi);
        if (eiIdx < 0) { p.active = false; continue; }

        const dir = EXPOSURE_DIRS[eiIdx];
        const sp = supportPoint(ellipseL, dir);
        const spScreen = {
          x: center.x + sp.x * ellipseScale,
          y: center.y + sp.y * ellipseScale,
        };

        const barX = startX + zi * (BAR_WIDTH + BAR_GAP) + BAR_WIDTH / 2;
        const barY = baselineY - barHeights[zi];

        // Interpolate position along curved path from support point to bar top
        const t = p.progress;
        const ctrl1X = spScreen.x;
        const ctrl1Y = spScreen.y + (barY - spScreen.y) * 0.3;
        const ctrl2X = barX;
        const ctrl2Y = barY - 30;

        // Cubic bezier interpolation
        const mt = 1 - t;
        const px = mt * mt * mt * spScreen.x + 3 * mt * mt * t * ctrl1X + 3 * mt * t * t * ctrl2X + t * t * t * barX;
        const py = mt * mt * mt * spScreen.y + 3 * mt * mt * t * ctrl1Y + 3 * mt * t * t * ctrl2Y + t * t * t * barY;

        const particleAlpha = t < 0.1 ? t / 0.1 : t > 0.85 ? (1 - t) / 0.15 : 1;
        Renderer.drawParticle(ctx, px, py, 2.5, COLORS.ember, particleAlpha * 0.6);
      }

      // --- 6. Title hint ---
      if (barsComplete) {
        const titleAlpha = Math.min(1, (entryTime - 1.8) * 2);
        if (titleAlpha > 0) {
          Renderer.drawText(ctx, 'R_z = \u03C1 \u00B7 ||L\u1D40 w_z||', width * 0.5, height * 0.58, {
            font: 'italic 14px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'center',
            baseline: 'middle',
            alpha: titleAlpha * 0.6,
          });
        }
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // No special interaction for scene 5
    },
  };
}
