// === Scene 04: Exposure Directions ===
// Ellipse center-stage with luminous exposure vectors from highlighted zones.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';
import { Ellipsoid } from '../components/ellipsoid.js';
import { supportPoint } from '../math/ellipse.js';

// Zone layout for background map and labels
const ZONE_INFO = [
  { id: 1, x: 0.15, y: 0.75 },
  { id: 2, x: 0.35, y: 0.80 },
  { id: 3, x: 0.55, y: 0.78 },
  { id: 4, x: 0.75, y: 0.72 },
  { id: 5, x: 0.90, y: 0.60 },
  { id: 6, x: 0.10, y: 0.35 },
  { id: 7, x: 0.30, y: 0.25 },
  { id: 8, x: 0.50, y: 0.22 },
  { id: 9, x: 0.70, y: 0.28 },
  { id: 10, x: 0.88, y: 0.38 },
];

const ZONE_ADJACENCY = [
  [1, 5], [0, 2, 6], [1, 3, 7], [2, 4, 8], [3, 9],
  [0, 6], [1, 5, 7], [2, 6, 8], [3, 7, 9], [4, 8],
];

// Highlighted zones with distinct exposure angles (0-indexed)
const HIGHLIGHTED_ZONES = [
  { zoneIdx: 2, angle: 0,                color: COLORS.teal },      // Zone 3: rightward
  { zoneIdx: 4, angle: Math.PI * 0.25,   color: COLORS.ember },     // Zone 5: 45 degrees
  { zoneIdx: 7, angle: Math.PI * 0.667,  color: COLORS.cobalt },    // Zone 8: ~120 degrees
];

// The learned L matrix for the ellipse (Static L shape)
const ELLIPSE_L = [[1.5, 0], [0.8, 0.55]];

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

export function createScene04() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let ellipsoid = null;
  let selectedZone = -1;

  // Animated support point positions (for smooth transitions)
  let supportPoints = []; // {x, y} in canvas coords for each highlighted zone

  // Zone label clickable areas (populated during render)
  let labelHitboxes = []; // {zoneIdx, x, y, w, h}

  function getZoneScreenPos(zone, mapCx, mapCy, mapR) {
    return {
      x: mapCx - mapR + zone.x * mapR * 2,
      y: mapCy - mapR + zone.y * mapR * 2,
    };
  }

  function computeSupportPoints(ellCx, ellCy, scale) {
    supportPoints = HIGHLIGHTED_ZONES.map(hz => {
      const dir = [Math.cos(hz.angle), Math.sin(hz.angle)];
      const sp = supportPoint(ELLIPSE_L, dir);
      return {
        x: ellCx + sp.x * scale,
        y: ellCy + sp.y * scale,
        value: sp.value,
        dirX: dir[0],
        dirY: dir[1],
      };
    });
  }

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);

      ellipsoid = new Ellipsoid({ scale: 130, particleCount: 14 });
      ellipsoid.setL(ELLIPSE_L);
      ellipsoid.showAxes = true;

      selectedZone = state.selectedZone !== null ? state.selectedZone : -1;
      supportPoints = [];
      labelHitboxes = [];
    },

    exit(state) {
      ellipsoid = null;
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);

      if (ellipsoid) {
        ellipsoid.update(dt);
      }

      // Sync selectedZone from state
      if (state.selectedZone !== null && state.selectedZone !== undefined) {
        selectedZone = state.selectedZone;
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      // --- Faint background zone map (small, upper-left) ---
      const mapCx = width * 0.13;
      const mapCy = height * 0.3;
      const mapR = 70;

      ctx.save();
      ctx.globalAlpha = alpha * 0.12;

      const edgeSet = new Set();
      for (let i = 0; i < 10; i++) {
        for (const j of ZONE_ADJACENCY[i]) {
          const key = Math.min(i, j) + '-' + Math.max(i, j);
          if (edgeSet.has(key)) continue;
          edgeSet.add(key);
          const p1 = getZoneScreenPos(ZONE_INFO[i], mapCx, mapCy, mapR);
          const p2 = getZoneScreenPos(ZONE_INFO[j], mapCx, mapCy, mapR);
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = 'rgba(45, 45, 45, 0.4)';
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }

      const zW = 20;
      const zH = 16;
      for (const z of ZONE_INFO) {
        const pos = getZoneScreenPos(z, mapCx, mapCy, mapR);
        ctx.fillStyle = 'rgb(238, 235, 230)';
        roundedRect(ctx, pos.x - zW / 2, pos.y - zH / 2, zW, zH, 2);
        ctx.fill();
      }
      ctx.restore();

      // --- Main ellipsoid ---
      const ellCx = width * 0.52;
      const ellCy = height * 0.45;
      const ellScale = 130;

      if (ellipsoid) {
        ellipsoid.cx = ellCx;
        ellipsoid.cy = ellCy;
        ellipsoid.scale = ellScale;

        ctx.save();
        ctx.globalAlpha = alpha;
        ellipsoid.render(ctx);
        ctx.restore();
      }

      // Compute support points
      computeSupportPoints(ellCx, ellCy, ellScale);

      // --- Zone labels on the left, connected to vectors ---
      const labelX = width * 0.12;
      const labelStartY = height * 0.35;
      const labelSpacing = 60;
      labelHitboxes = [];

      for (let hi = 0; hi < HIGHLIGHTED_ZONES.length; hi++) {
        const hz = HIGHLIGHTED_ZONES[hi];
        const sp = supportPoints[hi];
        const zoneId = hz.zoneIdx + 1;
        const isSelected = (selectedZone === hz.zoneIdx);
        const labelY = labelStartY + hi * labelSpacing;

        // Store hitbox for click detection
        const hitW = 80;
        const hitH = 36;
        labelHitboxes.push({
          zoneIdx: hz.zoneIdx,
          x: labelX - hitW / 2,
          y: labelY - hitH / 2,
          w: hitW,
          h: hitH,
        });

        // Determine alpha for this vector
        const hasSelection = selectedZone >= 0;
        const vectorAlpha = hasSelection ? (isSelected ? 1.0 : 0.15) : 0.6;
        const pulseAlpha = isSelected ? (0.7 + 0.3 * Math.sin(elapsed * 3)) : vectorAlpha;

        // --- Draw vector line from label to support point ---
        ctx.save();
        ctx.globalAlpha = alpha * pulseAlpha;

        // Line from label to support point
        ctx.beginPath();
        ctx.moveTo(labelX + 40, labelY);
        ctx.lineTo(sp.x, sp.y);
        ctx.strokeStyle = hz.color;
        ctx.lineWidth = isSelected ? 2.2 : 1.2;
        if (!isSelected && hasSelection) {
          ctx.setLineDash([4, 6]);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // Arrowhead at support point
        if (isSelected || !hasSelection) {
          const dx = sp.x - labelX;
          const dy = sp.y - labelY;
          const angle = Math.atan2(dy, dx);
          const aSize = isSelected ? 9 : 7;

          ctx.beginPath();
          ctx.moveTo(sp.x, sp.y);
          ctx.lineTo(
            sp.x - aSize * Math.cos(angle - Math.PI / 7),
            sp.y - aSize * Math.sin(angle - Math.PI / 7)
          );
          ctx.lineTo(
            sp.x - aSize * Math.cos(angle + Math.PI / 7),
            sp.y - aSize * Math.sin(angle + Math.PI / 7)
          );
          ctx.closePath();
          ctx.fillStyle = hz.color;
          ctx.fill();
        }

        ctx.restore();

        // --- Support point dot (pulsing if selected) ---
        ctx.save();
        const spPulse = isSelected ? (0.6 + 0.4 * Math.sin(elapsed * 4)) : 0.5;
        const spRadius = isSelected ? (5 + 2 * Math.sin(elapsed * 3)) : 3.5;

        // Glow ring for selected
        if (isSelected) {
          ctx.globalAlpha = alpha * spPulse * 0.3;
          const grad = ctx.createRadialGradient(sp.x, sp.y, 0, sp.x, sp.y, spRadius * 3.5);
          grad.addColorStop(0, hz.color);
          grad.addColorStop(1, 'transparent');
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(sp.x, sp.y, spRadius * 3.5, 0, Math.PI * 2);
          ctx.fill();
        }

        // Core dot
        ctx.globalAlpha = alpha * (hasSelection ? (isSelected ? spPulse : 0.2) : 0.6);
        ctx.fillStyle = hz.color;
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, spRadius, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();

        // --- Subtle dashed line downward from support point (reserve preview) ---
        if (isSelected) {
          const previewEndY = sp.y + 50;
          ctx.save();
          ctx.globalAlpha = alpha * 0.2;
          ctx.beginPath();
          ctx.moveTo(sp.x, sp.y + spRadius + 2);
          ctx.lineTo(sp.x, previewEndY);
          ctx.strokeStyle = hz.color;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 5]);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.restore();
        }

        // --- Zone label ---
        const lblAlpha = hasSelection ? (isSelected ? 1.0 : 0.3) : 0.7;
        ctx.save();
        ctx.globalAlpha = alpha * lblAlpha;

        // Label background
        const lblW = 56;
        const lblH = 28;
        const lblBgX = labelX - lblW / 2;
        const lblBgY = labelY - lblH / 2;

        if (isSelected) {
          ctx.fillStyle = 'rgba(26, 122, 109, 0.06)';
          roundedRect(ctx, lblBgX - 4, lblBgY - 2, lblW + 8, lblH + 4, 6);
          ctx.fill();
          ctx.strokeStyle = hz.color;
          ctx.lineWidth = 1.5;
          roundedRect(ctx, lblBgX - 4, lblBgY - 2, lblW + 8, lblH + 4, 6);
          ctx.stroke();
        }

        ctx.font = `bold 14px -apple-system, BlinkMacSystemFont, sans-serif`;
        ctx.fillStyle = isSelected ? hz.color : COLORS.ink;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`Zone ${zoneId}`, labelX, labelY);

        ctx.restore();
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      if (event.type !== 'click') return;

      // Check if click is on a zone label
      for (const hb of labelHitboxes) {
        if (
          event.x >= hb.x && event.x <= hb.x + hb.w &&
          event.y >= hb.y && event.y <= hb.y + hb.h
        ) {
          // Toggle selection
          if (selectedZone === hb.zoneIdx) {
            selectedZone = -1;
            state.selectedZone = null;
          } else {
            selectedZone = hb.zoneIdx;
            state.selectedZone = hb.zoneIdx;
          }
          return;
        }
      }

      // Click elsewhere: deselect
      selectedZone = -1;
      state.selectedZone = null;
    },
  };
}
