// === Scene 03: Uncertainty Has Shape ===
// Shows 200 residual dots with ellipsoid morphing: Box -> SampleCov -> Learned.
// Uses real projected data from residual_samples.json.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeInOutCubic } from '../engine/timeline.js';
import { drawResidualDots, drawProjectedEllipse } from '../components/residualDots.js';
import { computeViewport } from '../math/projection.js';

const SHAPE_SEQUENCE = ['box', 'samplecov', 'staticl'];
const SHAPE_LABELS = {
  box: 'Box (diagonal)',
  samplecov: 'Sample Covariance',
  staticl: 'Learned (Static L)',
};

const MORPH_DURATION = 1.5;
const PAUSE_DURATION = 2.5;

export function createScene03() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);

  let currentShapeIndex = 0;
  let morphPhase = 'pause';
  let phaseTimer = 0;
  let morphProgress = 0;
  let labelAlpha = new AnimatedValue(1);
  let currentLabel = SHAPE_LABELS.box;

  // Interpolated ellipse params
  let currentSemiA = 0;
  let currentSemiB = 0;
  let currentInsideMask = null;
  let currentCoverage = 0;

  // Data from state.residualData
  let samples = null;
  let methodEllipses = null;

  function getMethodData(key) {
    if (!methodEllipses || !methodEllipses[key]) return null;
    return methodEllipses[key];
  }

  function setShapeImmediate(key) {
    const data = getMethodData(key);
    if (!data) return;
    currentSemiA = data.semi_a;
    currentSemiB = data.semi_b;
    currentInsideMask = data.inside_mask;
    currentCoverage = data.coverage;
    currentLabel = SHAPE_LABELS[key] || key;
  }

  function startMorphTo(targetKey) {
    morphPhase = 'morphing';
    phaseTimer = 0;
    morphProgress = 0;
    labelAlpha.set(0);
    currentLabel = SHAPE_LABELS[targetKey] || targetKey;
  }

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);

      currentShapeIndex = 0;
      morphPhase = 'pause';
      phaseTimer = 0;
      morphProgress = 0;
      labelAlpha.snap(1);

      // Load residual data from state
      if (state.residualData) {
        samples = state.residualData.samples;
        methodEllipses = state.residualData.method_ellipses;
      }

      setShapeImmediate('box');
    },

    exit(state) {},

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);
      labelAlpha.update(dt);

      if (!methodEllipses) {
        if (state.residualData) {
          samples = state.residualData.samples;
          methodEllipses = state.residualData.method_ellipses;
          setShapeImmediate('box');
        }
        return;
      }

      // Explore mode: jump to selected method
      if (state.mode !== 'guided') {
        const key = state.method === 'contextual' ? 'staticl' : state.method;
        const validKey = SHAPE_SEQUENCE.includes(key) ? key : 'staticl';
        setShapeImmediate(validKey);
        return;
      }

      // Guided auto-sequence
      phaseTimer += dt;

      if (morphPhase === 'pause') {
        if (phaseTimer >= PAUSE_DURATION) {
          const nextIndex = currentShapeIndex + 1;
          if (nextIndex < SHAPE_SEQUENCE.length) {
            currentShapeIndex = nextIndex;
            startMorphTo(SHAPE_SEQUENCE[nextIndex]);
          }
        }
      } else if (morphPhase === 'morphing') {
        morphProgress = Math.min(1, phaseTimer / MORPH_DURATION);
        const t = easeInOutCubic(morphProgress);

        const prevKey = SHAPE_SEQUENCE[currentShapeIndex - 1] || 'box';
        const currKey = SHAPE_SEQUENCE[currentShapeIndex];
        const prev = getMethodData(prevKey);
        const curr = getMethodData(currKey);

        if (prev && curr) {
          currentSemiA = prev.semi_a + (curr.semi_a - prev.semi_a) * t;
          currentSemiB = prev.semi_b + (curr.semi_b - prev.semi_b) * t;
          currentCoverage = prev.coverage + (curr.coverage - prev.coverage) * t;
          // Snap mask at halfway
          currentInsideMask = t < 0.5 ? prev.inside_mask : curr.inside_mask;
        }

        if (morphProgress >= 1) {
          morphPhase = 'pause';
          phaseTimer = 0;
          setShapeImmediate(currKey);
          labelAlpha.set(1);
        }
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      // --- Layout ---
      const plotCx = width * 0.52;
      const plotCy = height * 0.45;
      const availW = width * 0.55;
      const availH = height * 0.65;

      // Compute viewport from the largest ellipse (box)
      const maxSemiA = methodEllipses ? Math.max(
        methodEllipses.box?.semi_a || 150,
        methodEllipses.samplecov?.semi_a || 140,
      ) : 150;
      const maxSemiB = methodEllipses ? Math.max(
        methodEllipses.box?.semi_b || 400,
        methodEllipses.samplecov?.semi_b || 400,
      ) : 400;

      const viewport = computeViewport(plotCx, plotCy, availW, availH, maxSemiA, maxSemiB, 1.4);

      // --- Draw residual dots ---
      if (samples && currentInsideMask) {
        drawResidualDots(ctx, samples, currentInsideMask, viewport, {
          alpha: alpha * 0.9,
          dotRadius: 3,
        });
      }

      // --- Draw current ellipse ---
      if (currentSemiA > 0 && currentSemiB > 0) {
        drawProjectedEllipse(ctx, currentSemiA, currentSemiB, viewport, {
          fillColor: 'rgba(26, 122, 109, 0.05)',
          strokeColor: COLORS.teal,
          lineWidth: 2.5,
          alpha: alpha * 0.85,
        });
      }

      // --- Axis labels ---
      ctx.save();
      ctx.globalAlpha = alpha * 0.35;
      ctx.font = '11px Inter, sans-serif';
      ctx.fillStyle = COLORS.inkLight;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText('Zone 5 Exposure (Solar+Load, MW)', plotCx, plotCy + availH / 2 + 8);

      ctx.save();
      ctx.translate(plotCx - availW / 2 - 14, plotCy);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText('Zone 7 Exposure (Wind+Load, MW)', 0, 0);
      ctx.restore();
      ctx.restore();

      // --- Shape label ---
      const lblAlpha = labelAlpha.get();
      if (lblAlpha > 0.01) {
        Renderer.drawText(ctx, currentLabel, plotCx, plotCy + availH / 2 - 16, {
          font: '15px Inter, sans-serif',
          color: COLORS.teal,
          align: 'center',
          baseline: 'top',
          alpha: alpha * lblAlpha * 0.8,
        });
      }

      // --- Coverage counter ---
      if (currentCoverage > 0) {
        const covText = `Coverage: ${(currentCoverage * 100).toFixed(1)}%`;
        Renderer.drawText(ctx, covText, plotCx + availW / 2 - 10, plotCy - availH / 2 + 10, {
          font: 'bold 14px Inter, sans-serif',
          color: COLORS.teal,
          align: 'right',
          baseline: 'top',
          alpha: alpha * 0.8,
        });
      }

      // --- Sequence dots ---
      if (state.mode === 'guided') {
        const dotY = plotCy + availH / 2 + 36;
        const dotSpacing = 16;
        const startDotX = plotCx - (SHAPE_SEQUENCE.length - 1) * dotSpacing / 2;

        for (let i = 0; i < SHAPE_SEQUENCE.length; i++) {
          const dx = startDotX + i * dotSpacing;
          const isCurrent = i === currentShapeIndex;
          const isPast = i < currentShapeIndex;

          ctx.beginPath();
          ctx.arc(dx, dotY, isCurrent ? 4 : 3, 0, Math.PI * 2);
          if (isCurrent) {
            ctx.fillStyle = COLORS.teal;
          } else if (isPast) {
            ctx.fillStyle = 'rgba(26, 122, 109, 0.4)';
          } else {
            ctx.fillStyle = 'rgba(45, 45, 45, 0.15)';
          }
          ctx.fill();
        }
      }

      // --- Legend ---
      const legX = plotCx + availW / 2 - 10;
      const legY = plotCy - availH / 2 + 32;

      ctx.save();
      ctx.globalAlpha = alpha * 0.7;
      // Inside dot
      ctx.fillStyle = COLORS.teal;
      ctx.beginPath();
      ctx.arc(legX - 80, legY, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.font = '10px Inter, sans-serif';
      ctx.fillStyle = COLORS.inkLight;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText('Inside', legX - 74, legY);

      // Outside dot
      ctx.fillStyle = COLORS.ember;
      ctx.beginPath();
      ctx.arc(legX - 30, legY, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = COLORS.inkLight;
      ctx.fillText('Outside', legX - 23, legY);
      ctx.restore();

      ctx.restore();
    },

    onInteraction(event, state) {
      if (event.type === 'click' && state.mode === 'guided') {
        // Click advances to next shape
        if (currentShapeIndex < SHAPE_SEQUENCE.length - 1) {
          currentShapeIndex++;
          startMorphTo(SHAPE_SEQUENCE[currentShapeIndex]);
        }
      }
    },
  };
}
