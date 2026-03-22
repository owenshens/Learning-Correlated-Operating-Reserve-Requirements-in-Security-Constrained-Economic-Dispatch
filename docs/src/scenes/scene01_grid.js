// === Scene 01: The Grid Is Calm ===
// Softly lit 10-zone schematic with ambient pulsing and connection pulses.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';

// Zone adjacency for the 10-zone layout (0-indexed)
const ZONE_ADJACENCY = [
  [1, 5],        // Z1 -> Z2, Z6
  [0, 2, 6],     // Z2 -> Z1, Z3, Z7
  [1, 3, 7],     // Z3 -> Z2, Z4, Z8
  [2, 4, 8],     // Z4 -> Z3, Z5, Z9
  [3, 9],        // Z5 -> Z4, Z10
  [0, 6],        // Z6 -> Z1, Z7
  [1, 5, 7],     // Z7 -> Z2, Z6, Z8
  [2, 6, 8],     // Z8 -> Z3, Z7, Z9
  [3, 7, 9],     // Z9 -> Z4, Z8, Z10
  [4, 8],        // Z10 -> Z5, Z9
];

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

export function createScene01() {
  // Local state
  let zones = [];        // {x, y, load, genCount, name, sources}
  let edges = [];        // {from, to}
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let pulses = [];       // {edgeIndex, progress, speed}
  const PULSE_COUNT = 6;

  function initZones(state) {
    // Zone positions and data from zones.json (hardcoded for self-containment)
    const zoneInfo = [
      { id: 1, load: 365, gen: 6, x: 0.15, y: 0.75, sources: ['load'] },
      { id: 2, load: 341, gen: 4, x: 0.35, y: 0.80, sources: ['load'] },
      { id: 3, load: 360, gen: 7, x: 0.55, y: 0.78, sources: ['load', 'solar'] },
      { id: 4, load: 395, gen: 3, x: 0.75, y: 0.72, sources: ['load', 'solar'] },
      { id: 5, load: 801, gen: 5, x: 0.90, y: 0.60, sources: ['load', 'solar'] },
      { id: 6, load: 222, gen: 7, x: 0.10, y: 0.35, sources: ['load', 'solar'] },
      { id: 7, load: 575, gen: 5, x: 0.30, y: 0.25, sources: ['load', 'wind'] },
      { id: 8, load: 453, gen: 6, x: 0.50, y: 0.22, sources: ['load', 'wind'] },
      { id: 9, load: 342, gen: 6, x: 0.70, y: 0.28, sources: ['load', 'wind'] },
      { id: 10, load: 388, gen: 5, x: 0.88, y: 0.38, sources: ['load', 'wind'] },
    ];

    zones = zoneInfo.map(z => ({
      id: z.id,
      name: `Z${z.id}`,
      load: z.load,
      genCount: z.gen,
      nx: z.x,   // normalized x
      ny: z.y,   // normalized y
      sources: z.sources,
    }));

    // Build edge list from adjacency (avoid duplicates)
    edges = [];
    const edgeSet = new Set();
    for (let i = 0; i < 10; i++) {
      for (const j of ZONE_ADJACENCY[i]) {
        const key = Math.min(i, j) + '-' + Math.max(i, j);
        if (!edgeSet.has(key)) {
          edgeSet.add(key);
          edges.push({ from: i, to: j });
        }
      }
    }

    // Initialize pulses along random edges
    pulses = [];
    for (let i = 0; i < PULSE_COUNT; i++) {
      pulses.push({
        edgeIndex: Math.floor(Math.random() * edges.length),
        progress: Math.random(),
        speed: 0.12 + Math.random() * 0.15,
      });
    }
  }

  function getZoneScreenPos(zone, width, height) {
    const margin = 80;
    const usableW = width - margin * 2;
    const usableH = height - margin * 2;
    return {
      x: margin + zone.nx * usableW,
      y: margin + zone.ny * usableH,
    };
  }

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);
      initZones(state);
    },

    exit(state) {
      // nothing to clean up
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);

      // Update pulses
      for (const p of pulses) {
        p.progress += p.speed * dt;
        if (p.progress > 1) {
          p.progress -= 1;
          p.edgeIndex = Math.floor(Math.random() * edges.length);
          p.speed = 0.12 + Math.random() * 0.15;
        }
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      // Find max load for normalization
      let maxLoad = 0;
      for (const z of zones) {
        if (z.load > maxLoad) maxLoad = z.load;
      }

      // Precompute screen positions
      const positions = zones.map(z => getZoneScreenPos(z, width, height));

      // --- Draw connections ---
      for (const edge of edges) {
        const p1 = positions[edge.from];
        const p2 = positions[edge.to];
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = 'rgba(45, 45, 45, 0.10)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // --- Draw pulse along connections ---
      for (const p of pulses) {
        const edge = edges[p.edgeIndex];
        const p1 = positions[edge.from];
        const p2 = positions[edge.to];
        const px = p1.x + (p2.x - p1.x) * p.progress;
        const py = p1.y + (p2.y - p1.y) * p.progress;

        // Pulse is a small bright segment
        const segLen = 0.12;
        const t0 = Math.max(0, p.progress - segLen / 2);
        const t1 = Math.min(1, p.progress + segLen / 2);
        const sx = p1.x + (p2.x - p1.x) * t0;
        const sy = p1.y + (p2.y - p1.y) * t0;
        const ex = p1.x + (p2.x - p1.x) * t1;
        const ey = p1.y + (p2.y - p1.y) * t1;

        // Brightness peaks at center of segment
        const pulseAlpha = 0.25 + 0.15 * Math.sin(elapsed * 2 + p.edgeIndex);
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(ex, ey);
        ctx.strokeStyle = `rgba(26, 122, 109, ${pulseAlpha})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Bright dot at center
        Renderer.drawParticle(ctx, px, py, 2, COLORS.tealLight, pulseAlpha * 1.2);
      }

      // --- Draw zones ---
      const zoneW = 64;
      const zoneH = 52;
      const cornerR = 8;

      for (let i = 0; i < zones.length; i++) {
        const zone = zones[i];
        const pos = positions[i];
        const loadNorm = maxLoad > 0 ? zone.load / maxLoad : 0;

        // Ambient pulse: very gentle alpha oscillation
        const pulsePeriod = 8;
        const phaseOffset = i * 0.63;
        const pulseVal = 0.92 + 0.08 * Math.sin((elapsed / pulsePeriod) * Math.PI * 2 + phaseOffset);

        ctx.save();
        ctx.globalAlpha = alpha * pulseVal;

        // Demand halo (warm radial gradient proportional to load)
        const haloRadius = 30 + loadNorm * 35;
        const haloAlpha = loadNorm * 0.15;
        const gradient = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, haloRadius);
        gradient.addColorStop(0, `rgba(139, 125, 107, ${haloAlpha})`);
        gradient.addColorStop(0.6, `rgba(139, 125, 107, ${haloAlpha * 0.4})`);
        gradient.addColorStop(1, 'rgba(139, 125, 107, 0)');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, haloRadius, 0, Math.PI * 2);
        ctx.fill();

        // Zone rectangle
        const rx = pos.x - zoneW / 2;
        const ry = pos.y - zoneH / 2;
        const brightness = 245 - Math.round(loadNorm * 20);
        ctx.fillStyle = `rgb(${brightness}, ${brightness - 3}, ${brightness - 8})`;
        roundedRect(ctx, rx, ry, zoneW, zoneH, cornerR);
        ctx.fill();

        // Border
        ctx.strokeStyle = 'rgba(45, 45, 45, 0.22)';
        ctx.lineWidth = 1;
        roundedRect(ctx, rx, ry, zoneW, zoneH, cornerR);
        ctx.stroke();

        // Zone label
        ctx.fillStyle = COLORS.ink;
        ctx.font = 'bold 13px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(zone.name, pos.x, ry + 5);

        // Generator dots
        const dotRadius = 2;
        const dotsPerRow = Math.min(zone.genCount, 5);
        const dotSpacing = 8;
        const dotsY = pos.y + 4;

        ctx.fillStyle = 'rgba(26, 122, 109, 0.45)';
        let dotIdx = 0;
        const dotRows = Math.ceil(zone.genCount / dotsPerRow);
        for (let row = 0; row < dotRows && dotIdx < zone.genCount; row++) {
          const dotsInRow = Math.min(dotsPerRow, zone.genCount - dotIdx);
          const rowStartX = pos.x - (dotsInRow - 1) * dotSpacing / 2;
          for (let col = 0; col < dotsInRow; col++) {
            ctx.beginPath();
            ctx.arc(rowStartX + col * dotSpacing, dotsY + row * dotSpacing, dotRadius, 0, Math.PI * 2);
            ctx.fill();
            dotIdx++;
          }
        }

        ctx.restore();
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // No interaction for scene 1
    },
  };
}
