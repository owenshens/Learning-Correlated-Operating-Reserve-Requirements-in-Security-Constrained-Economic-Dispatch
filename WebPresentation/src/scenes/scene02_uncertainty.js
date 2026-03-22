// === Scene 02: Uncertainty Appears ===
// Zone map fades to background, three color-coded uncertainty streams converge into an ellipse.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';
import { Ellipsoid } from '../components/ellipsoid.js';

// Zone layout (same as scene01)
const ZONE_INFO = [
  { id: 1, load: 365, gen: 6, x: 0.15, y: 0.75 },
  { id: 2, load: 341, gen: 4, x: 0.35, y: 0.80 },
  { id: 3, load: 360, gen: 7, x: 0.55, y: 0.78 },
  { id: 4, load: 395, gen: 3, x: 0.75, y: 0.72 },
  { id: 5, load: 801, gen: 5, x: 0.90, y: 0.60 },
  { id: 6, load: 222, gen: 7, x: 0.10, y: 0.35 },
  { id: 7, load: 575, gen: 5, x: 0.30, y: 0.25 },
  { id: 8, load: 453, gen: 6, x: 0.50, y: 0.22 },
  { id: 9, load: 342, gen: 6, x: 0.70, y: 0.28 },
  { id: 10, load: 388, gen: 5, x: 0.88, y: 0.38 },
];

const ZONE_ADJACENCY = [
  [1, 5], [0, 2, 6], [1, 3, 7], [2, 4, 8], [3, 9],
  [0, 6], [1, 5, 7], [2, 6, 8], [3, 7, 9], [4, 8],
];

const STREAM_CONFIGS = [
  { label: 'Load',  color: COLORS.load,  startNY: 0.35, curveAmp: -20 },
  { label: 'Solar', color: COLORS.solar, startNY: 0.50, curveAmp: 0 },
  { label: 'Wind',  color: COLORS.wind,  startNY: 0.65, curveAmp: 20 },
];

const PARTICLES_PER_STREAM = 18;

function roundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

export function createScene02() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);

  // Zone map shrink/shift state
  let mapScale = new AnimatedValue(1);
  let mapOffsetX = new AnimatedValue(0);
  let mapAlpha = new AnimatedValue(1);

  // Ellipsoid for the uncertainty cloud
  let ellipsoid = null;
  let cloudAlpha = new AnimatedValue(0);
  let cloudMorphTime = 0;

  // Particle arrays per stream
  let streams = [];

  function initParticles() {
    streams = STREAM_CONFIGS.map((config, si) => {
      const particles = [];
      for (let i = 0; i < PARTICLES_PER_STREAM; i++) {
        particles.push({
          t: i / PARTICLES_PER_STREAM,  // progress along path [0,1]
          speed: 0.06 + Math.random() * 0.04,
          perpOffset: (Math.random() - 0.5) * 16,
          radius: 1.5 + Math.random() * 2,
          alphaBase: 0.4 + Math.random() * 0.4,
        });
      }
      return { config, particles };
    });
  }

  function getZoneScreenPos(zone, mapCx, mapCy, scale) {
    const mapRadius = 120 * scale;
    const margin = mapRadius;
    return {
      x: mapCx - mapRadius + zone.x * mapRadius * 2,
      y: mapCy - mapRadius + zone.y * mapRadius * 2,
    };
  }

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);

      // Animate zone map to small/left
      mapScale.snap(1);
      mapScale.set(0.55);
      mapScale.smoothing = 2;

      mapOffsetX.snap(0);
      mapOffsetX.set(-0.22);
      mapOffsetX.smoothing = 2;

      mapAlpha.snap(1);
      mapAlpha.set(0.35);
      mapAlpha.smoothing = 2;

      // Cloud fades in
      cloudAlpha.snap(0);
      cloudAlpha.set(1);
      cloudAlpha.smoothing = 1.5;

      // Create the ellipsoid
      ellipsoid = new Ellipsoid({ scale: 110, particleCount: 12 });
      // Default L: slightly eccentric
      const defaultL = [[1.2, 0], [0.3, 0.9]];
      ellipsoid.setL(defaultL);
      ellipsoid.showAxes = false;

      cloudMorphTime = 0;
      initParticles();
    },

    exit(state) {
      ellipsoid = null;
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);
      mapScale.update(dt);
      mapOffsetX.update(dt);
      mapAlpha.update(dt);
      cloudAlpha.update(dt);

      // Ambient cloud morph: slow rotation/stretch
      cloudMorphTime += dt;

      if (ellipsoid) {
        ellipsoid.update(dt);
      }

      // Update particles
      for (const stream of streams) {
        for (const p of stream.particles) {
          p.t += p.speed * dt;
          if (p.t > 1) {
            p.t -= 1;
            p.perpOffset = (Math.random() - 0.5) * 16;
          }
        }
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      const mScale = mapScale.get();
      const mOffX = mapOffsetX.get();
      const mAlpha = mapAlpha.get();

      // --- Draw miniature zone map (shifted left, dimmer) ---
      const mapCx = width * (0.5 + mOffX) * mScale + width * (1 - mScale) * 0.15;
      const mapCy = height * 0.5;
      const mapR = 140 * mScale;

      ctx.save();
      ctx.globalAlpha = alpha * mAlpha;

      // Draw connections
      const edgeSet = new Set();
      for (let i = 0; i < 10; i++) {
        for (const j of ZONE_ADJACENCY[i]) {
          const key = Math.min(i, j) + '-' + Math.max(i, j);
          if (edgeSet.has(key)) continue;
          edgeSet.add(key);
          const p1 = getZoneScreenPos(ZONE_INFO[i], mapCx, mapCy, mScale);
          const p2 = getZoneScreenPos(ZONE_INFO[j], mapCx, mapCy, mScale);
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = 'rgba(45, 45, 45, 0.08)';
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      }

      // Draw zones
      const zW = 44 * mScale;
      const zH = 36 * mScale;
      for (let i = 0; i < ZONE_INFO.length; i++) {
        const z = ZONE_INFO[i];
        const pos = getZoneScreenPos(z, mapCx, mapCy, mScale);
        ctx.fillStyle = 'rgb(240, 237, 232)';
        roundedRect(ctx, pos.x - zW / 2, pos.y - zH / 2, zW, zH, 5 * mScale);
        ctx.fill();
        ctx.strokeStyle = 'rgba(45, 45, 45, 0.18)';
        ctx.lineWidth = 0.7;
        roundedRect(ctx, pos.x - zW / 2, pos.y - zH / 2, zW, zH, 5 * mScale);
        ctx.stroke();

        // Label
        ctx.fillStyle = COLORS.ink;
        ctx.font = `bold ${Math.round(10 * mScale)}px -apple-system, BlinkMacSystemFont, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`Z${z.id}`, pos.x, pos.y);
      }
      ctx.restore();

      // --- Ellipse cloud position ---
      const cloudCx = width * 0.62;
      const cloudCy = height * 0.48;
      const cAlpha = cloudAlpha.get();

      // --- Draw particle streams ---
      const streamStartX = width * 0.25;
      const streamEndX = cloudCx - 60;

      for (const stream of streams) {
        const cfg = stream.config;
        const baseY = height * cfg.startNY;

        // Stream label at left
        ctx.save();
        ctx.globalAlpha = alpha * Math.min(cAlpha, 0.85);
        ctx.font = '13px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillStyle = cfg.color;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(cfg.label, streamStartX - 12, baseY);
        ctx.restore();

        // Draw particles
        for (const p of stream.particles) {
          const t = p.t;
          // Curved path from left to cloud center
          const px = streamStartX + (streamEndX - streamStartX) * t;
          // Curve toward cloud center Y with a gentle arc
          const linearY = baseY + (cloudCy - baseY) * t;
          const curveY = linearY + cfg.curveAmp * Math.sin(t * Math.PI);
          const perpY = curveY + p.perpOffset * (1 - t * 0.7);

          // Alpha: fade in as approaching cloud, fade out at very start
          const fadeIn = Math.min(1, t * 4);
          const fadeEnd = 1 - Math.pow(t, 4) * 0.4;
          const pAlpha = p.alphaBase * fadeIn * fadeEnd * cAlpha;

          // Size decreases slightly as particle converges
          const pRadius = p.radius * (1 - t * 0.3);

          ctx.save();
          ctx.globalAlpha = alpha * pAlpha;
          ctx.fillStyle = cfg.color;
          ctx.beginPath();
          ctx.arc(px, perpY, pRadius, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        }
      }

      // --- Draw uncertainty ellipse cloud ---
      if (ellipsoid && cAlpha > 0.01) {
        // Ambient morph: slow rotation
        const morphAngle = cloudMorphTime * 0.15;
        const stretchA = 1.2 + 0.15 * Math.sin(morphAngle);
        const stretchB = 0.9 + 0.1 * Math.cos(morphAngle * 0.7);
        const rotAngle = 0.2 * Math.sin(morphAngle * 0.5);

        const cosR = Math.cos(rotAngle);
        const sinR = Math.sin(rotAngle);
        // L = R * diag(stretchA, stretchB)
        const ambientL = [
          [cosR * stretchA, -sinR * stretchB],
          [sinR * stretchA, cosR * stretchB],
        ];

        ellipsoid.cx = cloudCx;
        ellipsoid.cy = cloudCy;
        ellipsoid.setL(ambientL);

        ctx.save();
        ctx.globalAlpha = alpha * cAlpha;
        ellipsoid.render(ctx);
        ctx.restore();

        // Label: "Uncertainty Set"
        ctx.save();
        ctx.globalAlpha = alpha * cAlpha * 0.7;
        ctx.font = 'italic 14px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillStyle = COLORS.inkLight;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText('Uncertainty Set', cloudCx, cloudCy + ellipsoid.scale * 1.3 + 10);
        ctx.restore();
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // No interaction for scene 2
    },
  };
}
