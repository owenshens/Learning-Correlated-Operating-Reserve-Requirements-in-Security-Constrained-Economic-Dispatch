// === Scene 08: The Gradient Flows Backward ===
// SIGNATURE SCENE. Everything from Scene 7 visible. After a brief pause,
// ember particles stream BACKWARD from glowing zone bars, up along exposure
// vectors, to the ellipse boundary. Ripples spread on impact, and the
// ellipse deforms under gradient pressure.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeOutCubic, easeInOutCubic } from '../engine/timeline.js';
import { supportPoint } from '../math/ellipse.js';

// --- Data ---

const RESERVE_VALUES = [80, 65, 140, 55, 180, 45, 90, 160, 70, 120];
const ENERGY_VALUES  = [400, 350, 500, 300, 600, 200, 420, 550, 380, 450];
const TOTAL_COST = 95471;

const DUAL_VALUES = [0, 0, 3.2, 0, 4.8, 0, 0.5, 4.1, 0, 2.0];
const MAX_DUAL = 4.8;

// Zones with flow paths: 3, 5, 8 (0-indexed: 2, 4, 7)
const FLOW_ZONES = [2, 4, 7];
const FLOW_DUALS = [3.2, 4.8, 4.1];

// Exposure directions for all relevant zones
const EXPOSURE_ZONES = [0, 2, 4, 7];
const EXPOSURE_DIRS_MAP = {
  0: [0.85, -0.53],
  2: [-0.42, -0.91],
  4: [0.71, 0.71],
  7: [-0.87, 0.50],
};

const DEFAULT_L = [[1.8, 0], [0.6, 1.3]];

// Deformed L after gradient pressure (more eccentric)
const DEFORMED_L = [[2.05, 0], [0.85, 1.05]];

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

// --- Bezier utilities ---

function bezierPoint(p0, c1, c2, p3, t) {
  const mt = 1 - t;
  return {
    x: mt * mt * mt * p0.x + 3 * mt * mt * t * c1.x + 3 * mt * t * t * c2.x + t * t * t * p3.x,
    y: mt * mt * mt * p0.y + 3 * mt * mt * t * c1.y + 3 * mt * t * t * c2.y + t * t * t * p3.y,
  };
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// --- Particle and Ripple pools ---

const MAX_PARTICLES = 80;
const TRAIL_LENGTH = 5;

function createParticle() {
  return {
    active: false,
    flowIndex: 0,      // which flow path (0, 1, 2)
    progress: 0,       // 0 = at bar, 1 = at ellipse
    speed: 0,
    alpha: 1,
    size: 3,
    trail: [],         // last N positions {x, y}
    brightness: 1,
  };
}

const MAX_RIPPLES = 15;

function createRipple() {
  return {
    active: false,
    x: 0, y: 0,
    radius: 0,
    maxRadius: 0,
    alpha: 0,
    // Arc segment for partial boundary ripple
    startAngle: 0,
    sweepAngle: 0,
  };
}

export function createScene08() {
  // --- Local state ---
  let elapsed = 0;
  let entryTime = 0;
  let opacity = new AnimatedValue(0);

  // Bar heights (pre-computed)
  let energyHeights = new Float64Array(10);
  let reserveHeights = new Float64Array(10);

  // Dual animation values
  let dualAnimValues = new Float64Array(10);

  // Ellipse state
  let currentL = DEFAULT_L.map(r => [...r]);
  let ellipseScale = 120;
  let deformationProgress = 0;
  let deforming = false;
  let deformStartTime = 0;

  // Pulse state
  let pulsePhase = 'waiting'; // 'waiting' | 'brightening' | 'flowing' | 'impacting' | 'deforming' | 'done'
  let pulseStartTime = 0;
  let pulseTriggered = false;
  let brightenIntensity = 0;

  // Flow paths (computed on enter based on layout)
  let flowPaths = []; // { from: {x,y}, ctrl1: {x,y}, ctrl2: {x,y}, to: {x,y} }

  // Particle pool
  let particles = [];
  for (let i = 0; i < MAX_PARTICLES; i++) {
    particles.push(createParticle());
  }

  // Ripple pool
  let ripples = [];
  for (let i = 0; i < MAX_RIPPLES; i++) {
    ripples.push(createRipple());
  }

  // Spawn control
  let spawnTimers = [0, 0, 0];
  let particlesLanded = 0;
  let flowStartTime = 0;
  let flowComplete = false;

  // Replay support
  let canReplay = false;

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

  function computeFlowPaths(width, height) {
    const center = getEllipseCenter(width, height);
    const { startX, baselineY } = getBarArea(width, height);

    flowPaths = [];
    for (let fi = 0; fi < FLOW_ZONES.length; fi++) {
      const zi = FLOW_ZONES[fi];
      const dir = EXPOSURE_DIRS_MAP[zi];
      const sp = supportPoint(currentL, dir);

      // Bar top position
      const bx = startX + zi * (BAR_WIDTH + BAR_GAP) + BAR_WIDTH / 2;
      const by = baselineY - energyHeights[zi] - reserveHeights[zi];

      // Support point on ellipse
      const sx = center.x + sp.x * ellipseScale;
      const sy = center.y + sp.y * ellipseScale;

      // Bezier control points for a graceful upward curve
      const ctrl1 = {
        x: bx,
        y: by - 60,
      };
      const ctrl2 = {
        x: sx + (bx > sx ? 30 : -30),
        y: sy + 40,
      };

      flowPaths.push({
        from: { x: bx, y: by },
        ctrl1,
        ctrl2,
        to: { x: sx, y: sy },
        zoneIndex: zi,
        dualValue: FLOW_DUALS[fi],
        dualNorm: FLOW_DUALS[fi] / MAX_DUAL,
      });
    }
  }

  function acquireParticle() {
    for (let i = 0; i < MAX_PARTICLES; i++) {
      if (!particles[i].active) return particles[i];
    }
    return null;
  }

  function spawnFlowParticle(flowIndex) {
    const p = acquireParticle();
    if (!p) return;
    p.active = true;
    p.flowIndex = flowIndex;
    p.progress = 0;
    // Faster at start, slower near ellipse: base speed with easing in progress handling
    p.speed = 0.55 + Math.random() * 0.25;
    p.alpha = 1;
    p.size = 2.5 + flowPaths[flowIndex].dualNorm * 1.5;
    p.brightness = 0.8 + flowPaths[flowIndex].dualNorm * 0.4;
    p.trail = [];
  }

  function spawnRipple(x, y, intensity) {
    for (let i = 0; i < MAX_RIPPLES; i++) {
      if (!ripples[i].active) {
        ripples[i].active = true;
        ripples[i].x = x;
        ripples[i].y = y;
        ripples[i].radius = 3;
        ripples[i].maxRadius = 25 + intensity * 20;
        ripples[i].alpha = 0.7 * intensity;
        ripples[i].startAngle = 0;
        ripples[i].sweepAngle = Math.PI / 3; // 60 degrees
        return;
      }
    }
  }

  function resetPulse() {
    pulsePhase = 'waiting';
    pulseTriggered = false;
    brightenIntensity = 0;
    deformationProgress = 0;
    deforming = false;
    flowComplete = false;
    particlesLanded = 0;
    canReplay = false;
    currentL = DEFAULT_L.map(r => [...r]);
    spawnTimers = [0, 0, 0];

    // Reset all particles and ripples
    for (let i = 0; i < MAX_PARTICLES; i++) {
      particles[i].active = false;
    }
    for (let i = 0; i < MAX_RIPPLES; i++) {
      ripples[i].active = false;
    }
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

      // Pre-compute bar heights
      const maxT = maxTotal();
      const maxBarH = 155;
      for (let i = 0; i < 10; i++) {
        const scale = maxBarH / maxT;
        energyHeights[i] = ENERGY_VALUES[i] * scale;
        reserveHeights[i] = RESERVE_VALUES[i] * scale;
        dualAnimValues[i] = DUAL_VALUES[i]; // Already ignited from Scene 7
      }

      currentL = DEFAULT_L.map(r => [...r]);
      resetPulse();
    },

    exit(state) {},

    update(dt, state) {
      elapsed += dt;
      entryTime += dt;
      opacity.update(dt);

      // --- Phase machine ---

      // Phase 1: Waiting (1s pause)
      if (pulsePhase === 'waiting' && entryTime > 1.0) {
        pulsePhase = 'brightening';
        pulseStartTime = entryTime;
      }

      // Phase 2: Brightening (glowing zones pulse brighter, 0.8s)
      if (pulsePhase === 'brightening') {
        const bT = Math.min(1, (entryTime - pulseStartTime) / 0.8);
        brightenIntensity = easeOutCubic(bT);
        if (bT >= 1) {
          pulsePhase = 'flowing';
          flowStartTime = entryTime;
          pulseTriggered = true;
        }
      }

      // Phase 3: Flowing (particles streaming backward, ~3s)
      if (pulsePhase === 'flowing' && flowPaths.length > 0) {
        const flowElapsed = entryTime - flowStartTime;

        // Spawn particles at intervals on each flow path
        for (let fi = 0; fi < FLOW_ZONES.length && fi < flowPaths.length; fi++) {
          spawnTimers[fi] -= dt;
          if (spawnTimers[fi] <= 0 && flowElapsed < 2.5) {
            const interval = 0.18 / flowPaths[fi].dualNorm; // faster spawn for higher duals
            spawnTimers[fi] = Math.max(0.12, interval * (0.7 + Math.random() * 0.6));
            spawnFlowParticle(fi);
          }
        }

        // Check if flow phase is complete (all particles done)
        if (flowElapsed > 3.5) {
          let anyActive = false;
          for (let i = 0; i < MAX_PARTICLES; i++) {
            if (particles[i].active) { anyActive = true; break; }
          }
          if (!anyActive) {
            pulsePhase = 'deforming';
            deforming = true;
            deformStartTime = entryTime;
          }
        }
      }

      // Phase 4: Deforming (ellipse changes shape, 1.5s)
      if (pulsePhase === 'deforming') {
        const dT = Math.min(1, (entryTime - deformStartTime) / 1.5);
        deformationProgress = easeInOutCubic(dT);

        // Interpolate L matrix
        currentL = [
          [lerp(DEFAULT_L[0][0], DEFORMED_L[0][0], deformationProgress), lerp(DEFAULT_L[0][1], DEFORMED_L[0][1], deformationProgress)],
          [lerp(DEFAULT_L[1][0], DEFORMED_L[1][0], deformationProgress), lerp(DEFAULT_L[1][1], DEFORMED_L[1][1], deformationProgress)],
        ];

        if (dT >= 1) {
          pulsePhase = 'done';
          canReplay = true;
        }
      }

      // Maintain brighten after initial ramp
      if (pulsePhase !== 'waiting' && pulsePhase !== 'brightening') {
        // Gently pulse the brighten intensity
        brightenIntensity = 0.7 + 0.3 * Math.sin(elapsed * 1.5);
      }

      // --- Update particles ---
      for (let i = 0; i < MAX_PARTICLES; i++) {
        const p = particles[i];
        if (!p.active) continue;

        // Store trail position before moving
        if (p.flowIndex < flowPaths.length) {
          const path = flowPaths[p.flowIndex];
          const pos = bezierPoint(path.from, path.ctrl1, path.ctrl2, path.to, p.progress);

          // Record trail (keep last TRAIL_LENGTH positions)
          p.trail.push({ x: pos.x, y: pos.y });
          if (p.trail.length > TRAIL_LENGTH) {
            p.trail.shift();
          }
        }

        // Move particle along path
        // Speed easing: faster at start (near bar), slower near ellipse
        const speedMult = 1.0 - p.progress * 0.5; // slows down as it approaches
        p.progress += p.speed * speedMult * dt;

        // Fade near end for soft landing
        if (p.progress > 0.8) {
          p.alpha = Math.max(0, (1 - p.progress) / 0.2);
        }

        if (p.progress >= 1) {
          p.active = false;
          particlesLanded++;

          // Spawn ripple at ellipse boundary
          if (p.flowIndex < flowPaths.length) {
            const path = flowPaths[p.flowIndex];
            spawnRipple(path.to.x, path.to.y, path.dualNorm);
          }
        }
      }

      // --- Update ripples ---
      for (let i = 0; i < MAX_RIPPLES; i++) {
        const r = ripples[i];
        if (!r.active) continue;
        r.radius += dt * 35;
        r.alpha -= dt * 1.2;
        if (r.alpha <= 0 || r.radius >= r.maxRadius) {
          r.active = false;
        }
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      // Recompute flow paths each frame (handles resize)
      const maxT = maxTotal();
      const maxBarH = 155;
      for (let i = 0; i < 10; i++) {
        const scale = maxBarH / maxT;
        energyHeights[i] = ENERGY_VALUES[i] * scale;
        reserveHeights[i] = RESERVE_VALUES[i] * scale;
      }
      computeFlowPaths(width, height);

      ctx.save();
      ctx.globalAlpha = alpha;

      const center = getEllipseCenter(width, height);
      const { startX, baselineY, totalW } = getBarArea(width, height);

      // ==========================================================
      // LAYER 1: Background elements
      // ==========================================================

      // --- Mini zone map with glow ---
      {
        const mm = getMiniMapRect(width, height);
        ctx.save();
        ctx.globalAlpha = alpha * 0.45;

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

        for (let i = 0; i < 10; i++) {
          const p = ZONE_POSITIONS[i];
          const px = mm.x + p.x * mm.w;
          const py = mm.y + p.y * mm.h;
          const dualNorm = DUAL_VALUES[i] / MAX_DUAL;

          if (dualNorm > 0.05) {
            const pulse = brightenIntensity * (0.8 + 0.2 * Math.sin(elapsed * 2.1 + i * 0.8));
            Renderer.drawGlow(ctx, px, py, 15 + dualNorm * 12, COLORS.ember, dualNorm * pulse * 0.8);
          }

          ctx.beginPath();
          ctx.arc(px, py, dualNorm > 0.05 ? 5 : 4, 0, Math.PI * 2);
          ctx.fillStyle = dualNorm > 0.05
            ? `rgba(232, 118, 58, ${0.5 + dualNorm * 0.5})`
            : `rgba(26, 122, 109, 0.4)`;
          ctx.fill();
        }

        ctx.restore();
      }

      // ==========================================================
      // LAYER 2: Ellipse with potential deformation
      // ==========================================================

      // Boundary glow when particles are hitting
      if (pulsePhase === 'flowing' || pulsePhase === 'deforming') {
        const glowIntensity = pulsePhase === 'flowing'
          ? Math.min(1, particlesLanded / 8) * 0.25
          : (1 - deformationProgress) * 0.3;

        if (glowIntensity > 0.01) {
          // Draw a soft glow around the entire ellipse
          const numGlowPoints = 48;
          for (let gi = 0; gi < numGlowPoints; gi++) {
            const t = (gi / numGlowPoints) * Math.PI * 2;
            const cosT = Math.cos(t);
            const sinT = Math.sin(t);
            const px = (currentL[0][0] * cosT + currentL[0][1] * sinT) * ellipseScale + center.x;
            const py = (currentL[1][0] * cosT + currentL[1][1] * sinT) * ellipseScale + center.y;

            Renderer.drawGlow(ctx, px, py, 8, COLORS.ember, glowIntensity * 0.3);
          }
        }
      }

      // The ellipse itself
      Renderer.drawEllipse(ctx, center.x, center.y, currentL, ellipseScale, {
        fillColor: 'rgba(26, 122, 109, 0.06)',
        strokeColor: COLORS.teal,
        lineWidth: 2,
        alpha: 0.8,
      });

      // Deformation indicator: draw the original ellipse as a dashed ghost
      if (deformationProgress > 0.05) {
        Renderer.drawEllipse(ctx, center.x, center.y, DEFAULT_L, ellipseScale, {
          fillColor: null,
          strokeColor: COLORS.teal,
          lineWidth: 1,
          alpha: 0.15 * (1 - deformationProgress * 0.5),
          dash: [4, 6],
        });
      }

      // ==========================================================
      // LAYER 3: Exposure vectors
      // ==========================================================

      for (let ei = 0; ei < EXPOSURE_ZONES.length; ei++) {
        const zi = EXPOSURE_ZONES[ei];
        const dir = EXPOSURE_DIRS_MAP[zi];
        const sp = supportPoint(currentL, dir);
        const spScreen = {
          x: center.x + sp.x * ellipseScale,
          y: center.y + sp.y * ellipseScale,
        };
        const arrowLen = 55;
        const fromX = spScreen.x + dir[0] * arrowLen;
        const fromY = spScreen.y + dir[1] * arrowLen;

        // Is this a flow zone? If so, draw brighter
        const isFlowZone = FLOW_ZONES.includes(zi);
        const vectorAlpha = isFlowZone ? 0.35 : 0.15;

        Renderer.drawLine(ctx, fromX, fromY, spScreen.x, spScreen.y, {
          color: isFlowZone ? COLORS.ember : COLORS.teal,
          lineWidth: isFlowZone ? 1.5 : 1,
          alpha: vectorAlpha,
        });

        // Support point
        if (isFlowZone) {
          const pf = 0.6 + 0.4 * Math.sin(elapsed * 3 + ei);
          ctx.beginPath();
          ctx.arc(spScreen.x, spScreen.y, 3 + pf, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(232, 118, 58, ${0.4 + pf * 0.3})`;
          ctx.fill();
        }
      }

      // ==========================================================
      // LAYER 4: Flow path lines (subtle bezier curves)
      // ==========================================================

      if (pulseTriggered) {
        for (let fi = 0; fi < flowPaths.length; fi++) {
          const path = flowPaths[fi];
          ctx.save();

          // Draw the bezier path as a subtle guide line
          ctx.beginPath();
          ctx.moveTo(path.from.x, path.from.y);
          ctx.bezierCurveTo(path.ctrl1.x, path.ctrl1.y, path.ctrl2.x, path.ctrl2.y, path.to.x, path.to.y);
          ctx.strokeStyle = `rgba(232, 118, 58, ${0.06 + path.dualNorm * 0.06})`;
          ctx.lineWidth = 1;
          ctx.stroke();

          ctx.restore();
        }
      }

      // ==========================================================
      // LAYER 5: Baseline and stacked bars
      // ==========================================================

      // Baseline
      Renderer.drawLine(ctx, startX - 10, baselineY, startX + totalW + 10, baselineY, {
        color: COLORS.ink,
        lineWidth: 1,
        alpha: 0.25,
      });

      // Stacked bars with shadow-price glow
      for (let i = 0; i < 10; i++) {
        const bx = startX + i * (BAR_WIDTH + BAR_GAP);
        const eH = energyHeights[i];
        const rH = reserveHeights[i];
        const dualVal = DUAL_VALUES[i];
        const dualNorm = dualVal / MAX_DUAL;

        // Extra glow for flow-source zones during brightening phase
        const isFlowZone = FLOW_ZONES.includes(i);
        let extraGlow = 0;
        if (isFlowZone && brightenIntensity > 0) {
          extraGlow = brightenIntensity * dualNorm;
        }

        // Glow behind bar
        if (dualNorm > 0.01 || extraGlow > 0) {
          const pulseFactor = 0.8 + 0.2 * Math.sin(elapsed * (2 * Math.PI / 3) + i * 0.8);
          const glowIntensity = Math.max(dualNorm * pulseFactor, extraGlow) * 0.5;
          const glowCenterX = bx + BAR_WIDTH / 2;
          const glowCenterY = baselineY - (eH + rH) / 2;
          const glowRadius = 30 + Math.max(dualNorm, extraGlow) * 30;

          Renderer.drawGlow(ctx, glowCenterX, glowCenterY, glowRadius,
            isFlowZone ? COLORS.coral : COLORS.ember, glowIntensity);
        }

        // Energy portion
        if (eH > 0.5) {
          Renderer.drawBar(ctx, bx, baselineY, BAR_WIDTH, eH, {
            color: COLORS.teal,
            alpha: 0.55,
            radius: rH > 0.5 ? 0 : 3,
          });
        }

        // Reserve portion
        if (rH > 0.5) {
          const reserveBaseY = baselineY - eH;
          const glowColor = (dualNorm > 0.3 || extraGlow > 0.3) ? COLORS.ember : null;
          const glowI = Math.max(
            dualNorm > 0.3 ? dualNorm * (0.8 + 0.2 * Math.sin(elapsed * 2.1 + i)) : 0,
            extraGlow * 0.8
          );

          Renderer.drawBar(ctx, bx, reserveBaseY, BAR_WIDTH, rH, {
            color: COLORS.ember,
            alpha: 0.75,
            radius: 3,
            glowColor,
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

        // Pressure arcs for constrained zones
        if (dualNorm > 0.05) {
          const arcCenterX = bx + BAR_WIDTH / 2;
          const arcCenterY = baselineY - eH - rH - 15;
          const arcRadius = 18;
          const startAngle = -Math.PI;
          const sweepAngle = Math.PI * dualNorm;
          const pf = 0.85 + 0.15 * Math.sin(elapsed * (2 * Math.PI / 3) + i * 0.8);
          const arcAlpha = dualNorm * pf * 0.8;

          ctx.save();
          ctx.beginPath();
          ctx.arc(arcCenterX, arcCenterY, arcRadius, startAngle, startAngle + sweepAngle);
          ctx.strokeStyle = `rgba(232, 118, 58, ${arcAlpha})`;
          ctx.lineWidth = 3;
          ctx.lineCap = 'round';
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(arcCenterX, arcCenterY, arcRadius, startAngle, 0);
          ctx.strokeStyle = `rgba(45, 45, 45, 0.08)`;
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.restore();

          // Mu label
          Renderer.drawText(ctx, `\u03BC = ${dualVal.toFixed(1)}`, arcCenterX, arcCenterY - arcRadius - 6, {
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

      // ==========================================================
      // LAYER 6: Flow particles (the main event)
      // ==========================================================

      if (pulseTriggered) {
        for (let i = 0; i < MAX_PARTICLES; i++) {
          const p = particles[i];
          if (!p.active || p.flowIndex >= flowPaths.length) continue;

          const path = flowPaths[p.flowIndex];
          const pos = bezierPoint(path.from, path.ctrl1, path.ctrl2, path.to, p.progress);

          // --- Trail rendering ---
          for (let t = 0; t < p.trail.length; t++) {
            const tp = p.trail[t];
            const trailAge = (p.trail.length - t) / (p.trail.length + 1);
            const trailAlpha = p.alpha * (1 - trailAge) * 0.45;
            const trailSize = p.size * (1 - trailAge * 0.5) * 0.7;

            if (trailAlpha < 0.01) continue;

            // Trail with glow
            ctx.save();
            ctx.globalAlpha = alpha * trailAlpha;
            ctx.fillStyle = COLORS.ember;
            ctx.beginPath();
            ctx.arc(tp.x, tp.y, trailSize, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
          }

          // --- Main particle with glow ---
          const mainAlpha = p.alpha * p.brightness;

          // Outer glow halo
          const glowRadius = p.size * 3;
          ctx.save();
          ctx.globalAlpha = alpha * mainAlpha * 0.35;
          const glowGrad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowRadius);
          glowGrad.addColorStop(0, COLORS.ember);
          glowGrad.addColorStop(0.5, `rgba(232, 118, 58, 0.3)`);
          glowGrad.addColorStop(1, 'rgba(232, 118, 58, 0)');
          ctx.fillStyle = glowGrad;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();

          // Core bright dot
          ctx.save();
          ctx.globalAlpha = alpha * Math.min(1, mainAlpha * 1.2);
          ctx.fillStyle = COLORS.ember;
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, p.size, 0, Math.PI * 2);
          ctx.fill();

          // Hot white center
          ctx.globalAlpha = alpha * mainAlpha * 0.6;
          ctx.fillStyle = '#FFF5EB';
          ctx.beginPath();
          ctx.arc(pos.x, pos.y, p.size * 0.4, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        }
      }

      // ==========================================================
      // LAYER 7: Impact ripples on ellipse boundary
      // ==========================================================

      for (let i = 0; i < MAX_RIPPLES; i++) {
        const r = ripples[i];
        if (!r.active) continue;

        ctx.save();
        ctx.globalAlpha = alpha * r.alpha;

        // Draw expanding arc centered on impact point
        // The arc follows the ellipse boundary approximately
        const angSpan = r.sweepAngle * (1 + r.radius / r.maxRadius);
        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
        ctx.strokeStyle = COLORS.ember;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Inner glow
        const rGrad = ctx.createRadialGradient(r.x, r.y, 0, r.x, r.y, r.radius);
        rGrad.addColorStop(0, `rgba(232, 118, 58, ${r.alpha * 0.3})`);
        rGrad.addColorStop(1, 'rgba(232, 118, 58, 0)');
        ctx.fillStyle = rGrad;
        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }

      // ==========================================================
      // LAYER 8: Pulse origin glow at bars during brightening
      // ==========================================================

      if (pulsePhase === 'brightening' || (pulsePhase === 'flowing' && (entryTime - flowStartTime) < 0.5)) {
        for (let fi = 0; fi < FLOW_ZONES.length; fi++) {
          const zi = FLOW_ZONES[fi];
          const bx = startX + zi * (BAR_WIDTH + BAR_GAP) + BAR_WIDTH / 2;
          const by = baselineY - energyHeights[zi] - reserveHeights[zi];
          const intensity = brightenIntensity * FLOW_DUALS[fi] / MAX_DUAL;

          // Expanding pulse ring at source
          const ringRadius = 10 + brightenIntensity * 20;
          ctx.save();
          ctx.globalAlpha = alpha * intensity * 0.4;
          ctx.beginPath();
          ctx.arc(bx, by, ringRadius, 0, Math.PI * 2);
          ctx.strokeStyle = COLORS.coral;
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.restore();

          Renderer.drawGlow(ctx, bx, by, 20 + intensity * 15, COLORS.coral, intensity * 0.6);
        }
      }

      // ==========================================================
      // LAYER 9: Cost counter and labels
      // ==========================================================

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

      // ==========================================================
      // LAYER 10: Narrative text
      // ==========================================================

      if (pulsePhase === 'flowing' || pulsePhase === 'deforming' || pulsePhase === 'done') {
        const narrativeT = pulsePhase === 'done' ? 1 : Math.min(1, (entryTime - flowStartTime - 0.5) * 1.5);
        if (narrativeT > 0) {
          Renderer.drawText(ctx, 'The gradient flows backward', width * 0.5, height * 0.56, {
            font: 'italic 16px Inter, sans-serif',
            color: COLORS.ink,
            align: 'center',
            baseline: 'middle',
            alpha: narrativeT * 0.7,
          });

          if (pulsePhase === 'deforming' || pulsePhase === 'done') {
            const subT = pulsePhase === 'done' ? 1 : Math.min(1, deformationProgress * 2);
            Renderer.drawText(ctx, 'reshaping uncertainty to reduce cost', width * 0.5, height * 0.56 + 22, {
              font: 'italic 13px Inter, sans-serif',
              color: COLORS.inkLight,
              align: 'center',
              baseline: 'middle',
              alpha: subT * 0.5,
            });
          }
        }
      }

      // Replay hint
      if (canReplay) {
        const hintAlpha = 0.3 + 0.15 * Math.sin(elapsed * 2);
        Renderer.drawText(ctx, 'Click to replay', width * 0.5, height * 0.95, {
          font: '12px Inter, sans-serif',
          color: COLORS.inkLight,
          align: 'center',
          baseline: 'middle',
          alpha: hintAlpha,
        });
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // Replay pulse on click when done
      if (canReplay && (event.type === 'click' || event.type === 'touchend')) {
        // Reset everything for replay
        entryTime = 0;
        elapsed = 0;
        resetPulse();
        return;
      }
    },
  };
}
