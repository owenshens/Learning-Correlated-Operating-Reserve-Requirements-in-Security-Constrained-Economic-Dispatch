// === Composite Scene ===
// Merges two existing scenes into one with an internal phase transition.
// Phase 1 runs for `splitTime` seconds, then auto-transitions to Phase 2.

import { AnimatedValue } from '../../engine/timeline.js';

/**
 * Create a composite scene from two scene factories.
 *
 * @param {Function} factory1 - creates the Phase 1 scene
 * @param {Function} factory2 - creates the Phase 2 scene
 * @param {number} splitTime - seconds before auto-transitioning to Phase 2
 * @returns {object} scene interface { enter, exit, update, render, onInteraction }
 */
export function createCompositeScene(factory1, factory2, splitTime) {
  const scene1 = factory1();
  const scene2 = factory2();

  let elapsed = 0;
  let phase = 1; // 1 or 2
  let transitioned = false;
  let phase2Alpha = new AnimatedValue(0);

  return {
    enter(state) {
      elapsed = 0;
      phase = 1;
      transitioned = false;
      phase2Alpha.snap(0);
      scene1.enter(state);
    },

    exit(state) {
      if (phase === 1 && scene1.exit) scene1.exit(state);
      if (phase === 2 && scene2.exit) scene2.exit(state);
      // Also clean up the other phase in case it was entered
      if (transitioned && scene2.exit) scene2.exit(state);
    },

    update(dt, state) {
      elapsed += dt;
      phase2Alpha.update(dt);

      // Auto-transition to Phase 2
      if (!transitioned && elapsed >= splitTime) {
        transitioned = true;
        phase = 2;
        if (scene1.exit) scene1.exit(state);
        scene2.enter(state);
        phase2Alpha.set(1);
      }

      if (phase === 1) {
        scene1.update(dt, state);
      } else {
        scene2.update(dt, state);
      }
    },

    render(ctx, state, width, height) {
      if (phase === 1) {
        scene1.render(ctx, state, width, height);
      } else {
        // Crossfade: fade out scene 1, fade in scene 2
        const alpha2 = phase2Alpha.get();
        if (alpha2 < 0.99) {
          ctx.save();
          ctx.globalAlpha = 1 - alpha2;
          scene1.render(ctx, state, width, height);
          ctx.restore();
        }
        ctx.save();
        ctx.globalAlpha = alpha2;
        scene2.render(ctx, state, width, height);
        ctx.restore();
      }
    },

    onInteraction(event, state) {
      if (phase === 1 && scene1.onInteraction) {
        scene1.onInteraction(event, state);
      } else if (phase === 2 && scene2.onInteraction) {
        scene2.onInteraction(event, state);
      }
    },
  };
}
