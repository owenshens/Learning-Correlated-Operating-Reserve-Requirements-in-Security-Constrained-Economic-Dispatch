// === Scene 10: Method Comparison ===
// Four panels in a 2x2 grid, each showing the same 200 dots with different
// method ellipses. Uses real projected data from residual_samples.json.

import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';
import { drawResidualDots, drawProjectedEllipse } from '../components/residualDots.js';
import { computeViewport } from '../math/projection.js';

// Reserve data per method (from methods.json)
const RESERVES_BY_METHOD = {
  box:       [51.81, 48.40, 59.65, 65.45, 140.18, 38.85, 375.31, 295.68, 228.68, 259.43],
  samplecov: [50.96, 47.61, 57.20, 62.76, 131.63, 36.48, 383.45, 302.09, 234.01, 265.49],
  staticl:   [42.79, 39.97, 55.58, 60.98, 99.01, 27.44, 201.34, 158.62, 126.60, 143.63],
  contextual:[53.25, 49.75, 68.03, 74.65, 120.78, 33.47, 245.47, 193.39, 153.55, 174.20],
};

const METHOD_CONFIGS = [
  { key: 'box',        label: 'Box',                  color: COLORS.cobalt,
    cost: 99944, reserveCost: 9115, coverage: 0.986, reserveTotal: 1563 },
  { key: 'samplecov',  label: 'Sample Cov',           color: '#7B9FBF',
    cost: 100012, reserveCost: 9178, coverage: 0.980, reserveTotal: 1572 },
  { key: 'staticl',    label: 'Learned (Static)',      color: COLORS.teal,
    cost: 95471, reserveCost: 4805, coverage: 0.967, reserveTotal: 956 },
  { key: 'contextual', label: 'Learned (Contextual)',  color: COLORS.tealLight,
    cost: 96886, reserveCost: 6248, coverage: 0.983, reserveTotal: 1167 },
];

const bestCost = Math.min(...METHOD_CONFIGS.map(m => m.cost));

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

export function createScene10() {
  let elapsed = 0;
  let opacity = new AnimatedValue(0);
  let panelFadeIn = [
    new AnimatedValue(0),
    new AnimatedValue(0),
    new AnimatedValue(0),
    new AnimatedValue(0),
  ];

  // Data from state.residualData
  let samples = null;
  let methodEllipses = null;
  let maxSemiA = 150;
  let maxSemiB = 400;

  function loadData(state) {
    if (state.residualData && !samples) {
      samples = state.residualData.samples;
      methodEllipses = state.residualData.method_ellipses;
      if (methodEllipses) {
        maxSemiA = 0;
        maxSemiB = 0;
        for (const key of Object.keys(methodEllipses)) {
          maxSemiA = Math.max(maxSemiA, methodEllipses[key].semi_a);
          maxSemiB = Math.max(maxSemiB, methodEllipses[key].semi_b);
        }
      }
    }
  }

  function getPanelLayout(width, height) {
    const panelW = Math.min(340, (width - 80) / 2);
    const panelH = Math.min(300, (height - 100) / 2);
    const gapX = 16;
    const gapY = 16;
    const totalW = panelW * 2 + gapX;
    const totalH = panelH * 2 + gapY;
    const startX = (width - totalW) / 2;
    const startY = (height - totalH) / 2 + 10;

    return [
      { x: startX, y: startY, w: panelW, h: panelH },
      { x: startX + panelW + gapX, y: startY, w: panelW, h: panelH },
      { x: startX, y: startY + panelH + gapY, w: panelW, h: panelH },
      { x: startX + panelW + gapX, y: startY + panelH + gapY, w: panelW, h: panelH },
    ];
  }

  function drawPanel(ctx, panel, methodCfg, alpha, isSelected) {
    const { x, y, w, h } = panel;
    const mKey = methodCfg.key;

    // Panel background
    ctx.save();
    ctx.globalAlpha = alpha * 0.04;
    ctx.fillStyle = methodCfg.color;
    roundedRect(ctx, x, y, w, h, 8);
    ctx.fill();
    ctx.restore();

    // Panel border
    ctx.save();
    ctx.globalAlpha = alpha * (isSelected ? 0.8 : 0.2);
    ctx.strokeStyle = methodCfg.color;
    ctx.lineWidth = isSelected ? 2.5 : 1;
    roundedRect(ctx, x, y, w, h, 8);
    ctx.stroke();
    ctx.restore();

    // Selected glow
    if (isSelected) {
      ctx.save();
      ctx.globalAlpha = alpha * 0.15;
      ctx.shadowColor = methodCfg.color;
      ctx.shadowBlur = 15;
      ctx.strokeStyle = methodCfg.color;
      ctx.lineWidth = 2;
      roundedRect(ctx, x, y, w, h, 8);
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.restore();
    }

    // Panel label
    Renderer.drawText(ctx, methodCfg.label, x + w / 2, y + 14, {
      font: 'bold 13px Inter, sans-serif',
      color: methodCfg.color,
      align: 'center',
      baseline: 'top',
      alpha: alpha * 0.9,
    });

    // --- Dots + ellipse area ---
    const plotCx = x + w / 2;
    const plotCy = y + h * 0.38;
    const plotW = w * 0.85;
    const plotH = h * 0.42;

    // Clip to panel interior
    ctx.save();
    ctx.beginPath();
    roundedRect(ctx, x + 2, y + 30, w - 4, h * 0.5, 4);
    ctx.clip();

    const viewport = computeViewport(plotCx, plotCy, plotW, plotH, maxSemiA, maxSemiB, 1.4);

    // Draw dots
    const mData = methodEllipses ? methodEllipses[mKey] : null;
    if (samples && mData) {
      drawResidualDots(ctx, samples, mData.inside_mask, viewport, {
        alpha: alpha * 0.7,
        dotRadius: 2,
      });
    }

    // Draw method ellipse
    if (mData) {
      drawProjectedEllipse(ctx, mData.semi_a, mData.semi_b, viewport, {
        fillColor: null,
        strokeColor: methodCfg.color,
        lineWidth: 1.8,
        alpha: alpha * 0.75,
      });
    }

    ctx.restore();

    // --- Cost + coverage info ---
    const isBest = methodCfg.cost === bestCost;
    const infoY = y + h * 0.66;

    const costStr = `$${methodCfg.cost.toLocaleString()}/hr`;
    Renderer.drawText(ctx, costStr, x + w / 2, infoY, {
      font: `bold 15px Inter, sans-serif`,
      color: isBest ? COLORS.teal : COLORS.ink,
      align: 'center',
      baseline: 'middle',
      alpha: alpha * (isBest ? 1.0 : 0.7),
    });

    if (isBest) {
      Renderer.drawText(ctx, 'BEST', x + w / 2 + 72, infoY, {
        font: 'bold 10px Inter, sans-serif',
        color: COLORS.teal,
        align: 'left',
        baseline: 'middle',
        alpha: alpha * 0.7,
      });
    }

    // Coverage
    const covStr = `Coverage: ${(methodCfg.coverage * 100).toFixed(1)}%`;
    Renderer.drawText(ctx, covStr, x + w / 2, infoY + 18, {
      font: '11px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'middle',
      alpha: alpha * 0.6,
    });

    Renderer.drawText(ctx, `Reserve: $${methodCfg.reserveCost.toLocaleString()}`, x + w / 2, infoY + 33, {
      font: '11px Inter, sans-serif',
      color: COLORS.inkLight,
      align: 'center',
      baseline: 'middle',
      alpha: alpha * 0.5,
    });

    // --- Mini reserve bars ---
    const reserves = RESERVES_BY_METHOD[mKey];
    if (reserves) {
      const barAreaY = y + h * 0.82;
      const barAreaH = h * 0.14;
      const barW = Math.max(5, (w - 40) / 10 - 2);
      const barGap = 2;
      const barTotalW = 10 * barW + 9 * barGap;
      const barStartX = x + (w - barTotalW) / 2;
      const maxR = 400;

      for (let i = 0; i < 10; i++) {
        const bx = barStartX + i * (barW + barGap);
        const rH = (reserves[i] / maxR) * barAreaH;
        Renderer.drawBar(ctx, bx, barAreaY + barAreaH, barW, rH, {
          color: methodCfg.color, alpha: alpha * 0.45, radius: 1,
        });
      }
      Renderer.drawLine(ctx, barStartX - 2, barAreaY + barAreaH, barStartX + barTotalW + 2, barAreaY + barAreaH, {
        color: COLORS.ink, lineWidth: 0.5, alpha: alpha * 0.15,
      });
    }
  }

  let timeoutIds = [];

  return {
    enter(state) {
      elapsed = 0;
      opacity.snap(0);
      opacity.set(1);

      loadData(state);

      for (let i = 0; i < 4; i++) {
        panelFadeIn[i].snap(0);
        timeoutIds.push(setTimeout(() => panelFadeIn[i].set(1), i * 200));
      }
    },

    exit(state) {
      timeoutIds.forEach(id => clearTimeout(id));
      timeoutIds = [];
    },

    update(dt, state) {
      elapsed += dt;
      opacity.update(dt);
      for (let i = 0; i < 4; i++) {
        panelFadeIn[i].update(dt);
      }
      loadData(state);
    },

    render(ctx, state, width, height) {
      const alpha = opacity.get();
      if (alpha < 0.001) return;

      ctx.save();
      ctx.globalAlpha = alpha;

      const panels = getPanelLayout(width, height);

      for (let i = 0; i < 4; i++) {
        const method = METHOD_CONFIGS[i];
        const panel = panels[i];
        const pAlpha = panelFadeIn[i].get();
        const isSelected = state.method === method.key;
        drawPanel(ctx, panel, method, pAlpha, isSelected);
      }

      // Hint at bottom
      const hintAlpha = 0.25 + 0.1 * Math.sin(elapsed * 2);
      Renderer.drawText(ctx, 'Click a panel to select method', width / 2, height - 16, {
        font: '11px Inter, sans-serif',
        color: COLORS.inkLight,
        align: 'center',
        baseline: 'bottom',
        alpha: hintAlpha,
      });

      ctx.restore();
    },

    onInteraction(event, state) {
      if (event.type !== 'click') return;

      const width = window.innerWidth;
      const height = window.innerHeight;
      const panels = getPanelLayout(width, height);

      for (let i = 0; i < 4; i++) {
        const p = panels[i];
        if (event.x >= p.x && event.x <= p.x + p.w &&
            event.y >= p.y && event.y <= p.y + p.h) {
          state.method = METHOD_CONFIGS[i].key;
          break;
        }
      }
    },
  };
}
