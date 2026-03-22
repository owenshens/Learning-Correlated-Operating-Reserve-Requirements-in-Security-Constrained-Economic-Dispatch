// === Residual Dots Component ===
// Renders 200 projected residual samples as dots with inside/outside coloring.
// Used by scenes that show the uncertainty ellipsoid with data coverage.

import { COLORS } from '../engine/renderer.js';

/**
 * Draw residual dots on canvas.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<{x: number, y: number}>} samples - projected (x, y) positions in MW
 * @param {boolean[]} insideMask - true = inside ellipsoid, false = outside
 * @param {object} viewport - { cx, cy, scaleX, scaleY } mapping MW coords to pixels
 * @param {object} [opts] - { alpha, dotRadius, fadeProgress }
 */
export function drawResidualDots(ctx, samples, insideMask, viewport, opts = {}) {
  const {
    alpha = 1.0,
    dotRadius = 3,
    fadeProgress = 1.0, // 0-1 for animation; 1 = fully visible
  } = opts;

  if (!samples || samples.length === 0) return;

  const { cx, cy, scaleX, scaleY } = viewport;

  ctx.save();

  // Batch by color for performance
  // Draw inside dots (teal) first, then outside dots (ember)
  const insideDots = [];
  const outsideDots = [];

  for (let i = 0; i < samples.length; i++) {
    const s = samples[i];
    const px = cx + s.x * scaleX;
    const py = cy - s.y * scaleY; // Y is inverted on canvas
    const inside = insideMask ? insideMask[i] : true;

    if (inside) {
      insideDots.push({ px, py });
    } else {
      outsideDots.push({ px, py });
    }
  }

  // Inside dots: teal
  ctx.globalAlpha = alpha * fadeProgress * 0.5;
  ctx.fillStyle = COLORS.teal;
  for (const d of insideDots) {
    ctx.beginPath();
    ctx.arc(d.px, d.py, dotRadius, 0, Math.PI * 2);
    ctx.fill();
  }

  // Outside dots: ember with slightly larger radius and higher alpha
  ctx.globalAlpha = alpha * fadeProgress * 0.8;
  ctx.fillStyle = COLORS.ember;
  for (const d of outsideDots) {
    ctx.beginPath();
    ctx.arc(d.px, d.py, dotRadius + 1, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

/**
 * Interpolate inside masks between two training steps.
 * A dot transitions from inside to outside (or vice versa) gradually.
 *
 * @param {boolean[]} mask1 - inside mask at step i
 * @param {boolean[]} mask2 - inside mask at step i+1
 * @param {number} t - interpolation factor 0-1
 * @returns {boolean[]} - interpolated mask (snaps at t=0.5)
 */
export function interpolateInsideMask(mask1, mask2, t) {
  if (!mask1 || !mask2) return mask1 || mask2 || [];
  return mask1.map((v, i) => t < 0.5 ? v : mask2[i]);
}

/**
 * Draw an axis-aligned ellipse (for the projected uncertainty set).
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} semiA - semi-axis in X direction (MW)
 * @param {number} semiB - semi-axis in Y direction (MW)
 * @param {object} viewport - { cx, cy, scaleX, scaleY }
 * @param {object} [opts]
 */
export function drawProjectedEllipse(ctx, semiA, semiB, viewport, opts = {}) {
  const {
    fillColor = 'rgba(26, 122, 109, 0.06)',
    strokeColor = COLORS.teal,
    lineWidth = 2,
    alpha = 0.85,
    dash = null,
  } = opts;

  const { cx, cy, scaleX, scaleY } = viewport;

  ctx.save();
  ctx.globalAlpha = alpha;

  const rx = Math.abs(semiA * scaleX);
  const ry = Math.abs(semiB * scaleY);

  if (fillColor) {
    ctx.fillStyle = fillColor;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  if (strokeColor) {
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = lineWidth;
    if (dash) ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.stroke();
    if (dash) ctx.setLineDash([]);
  }

  ctx.restore();
}
