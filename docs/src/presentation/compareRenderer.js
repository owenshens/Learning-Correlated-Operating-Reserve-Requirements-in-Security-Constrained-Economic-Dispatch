import { COLORS, Renderer } from '../engine/renderer.js';

function roundedRect(ctx, x, y, width, height, radius = 24) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function alphaColor(hexColor, alpha) {
  const normalized = hexColor.replace('#', '');
  const red = parseInt(normalized.slice(0, 2), 16);
  const green = parseInt(normalized.slice(2, 4), 16);
  const blue = parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function formatCurrency(value) {
  return '$' + Math.round(value).toLocaleString('en-US');
}

function formatPercent(value) {
  return (value * 100).toFixed(1) + '%';
}

function formatWhole(value) {
  return Math.round(value).toLocaleString('en-US');
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1);
}

function std(values) {
  const avg = mean(values);
  const variance =
    values.reduce((sum, value) => sum + Math.pow(value - avg, 2), 0) / Math.max(values.length - 1, 1);
  return Math.sqrt(variance);
}

function invert2x2(matrix) {
  const [[a, b], [c, d]] = matrix;
  const det = a * d - b * c;
  return [
    [d / det, -b / det],
    [-c / det, a / det],
  ];
}

function gaugeScore(matrix, point) {
  const inverse = invert2x2(matrix);
  const x = inverse[0][0] * point.x + inverse[0][1] * point.y;
  const y = inverse[1][0] * point.x + inverse[1][1] * point.y;
  return Math.hypot(x, y);
}

function quantile(values, tau) {
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.max(0, Math.min(sorted.length - 1, Math.ceil(sorted.length * tau) - 1));
  return sorted[index];
}

function ellipseExtent(matrix, rho, steps = 96) {
  let maxAbsX = 0;
  let maxAbsY = 0;
  for (let step = 0; step <= steps; step++) {
    const angle = (step / steps) * Math.PI * 2;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const x = rho * (matrix[0][0] * cos + matrix[0][1] * sin);
    const y = rho * (matrix[1][0] * cos + matrix[1][1] * sin);
    maxAbsX = Math.max(maxAbsX, Math.abs(x));
    maxAbsY = Math.max(maxAbsY, Math.abs(y));
  }
  return { maxAbsX, maxAbsY };
}

function buildToyGeometry(samples, matrix, tau, label, accent) {
  const scores = samples.map((point) => gaugeScore(matrix, point));
  const rho = quantile(scores, tau);
  const insideMask = scores.map((score) => score <= rho);
  return { label, matrix, rho, insideMask, accent };
}

function getToyViewport(rect, extent) {
  const pad = 18;
  const width = rect.w - pad * 2;
  const height = rect.h - pad * 2;
  const scaleX = width / (extent.maxAbsX * 2.25);
  const scaleY = height / (extent.maxAbsY * 2.25);
  return {
    cx: rect.x + rect.w / 2,
    cy: rect.y + rect.h / 2 + 6,
    scale: Math.min(scaleX, scaleY),
  };
}

function drawToyDots(ctx, samples, insideMask, viewport, intro, accent) {
  ctx.save();
  for (let index = 0; index < samples.length; index++) {
    const sample = samples[index];
    const px = viewport.cx + sample.x * viewport.scale;
    const py = viewport.cy - sample.y * viewport.scale;
    const inside = insideMask[index];

    ctx.globalAlpha = inside ? 0.28 + intro * 0.22 : 0.7 * intro;
    ctx.fillStyle = inside ? alphaColor(accent, 0.9) : alphaColor(COLORS.ember, 0.95);
    ctx.beginPath();
    ctx.arc(px, py, inside ? 2.8 : 3.3, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawChartAxes(ctx, rect, viewport) {
  Renderer.drawLine(ctx, rect.x + 10, viewport.cy, rect.x + rect.w - 10, viewport.cy, {
    color: COLORS.inkLight,
    alpha: 0.15,
    lineWidth: 1,
  });
  Renderer.drawLine(ctx, viewport.cx, rect.y + 10, viewport.cx, rect.y + rect.h - 10, {
    color: COLORS.inkLight,
    alpha: 0.15,
    lineWidth: 1,
  });
}

function drawToyCard(ctx, rect, geometry, samples, extent, intro) {
  roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 22);
  ctx.fillStyle = 'rgba(255,255,255,0.78)';
  ctx.fill();
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = alphaColor(geometry.accent, 0.18);
  ctx.stroke();

  const badgeWidth = 102;
  roundedRect(ctx, rect.x + 16, rect.y + 14, badgeWidth, 28, 14);
  ctx.fillStyle = alphaColor(geometry.accent, 0.12);
  ctx.fill();

  Renderer.drawText(ctx, geometry.label, rect.x + 18, rect.y + 29, {
    font: '700 14px "Manrope", sans-serif',
    color: geometry.accent,
    align: 'left',
    baseline: 'middle',
  });

  Renderer.drawText(ctx, 'τ = 95%', rect.x + rect.w - 18, rect.y + 29, {
    font: '600 12px "Manrope", sans-serif',
    color: COLORS.inkLight,
    align: 'right',
    baseline: 'middle',
  });

  const chartRect = { x: rect.x + 14, y: rect.y + 56, w: rect.w - 28, h: rect.h - 118 };
  const viewport = getToyViewport(chartRect, extent);

  ctx.save();
  roundedRect(ctx, chartRect.x, chartRect.y, chartRect.w, chartRect.h, 16);
  ctx.clip();
  drawChartAxes(ctx, chartRect, viewport);
  drawToyDots(ctx, samples, geometry.insideMask, viewport, intro, geometry.accent);
  Renderer.drawEllipse(ctx, viewport.cx, viewport.cy, geometry.matrix, viewport.scale * geometry.rho, {
    strokeColor: geometry.accent,
    fillColor: alphaColor(geometry.accent, 0.08),
    lineWidth: 2.4,
    alpha: 0.95,
  });
  ctx.restore();

  Renderer.drawText(ctx, geometry.label === 'Independent' ? 'Axis-aligned' : 'Correlation-aware', rect.x + 18, rect.y + rect.h - 24, {
    font: '600 12px "Manrope", sans-serif',
    color: COLORS.ink,
    align: 'left',
    baseline: 'middle',
    alpha: 0.9,
  });
}

function drawMethodCard(ctx, rect, label, accent, stats, intro) {
  roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 24);
  ctx.fillStyle = 'rgba(255,255,255,0.8)';
  ctx.fill();
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = alphaColor(accent, 0.18);
  ctx.stroke();

  Renderer.drawText(ctx, label, rect.x + 18, rect.y + 28, {
    font: '700 15px "Manrope", sans-serif',
    color: accent,
    align: 'left',
    baseline: 'middle',
  });
  Renderer.drawText(ctx, 'τ = 95%', rect.x + rect.w - 18, rect.y + 28, {
    font: '600 12px "Manrope", sans-serif',
    color: COLORS.inkLight,
    align: 'right',
    baseline: 'middle',
  });

  const countUp = easeOutCubic(intro);
  const rows = [
    ['Cost', formatCurrency(stats.cost * countUp)],
    ['Total reserve', `${formatWhole(stats.reserve_total * countUp)} MW`],
    ['Test coverage', formatPercent(stats.coverage)],
  ];

  rows.forEach(([rowLabel, value], index) => {
    const top = rect.y + 62 + index * 40;
    Renderer.drawText(ctx, rowLabel, rect.x + 18, top, {
      font: '600 12px "Manrope", sans-serif',
      color: COLORS.inkLight,
      align: 'left',
      baseline: 'middle',
    });
    Renderer.drawText(ctx, value, rect.x + rect.w - 18, top, {
      font: '700 14px "Manrope", sans-serif',
      color: COLORS.ink,
      align: 'right',
      baseline: 'middle',
    });
  });
}

export class CompareRenderer {
  constructor(data) {
    this.storyToy = data.storyToy;
    this.methods = data.methods.methods;
    this.elapsed = 0;
    this.introProgress = 0;

    const samples = this.storyToy.samples || [];
    const learnedRecord = this.storyToy.iterations?.[0] || {};
    const xs = samples.map((sample) => sample.x);
    const ys = samples.map((sample) => sample.y);

    this.toySamples = samples;
    this.tauTarget = this.storyToy.tau_target ?? 0.95;
    this.independentGeometry = buildToyGeometry(
      samples,
      [
        [std(xs), 0],
        [0, std(ys)],
      ],
      this.tauTarget,
      'Independent',
      COLORS.cobalt,
    );
    this.learnedGeometry = buildToyGeometry(
      samples,
      learnedRecord.L_2d || [
        [1.5, 0],
        [0.6, 1.1],
      ],
      this.tauTarget,
      'Learned',
      COLORS.teal,
    );

    const independentExtent = ellipseExtent(this.independentGeometry.matrix, this.independentGeometry.rho);
    const learnedExtent = ellipseExtent(this.learnedGeometry.matrix, this.learnedGeometry.rho);
    const sampleExtent = samples.reduce(
      (extent, sample) => ({
        maxAbsX: Math.max(extent.maxAbsX, Math.abs(sample.x)),
        maxAbsY: Math.max(extent.maxAbsY, Math.abs(sample.y)),
      }),
      { maxAbsX: 0, maxAbsY: 0 },
    );

    this.toyExtent = {
      maxAbsX: Math.max(independentExtent.maxAbsX, learnedExtent.maxAbsX, sampleExtent.maxAbsX),
      maxAbsY: Math.max(independentExtent.maxAbsY, learnedExtent.maxAbsY, sampleExtent.maxAbsY),
    };

    this.baseline = this.methods.box;
    this.learned = this.methods.staticl;
  }

  enter() {
    this.elapsed = 0;
    this.introProgress = 0;
  }

  update(dt) {
    this.elapsed += dt;
    this.introProgress = Math.min(1, this.elapsed / 1.2);
  }

  render(ctx, width, height) {
    const intro = easeOutCubic(this.introProgress);
    const margin = Math.max(34, width * 0.026);
    const top = Math.max(128, height * 0.145);
    const bottom = Math.max(108, height * 0.14);
    const usableHeight = height - top - bottom;
    const leftWidth = width * 0.54;
    const gap = Math.max(20, width * 0.018);
    const rightWidth = width - margin * 2 - gap - leftWidth;

    const leftRect = { x: margin, y: top, w: leftWidth, h: usableHeight };
    const rightRect = { x: margin + leftWidth + gap, y: top, w: rightWidth, h: usableHeight };

    const backdrop = ctx.createLinearGradient(0, 0, width, height);
    backdrop.addColorStop(0, '#f3efe7');
    backdrop.addColorStop(0.55, '#fbf8f1');
    backdrop.addColorStop(1, '#efe8dc');
    ctx.fillStyle = backdrop;
    ctx.fillRect(0, 0, width, height);

    this.drawPanelFrame(ctx, leftRect, 'Toy geometry');
    this.drawPanelFrame(ctx, rightRect, 'Real dispatch');

    const toyGap = 18;
    const toyCardWidth = (leftRect.w - 54 - toyGap) / 2;
    const toyCardHeight = leftRect.h - 152;
    const toyCardTop = leftRect.y + 86;
    const independentRect = { x: leftRect.x + 18, y: toyCardTop, w: toyCardWidth, h: toyCardHeight };
    const learnedRect = { x: independentRect.x + toyCardWidth + toyGap, y: toyCardTop, w: toyCardWidth, h: toyCardHeight };

    drawToyCard(ctx, independentRect, this.independentGeometry, this.toySamples, this.toyExtent, intro);
    drawToyCard(ctx, learnedRect, this.learnedGeometry, this.toySamples, this.toyExtent, intro);

    Renderer.drawArrow(
      ctx,
      leftRect.x + 42,
      leftRect.y + leftRect.h - 34,
      leftRect.x + leftRect.w - 42,
      leftRect.y + leftRect.h - 34,
      { color: COLORS.ember, lineWidth: 2, alpha: 0.38, headSize: 10 },
    );
    Renderer.drawText(ctx, 'Costly reserve direction', leftRect.x + leftRect.w / 2, leftRect.y + leftRect.h - 54, {
      font: '700 12px "Manrope", sans-serif',
      color: COLORS.ember,
      align: 'center',
      baseline: 'middle',
      alpha: 0.75,
    });

    const cardGap = 16;
    const methodCardWidth = (rightRect.w - 52 - cardGap) / 2;
    const methodCardHeight = 230;
    const methodTop = rightRect.y + 88;
    const baselineRect = { x: rightRect.x + 18, y: methodTop, w: methodCardWidth, h: methodCardHeight };
    const learnedRectCard = { x: baselineRect.x + methodCardWidth + cardGap, y: methodTop, w: methodCardWidth, h: methodCardHeight };

    drawMethodCard(ctx, baselineRect, 'Independent baseline', COLORS.cobalt, this.baseline, intro);
    drawMethodCard(ctx, learnedRectCard, 'Learned static ellipsoid', COLORS.teal, this.learned, intro);

    const deltaCost = this.baseline.cost - this.learned.cost;
    const deltaReserve = 1 - this.learned.reserve_total / this.baseline.reserve_total;
    const ribbonRect = { x: rightRect.x + 18, y: methodTop + methodCardHeight + 22, w: rightRect.w - 36, h: 84 };
    roundedRect(ctx, ribbonRect.x, ribbonRect.y, ribbonRect.w, ribbonRect.h, 20);
    ctx.fillStyle = 'rgba(18, 84, 75, 0.08)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(18, 84, 75, 0.12)';
    ctx.lineWidth = 1.1;
    ctx.stroke();
    Renderer.drawText(ctx, 'Learned vs independent', ribbonRect.x + 18, ribbonRect.y + 24, {
      font: '700 13px "Manrope", sans-serif',
      color: COLORS.inkLight,
      align: 'left',
      baseline: 'middle',
    });
    Renderer.drawText(ctx, `−${formatCurrency(deltaCost)} / hr`, ribbonRect.x + 18, ribbonRect.y + 56, {
      font: '700 24px "Manrope", sans-serif',
      color: COLORS.teal,
      align: 'left',
      baseline: 'middle',
    });
    Renderer.drawText(ctx, `−${Math.round(deltaReserve * 100)}% reserve`, ribbonRect.x + ribbonRect.w - 18, ribbonRect.y + 56, {
      font: '700 24px "Manrope", sans-serif',
      color: COLORS.teal,
      align: 'right',
      baseline: 'middle',
    });
  }

  drawPanelFrame(ctx, rect, title) {
    roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 30);
    ctx.fillStyle = 'rgba(255,255,255,0.62)';
    ctx.fill();
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = 'rgba(38, 54, 74, 0.08)';
    ctx.stroke();

    Renderer.drawText(ctx, title, rect.x + 20, rect.y + 30, {
      font: '700 18px "Manrope", sans-serif',
      color: COLORS.ink,
      align: 'left',
      baseline: 'middle',
    });
  }
}
