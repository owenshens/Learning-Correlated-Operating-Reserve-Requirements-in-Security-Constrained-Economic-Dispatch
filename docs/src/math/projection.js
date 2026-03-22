// === Projection Math ===
// Utilities for projecting 15D ellipsoids to 2D zone-exposure planes.
// Most heavy computation is precomputed in Python; this module handles
// interpolation and viewport mapping at runtime.

/**
 * Interpolate between two training snapshots' ellipse parameters.
 *
 * @param {object} snap1 - { semi_a, semi_b, inside_mask, coverage }
 * @param {object} snap2 - same structure
 * @param {number} t - interpolation factor [0, 1]
 * @returns {{ semi_a: number, semi_b: number, coverage: number }}
 */
export function interpolateEllipse(snap1, snap2, t) {
  return {
    semi_a: snap1.semi_a + (snap2.semi_a - snap1.semi_a) * t,
    semi_b: snap1.semi_b + (snap2.semi_b - snap1.semi_b) * t,
    coverage: snap1.coverage + (snap2.coverage - snap1.coverage) * t,
  };
}

/**
 * Compute a viewport mapping from MW coordinates to canvas pixels.
 * The ellipse and dots share this coordinate system.
 *
 * @param {number} canvasCx - center X on canvas (pixels)
 * @param {number} canvasCy - center Y on canvas (pixels)
 * @param {number} availableW - available width for the plot (pixels)
 * @param {number} availableH - available height for the plot (pixels)
 * @param {number} maxSemiA - largest semi-axis A to display (MW)
 * @param {number} maxSemiB - largest semi-axis B to display (MW)
 * @param {number} [padding=1.3] - padding factor (1.3 = 30% margin beyond ellipse)
 * @returns {{ cx, cy, scaleX, scaleY }}
 */
export function computeViewport(canvasCx, canvasCy, availableW, availableH, maxSemiA, maxSemiB, padding = 1.3) {
  // Scale so the largest ellipse fits within the available area
  const scaleX = (availableW / 2) / (maxSemiA * padding);
  const scaleY = (availableH / 2) / (maxSemiB * padding);
  // Use uniform scale to preserve aspect ratio
  const scale = Math.min(scaleX, scaleY);

  return {
    cx: canvasCx,
    cy: canvasCy,
    scaleX: scale,
    scaleY: scale,
  };
}
