// === Scene 13: Closing ===
// Clean split view: uncertainty ellipse on left, cost/reserve outcome on right.
// A single backward gradient arrow connects them with gentle pulsing particles.
// Calm, settled resolution.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue, easeOutCubic } from '../engine/timeline.js';

const LEARNED_L = [[0.233, 0], [0.032, 0.736]];
const DISPLAY_L = [[1.4, 0], [0.2, 1.0]]; // Normalized for nice visual

const COST_BEFORE = 99944;
const COST_AFTER = 95471;
const RESERVE_BEFORE = 9115;
const RESERVE_AFTER = 4805;

const COST_REDUCTION_PCT = '4.5%';
const RESERVE_REDUCTION_PCT = '47%';

export function createScene13() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let costCountUp = new AnimatedValue(0); // 0 to 1 for count-up animation
  let fadeInLeft = new AnimatedValue(0);
  let fadeInRight = new AnimatedValue(0);
  let fadeInArrow = new AnimatedValue(0);
  let fadeInStats = new AnimatedValue(0);
  let timeoutIds = [];

  // Particles cycling along the gradient arrow
  const NUM_PARTICLES = 3;
  let particles = [];
  for (let i = 0; i < NUM_PARTICLES; i++) {
    particles.push({
      progress: i / NUM_PARTICLES,
      speed: 0.12 + Math.random() * 0.04,
    });
  }

  function bezierPoint(p0, c1, c2, p3, t) {
    const mt = 1 - t;
    return {
      x: mt * mt * mt * p0.x + 3 * mt * mt * t * c1.x + 3 * mt * t * t * c2.x + t * t * t * p3.x,
      y: mt * mt * mt * p0.y + 3 * mt * mt * t * c1.y + 3 * mt * t * t * c2.y + t * t * t * p3.y,
    };
  }

  function getLayout(width, height) {
    const ellipseCx = width * 0.28;
    const ellipseCy = height * 0.42;
    const ellipseScale = Math.min(width * 0.08, 90);

    const outcomeCx = width * 0.72;
    const outcomeCy = height * 0.42;

    // Arrow from right to left (gradient flows backward: outcome -> shape)
    const arrowStart = { x: outcomeCx - 60, y: outcomeCy };
    const arrowEnd = { x: ellipseCx + ellipseScale + 30, y: ellipseCy };
    const ctrl1 = { x: arrowStart.x - 40, y: arrowStart.y - 60 };
    const ctrl2 = { x: arrowEnd.x + 40, y: arrowEnd.y - 60 };

    return { ellipseCx, ellipseCy, ellipseScale, outcomeCx, outcomeCy, arrowStart, arrowEnd, ctrl1, ctrl2 };
  }

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);
      costCountUp.snap(0);
      fadeInLeft.snap(0);
      fadeInRight.snap(0);
      fadeInArrow.snap(0);
      fadeInStats.snap(0);

      // Staggered reveal
      timeoutIds.push(setTimeout(() => fadeInLeft.set(1), 200));
      timeoutIds.push(setTimeout(() => fadeInRight.set(1), 600));
      timeoutIds.push(setTimeout(() => fadeInArrow.set(1), 1000));
      timeoutIds.push(setTimeout(() => {
        costCountUp.set(1);
        fadeInStats.set(1);
      }, 1400));
    },

    exit(state) {
      timeoutIds.forEach(id => clearTimeout(id));
      timeoutIds = [];
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);
      costCountUp.update(dt);
      fadeInLeft.update(dt);
      fadeInRight.update(dt);
      fadeInArrow.update(dt);
      fadeInStats.update(dt);

      // Update particles
      for (const p of particles) {
        p.progress += p.speed * dt;
        if (p.progress > 1) p.progress -= 1;
      }
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      const layout = getLayout(width, height);
      const { ellipseCx, ellipseCy, ellipseScale, outcomeCx, outcomeCy, arrowStart, arrowEnd, ctrl1, ctrl2 } = layout;

      // ==============================
      // LEFT SIDE: Uncertainty ellipse
      // ==============================
      {
        const leftAlpha = fadeInLeft.get();
        if (leftAlpha > 0.01) {
          ctx.save();
          ctx.globalAlpha = alpha * leftAlpha;

          // Subtle background circle
          ctx.beginPath();
          ctx.arc(ellipseCx, ellipseCy, ellipseScale * 1.8, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(26, 122, 109, 0.02)';
          ctx.fill();

          // The learned ellipse
          Renderer.drawEllipse(ctx, ellipseCx, ellipseCy, DISPLAY_L, ellipseScale, {
            fillColor: 'rgba(26, 122, 109, 0.08)',
            strokeColor: COLORS.teal,
            lineWidth: 2,
            alpha: 0.85,
          });

          // Label
          Renderer.drawText(ctx, 'Uncertainty Shape', ellipseCx, ellipseCy + ellipseScale + 30, {
            font: '13px Inter, sans-serif',
            color: COLORS.teal,
            align: 'center',
            baseline: 'top',
            alpha: 0.6,
          });

          Renderer.drawText(ctx, 'Learned', ellipseCx, ellipseCy + ellipseScale + 48, {
            font: 'italic 11px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'center',
            baseline: 'top',
            alpha: 0.4,
          });

          ctx.restore();
        }
      }

      // ==============================
      // GRADIENT ARROW (right to left)
      // ==============================
      {
        const arrowAlpha = fadeInArrow.get();
        if (arrowAlpha > 0.01) {
          ctx.save();
          ctx.globalAlpha = alpha * arrowAlpha;

          // Draw bezier path
          ctx.beginPath();
          ctx.moveTo(arrowStart.x, arrowStart.y);
          ctx.bezierCurveTo(ctrl1.x, ctrl1.y, ctrl2.x, ctrl2.y, arrowEnd.x, arrowEnd.y);
          ctx.strokeStyle = COLORS.ember;
          ctx.lineWidth = 1.5;
          ctx.globalAlpha = alpha * arrowAlpha * 0.2;
          ctx.stroke();
          ctx.globalAlpha = alpha * arrowAlpha;

          // Arrowhead at the end (pointing left toward ellipse)
          const tipT = 0.98;
          const nearTipT = 0.95;
          const tip = bezierPoint(arrowStart, ctrl1, ctrl2, arrowEnd, 1.0);
          const nearTip = bezierPoint(arrowStart, ctrl1, ctrl2, arrowEnd, nearTipT);
          const angle = Math.atan2(tip.y - nearTip.y, tip.x - nearTip.x);
          const headSize = 8;

          ctx.beginPath();
          ctx.moveTo(tip.x, tip.y);
          ctx.lineTo(
            tip.x - headSize * Math.cos(angle - Math.PI / 6),
            tip.y - headSize * Math.sin(angle - Math.PI / 6)
          );
          ctx.lineTo(
            tip.x - headSize * Math.cos(angle + Math.PI / 6),
            tip.y - headSize * Math.sin(angle + Math.PI / 6)
          );
          ctx.closePath();
          ctx.fillStyle = COLORS.ember;
          ctx.globalAlpha = alpha * arrowAlpha * 0.5;
          ctx.fill();

          // Particles along the curve
          const pulsePhase = Math.sin(elapsed * Math.PI / 2) * 0.5 + 0.5; // gentle pulse every 4s
          for (const p of particles) {
            const pos = bezierPoint(arrowStart, ctrl1, ctrl2, arrowEnd, p.progress);
            const pAlpha = 0.3 + 0.4 * pulsePhase;

            // Glow
            ctx.globalAlpha = alpha * arrowAlpha * pAlpha * 0.3;
            const grad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, 8);
            grad.addColorStop(0, COLORS.ember);
            grad.addColorStop(1, 'rgba(232, 118, 58, 0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
            ctx.fill();

            // Core dot
            ctx.globalAlpha = alpha * arrowAlpha * pAlpha;
            ctx.fillStyle = COLORS.ember;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 2.5, 0, Math.PI * 2);
            ctx.fill();
          }

          // Label on arrow
          const midPoint = bezierPoint(arrowStart, ctrl1, ctrl2, arrowEnd, 0.5);
          ctx.globalAlpha = alpha * arrowAlpha * 0.45;
          Renderer.drawText(ctx, 'gradient', midPoint.x, midPoint.y - 18, {
            font: 'italic 11px Inter, sans-serif',
            color: COLORS.ember,
            align: 'center',
            baseline: 'bottom',
            alpha: 1,
          });

          ctx.restore();
        }
      }

      // ==============================
      // RIGHT SIDE: Cost outcome
      // ==============================
      {
        const rightAlpha = fadeInRight.get();
        if (rightAlpha > 0.01) {
          ctx.save();
          ctx.globalAlpha = alpha * rightAlpha;

          // Background panel
          ctx.globalAlpha = alpha * rightAlpha * 0.03;
          ctx.fillStyle = COLORS.ink;
          const panelW = 200;
          const panelH = 130;
          const panelX = outcomeCx - panelW / 2;
          const panelY = outcomeCy - panelH / 2;
          roundedRect(ctx, panelX, panelY, panelW, panelH, 8);
          ctx.fill();
          ctx.globalAlpha = alpha * rightAlpha;

          // Cost transition display
          const countT = costCountUp.get();

          // "Before" cost (dimmed)
          Renderer.drawText(ctx, `$${COST_BEFORE.toLocaleString()}`, outcomeCx - 12, outcomeCy - 25, {
            font: '16px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'right',
            baseline: 'middle',
            alpha: 0.4,
          });

          // Arrow
          Renderer.drawText(ctx, '\u2192', outcomeCx, outcomeCy - 25, {
            font: '16px Inter, sans-serif',
            color: COLORS.ink,
            align: 'center',
            baseline: 'middle',
            alpha: 0.5,
          });

          // "After" cost (bright)
          const displayCost = Math.round(COST_BEFORE - (COST_BEFORE - COST_AFTER) * countT);
          Renderer.drawText(ctx, `$${displayCost.toLocaleString()}`, outcomeCx + 12, outcomeCy - 25, {
            font: 'bold 18px Inter, sans-serif',
            color: COLORS.teal,
            align: 'left',
            baseline: 'middle',
            alpha: Math.min(1, countT + 0.3),
          });

          // "/hr" suffix
          Renderer.drawText(ctx, '/hr', outcomeCx + 95, outcomeCy - 25, {
            font: '12px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'left',
            baseline: 'middle',
            alpha: 0.5,
          });

          // Label
          Renderer.drawText(ctx, 'Operating Cost', outcomeCx, outcomeCy - 50, {
            font: '12px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'center',
            baseline: 'bottom',
            alpha: 0.5,
          });

          ctx.restore();
        }
      }

      // ==============================
      // BOTTOM: Summary statistics
      // ==============================
      {
        const statsAlpha = fadeInStats.get();
        if (statsAlpha > 0.01) {
          ctx.save();
          ctx.globalAlpha = alpha * statsAlpha;

          const statsY = height * 0.72;

          // Cost reduction
          Renderer.drawText(ctx, COST_REDUCTION_PCT, width * 0.38, statsY, {
            font: 'bold 28px Inter, sans-serif',
            color: COLORS.teal,
            align: 'center',
            baseline: 'middle',
            alpha: 0.9,
          });
          Renderer.drawText(ctx, 'cost reduction', width * 0.38, statsY + 22, {
            font: '13px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'center',
            baseline: 'top',
            alpha: 0.55,
          });

          // Divider
          Renderer.drawLine(ctx, width * 0.5, statsY - 15, width * 0.5, statsY + 35, {
            color: COLORS.ink, lineWidth: 1, alpha: 0.1,
          });

          // Reserve savings
          Renderer.drawText(ctx, RESERVE_REDUCTION_PCT, width * 0.62, statsY, {
            font: 'bold 28px Inter, sans-serif',
            color: COLORS.ember,
            align: 'center',
            baseline: 'middle',
            alpha: 0.9,
          });
          Renderer.drawText(ctx, 'reserve savings', width * 0.62, statsY + 22, {
            font: '13px Inter, sans-serif',
            color: COLORS.inkLight,
            align: 'center',
            baseline: 'top',
            alpha: 0.55,
          });

          // Down arrow indicator
          const arrowX = width * 0.38;
          const arrowY2 = statsY - 18;
          ctx.beginPath();
          ctx.moveTo(arrowX, arrowY2);
          ctx.lineTo(arrowX - 5, arrowY2 - 8);
          ctx.lineTo(arrowX + 5, arrowY2 - 8);
          ctx.closePath();
          ctx.fillStyle = COLORS.teal;
          ctx.globalAlpha = alpha * statsAlpha * 0.5;
          ctx.fill();

          const arrowX2 = width * 0.62;
          ctx.beginPath();
          ctx.moveTo(arrowX2, arrowY2);
          ctx.lineTo(arrowX2 - 5, arrowY2 - 8);
          ctx.lineTo(arrowX2 + 5, arrowY2 - 8);
          ctx.closePath();
          ctx.fillStyle = COLORS.ember;
          ctx.globalAlpha = alpha * statsAlpha * 0.5;
          ctx.fill();

          ctx.restore();
        }
      }

      // ==============================
      // BOTTOM TEXT: Closing statement
      // ==============================
      {
        const stmtAlpha = fadeInStats.get();
        if (stmtAlpha > 0.3) {
          const normalizedAlpha = (stmtAlpha - 0.3) / 0.7;
          Renderer.drawText(ctx, 'Shape matters. Learning it end-to-end saves real cost.', width / 2, height * 0.88, {
            font: 'italic 14px Inter, sans-serif',
            color: COLORS.ink,
            align: 'center',
            baseline: 'middle',
            alpha: normalizedAlpha * 0.5,
          });
        }
      }

      ctx.restore();
    },

    onInteraction(event, state) {
      // No interaction for closing scene
    },
  };
}

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
