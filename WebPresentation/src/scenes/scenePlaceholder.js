// === Placeholder Scene Factory ===
// Creates stub scenes that display scene number and title.
// These will be replaced by real scene implementations.

import { Renderer, COLORS } from '../engine/renderer.js';

export function createPlaceholderScene(index, title) {
  let opacity = 0;
  let elapsed = 0;

  return {
    enter(state) {
      opacity = 0;
      elapsed = 0;
    },

    exit(state) {
      // cleanup if needed
    },

    update(dt, state) {
      elapsed += dt;
      opacity = Math.min(opacity + dt * 2, 1); // fade in over 0.5s
    },

    render(ctx, state, width, height) {
      ctx.save();
      ctx.globalAlpha = opacity;

      // Scene number — large, faint
      const numStr = String(index + 1).padStart(2, '0');
      ctx.font = `200 120px 'Crimson Pro', serif`;
      ctx.fillStyle = COLORS.ink;
      ctx.globalAlpha = opacity * 0.06;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(numStr, width / 2, height / 2 - 20);

      // Title
      ctx.globalAlpha = opacity * 0.3;
      ctx.font = `400 22px 'Crimson Pro', serif`;
      ctx.fillStyle = COLORS.ink;
      ctx.fillText(title, width / 2, height / 2 + 50);

      // Subtle decorative circle
      ctx.globalAlpha = opacity * 0.08;
      ctx.strokeStyle = COLORS.teal;
      ctx.lineWidth = 1;
      const r = 100 + Math.sin(elapsed * 0.5) * 10;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, r, 0, Math.PI * 2);
      ctx.stroke();

      ctx.restore();
    },

    onInteraction(event, state) {
      // placeholder — no interaction
    },
  };
}
