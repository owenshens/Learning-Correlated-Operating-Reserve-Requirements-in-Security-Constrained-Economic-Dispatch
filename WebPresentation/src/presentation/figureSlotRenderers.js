import { Renderer, COLORS } from '../engine/renderer.js';

const PAPER_TOP = '#f4efe3';
const PAPER_MID = '#fbf7ef';
const PAPER_BOTTOM = '#efe4cf';
const FIGURE_FONT = '"Manrope", "Aptos", "Segoe UI", sans-serif';

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function lerpMatrix(a, b, t) {
  const left = a || [[1, 0], [0, 1]];
  const right = b || left;
  return [
    [
      lerp(left[0]?.[0] ?? 1, right[0]?.[0] ?? left[0]?.[0] ?? 1, t),
      lerp(left[0]?.[1] ?? 0, right[0]?.[1] ?? left[0]?.[1] ?? 0, t),
    ],
    [
      lerp(left[1]?.[0] ?? 0, right[1]?.[0] ?? left[1]?.[0] ?? 0, t),
      lerp(left[1]?.[1] ?? 1, right[1]?.[1] ?? left[1]?.[1] ?? 1, t),
    ],
  ];
}

function ensureCanvasSize(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return { width: rect.width, height: rect.height, dpr };
}

function alphaColor(color, alpha) {
  const normalized = color.replace('#', '');
  const red = parseInt(normalized.slice(0, 2), 16);
  const green = parseInt(normalized.slice(2, 4), 16);
  const blue = parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function roundedRect(ctx, x, y, width, height, radius = 18) {
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

function getRecordRho(record) {
  return record?.rho_hat ?? record?.rho ?? 1;
}

function getRecordCoverage(record) {
  return record?.coverage_test ?? record?.coverage_cal ?? record?.coverage ?? 0;
}

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function getSequenceState(time, sequenceIndices = [], stepDuration = 1.8) {
  if (!sequenceIndices.length) {
    return { currentIndex: 0, nextIndex: 0, mix: 0 };
  }
  if (sequenceIndices.length === 1) {
    return { currentIndex: sequenceIndices[0], nextIndex: sequenceIndices[0], mix: 0 };
  }
  const cycle = time / stepDuration;
  const step = Math.floor(cycle) % sequenceIndices.length;
  const nextStep = (step + 1) % sequenceIndices.length;
  return {
    currentIndex: sequenceIndices[step],
    nextIndex: sequenceIndices[nextStep],
    mix: cycle - Math.floor(cycle),
  };
}

function drawPaperBackdrop(ctx, width, height) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, PAPER_TOP);
  gradient.addColorStop(0.55, PAPER_MID);
  gradient.addColorStop(1, PAPER_BOTTOM);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.04;
  for (let x = 0; x < width; x += 32) {
    Renderer.drawLine(ctx, x, 0, x, height, { color: COLORS.ink, alpha: 0.18 });
  }
  for (let y = 0; y < height; y += 32) {
    Renderer.drawLine(ctx, 0, y, width, y, { color: COLORS.ink, alpha: 0.14 });
  }
  ctx.restore();

  roundedRect(ctx, 0.5, 0.5, width - 1, height - 1, 16);
  ctx.fillStyle = 'rgba(255,255,255,0.2)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(120, 106, 82, 0.14)';
  ctx.lineWidth = 1;
  ctx.stroke();
}

function getEllipseExtents(record) {
  const L = record?.L_2d || [[1, 0], [0, 1]];
  const rho = getRecordRho(record);
  const row0 = L[0] || [1, 0];
  const row1 = L[1] || [0, 1];
  return {
    width: rho * Math.hypot(row0[0] || 0, row0[1] || 0),
    height: rho * Math.hypot(row1[0] || 0, row1[1] || 0),
  };
}

function getTraceExtents(trace, samples) {
  let maxX = 1;
  let maxY = 1;

  for (const sample of samples || []) {
    maxX = Math.max(maxX, Math.abs(sample.x));
    maxY = Math.max(maxY, Math.abs(sample.y));
  }

  for (const iteration of trace?.iterations || []) {
    const ellipseExtent = getEllipseExtents(iteration);
    maxX = Math.max(maxX, ellipseExtent.width);
    maxY = Math.max(maxY, ellipseExtent.height);
    for (const point of iteration.support_points_2d || []) {
      maxX = Math.max(maxX, Math.abs(point.x));
      maxY = Math.max(maxY, Math.abs(point.y));
    }
  }

  return { width: maxX, height: maxY };
}

function getShapeTransform(plotRect, trace, samples) {
  const extents = getTraceExtents(trace, samples);
  const scale = Math.min(
    plotRect.w / Math.max(extents.width * 2.2, 1),
    plotRect.h / Math.max(extents.height * 2.2, 1),
  );
  const center = {
    x: plotRect.x + plotRect.w * 0.52,
    y: plotRect.y + plotRect.h * 0.52,
  };
  return { center, scale };
}

function drawPlotPanel(ctx, rect) {
  ctx.save();
  roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 18);
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  ctx.fill();
  ctx.clip();
}

function drawShapeGrid(ctx, rect, center) {
  ctx.save();
  ctx.strokeStyle = 'rgba(45, 45, 45, 0.07)';
  ctx.lineWidth = 1;
  for (let i = -4; i <= 4; i++) {
    ctx.beginPath();
    ctx.moveTo(rect.x, center.y + i * 50);
    ctx.lineTo(rect.x + rect.w, center.y + i * 50);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(center.x + i * 50, rect.y);
    ctx.lineTo(center.x + i * 50, rect.y + rect.h);
    ctx.stroke();
  }
  Renderer.drawLine(ctx, rect.x, center.y, rect.x + rect.w, center.y, { color: COLORS.ink, alpha: 0.16 });
  Renderer.drawLine(ctx, center.x, rect.y, center.x, rect.y + rect.h, { color: COLORS.ink, alpha: 0.16 });
  ctx.restore();
}

function drawSamples(ctx, samples, insideMask, center, scale, pulse = 0) {
  if (!samples?.length) return;
  for (let index = 0; index < samples.length; index++) {
    const sample = samples[index];
    const inside = insideMask ? insideMask[index] : true;
    const x = center.x + sample.x * scale;
    const y = center.y - sample.y * scale;
    Renderer.drawParticle(
      ctx,
      x,
      y,
      inside ? 2.2 : 2.6,
      inside ? COLORS.teal : COLORS.ember,
      inside ? 0.28 + pulse * 0.12 : 0.44 + pulse * 0.14,
    );
  }
}

function drawSupportPoints(ctx, supportPoints, record, center, scale, pulse = 0) {
  const highlightedZones = new Set((record?.dominant_zones || []).slice(0, 3));
  for (const point of supportPoints || []) {
    const x = center.x + point.x * scale;
    const y = center.y - point.y * scale;
    const highlighted = highlightedZones.has(point.zone);
    Renderer.drawLine(ctx, center.x, center.y, x, y, {
      color: highlighted ? COLORS.ember : COLORS.cobalt,
      alpha: highlighted ? 0.38 : 0.15,
      lineWidth: highlighted ? 1.8 : 1,
      dash: highlighted ? null : [6, 6],
    });
    Renderer.drawGlow(ctx, x, y, highlighted ? 14 + pulse * 4 : 8, highlighted ? COLORS.ember : COLORS.cobalt, highlighted ? 0.44 + pulse * 0.16 : 0.22);
    Renderer.drawParticle(ctx, x, y, highlighted ? 4.2 : 2.6, highlighted ? COLORS.ember : COLORS.cobalt, highlighted ? 0.84 + pulse * 0.12 : 0.48);
    if (highlighted) {
      Renderer.drawText(ctx, `Z${point.zone}`, x + 8, y - 8, {
        font: `11px ${FIGURE_FONT}`,
        color: COLORS.ink,
        align: 'left',
        baseline: 'middle',
        alpha: 0.84,
      });
    }
  }
}

function ellipsePoint(center, matrix, rho, scale, angle, scaleFactor = 1) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return {
    x: center.x + rho * scale * scaleFactor * ((matrix[0][0] * cos) + (matrix[0][1] * sin)),
    y: center.y - rho * scale * scaleFactor * ((matrix[1][0] * cos) + (matrix[1][1] * sin)),
  };
}

function drawCoverageCorrectionCue(ctx, record, center, scale, rho, pulse = 0) {
  const target = record?.tau_target ?? 0.95;
  const coverage = record?.coverage_cal ?? getRecordCoverage(record);
  const gap = target - coverage;
  const direction = gap >= 0 ? 1 : -1;
  const gapStrength = clamp(Math.abs(gap) / 0.03, 0, 1);
  const gradShare = clamp(
    (record?.grad_rho_norm || 0) / Math.max((record?.grad_shape_norm || 0) + (record?.grad_rho_norm || 0), 1e-9),
    0,
    1,
  );
  const strength = gapStrength * (0.35 + 0.65 * gradShare);
  if (strength <= 0.04) return;

  const correctionScale = 1 + direction * 0.09 * strength;
  Renderer.drawEllipse(ctx, center.x, center.y, record?.L_2d || [[1, 0], [0, 1]], scale * rho * correctionScale, {
    strokeColor: COLORS.tealLight,
    fillColor: null,
    lineWidth: 1.25,
    alpha: 0.16 + strength * (0.14 + pulse * 0.12),
    dash: [5, 6],
  });

  for (const angle of [-1.15, -0.2, 0.75, 1.9]) {
    const start = ellipsePoint(center, record?.L_2d || [[1, 0], [0, 1]], rho, scale, angle, 1);
    const end = ellipsePoint(center, record?.L_2d || [[1, 0], [0, 1]], rho, scale, angle, correctionScale);
    Renderer.drawArrow(ctx, start.x, start.y, end.x, end.y, {
      color: COLORS.tealLight,
      alpha: 0.24 + strength * 0.38,
      lineWidth: 1.4,
      headSize: 6,
    });
  }
}

function drawNextShapeGhost(ctx, record, center, scale, rho, pulse = 0) {
  if (!record?.L_next_2d) return;
  Renderer.drawEllipse(ctx, center.x, center.y, record.L_next_2d, scale * rho, {
    strokeColor: COLORS.ember,
    fillColor: null,
    lineWidth: 1.35,
    alpha: 0.18 + pulse * 0.14,
    dash: [4, 5],
  });
}

function drawReserveForceArrows(ctx, record, center, scale, pulse = 0) {
  const contributions = (record?.zone_contributions || [])
    .slice()
    .sort((left, right) => right.total_contribution - left.total_contribution)
    .slice(0, 3);
  if (!contributions.length) return;

  const supportByZone = new Map((record?.support_points_2d || []).map((point) => [point.zone, point]));
  const maxContribution = Math.max(...contributions.map((row) => row.total_contribution), 1e-9);

  contributions.forEach((row, rank) => {
    const point = supportByZone.get(row.zone);
    if (!point) return;
    const x = center.x + point.x * scale;
    const y = center.y - point.y * scale;
    const dx = x - center.x;
    const dy = y - center.y;
    const norm = Math.hypot(dx, dy);
    if (norm < 1e-6) return;
    const ux = dx / norm;
    const uy = dy / norm;
    const length = 12 + 24 * clamp(row.total_contribution / maxContribution, 0.15, 1) + pulse * 4;
    const alpha = 0.78 - rank * 0.14;

    Renderer.drawArrow(ctx, x, y, x + ux * length, y + uy * length, {
      color: COLORS.ember,
      alpha,
      lineWidth: rank === 0 ? 2.1 : 1.7,
      headSize: 7,
    });
  });
}

function drawShapeLegend(ctx, rect) {
  Renderer.drawText(
    ctx,
    'Orange arrows: reserve pull  ·  Teal cue: coverage correction  ·  dotted: one-step shape preview',
    rect.x + 18,
    rect.y + rect.h - 18,
    {
      font: `11px ${FIGURE_FONT}`,
      color: COLORS.inkLight,
      align: 'left',
      baseline: 'middle',
      alpha: 0.88,
    },
  );
}

function drawLineChart(ctx, rect, xs, ys, options) {
  if (!xs.length || !ys.length) return;
  const minX = Math.min(...xs, options.currentX ?? Infinity);
  const maxX = Math.max(...xs, options.currentX ?? -Infinity);
  const minY = 0;
  const maxY = 1;

  drawPlotPanel(ctx, rect);

  if (options.targetY !== undefined) {
    const y = rect.y + (1 - (options.targetY - minY) / (maxY - minY)) * rect.h;
    Renderer.drawLine(ctx, rect.x + 8, y, rect.x + rect.w - 8, y, {
      color: COLORS.cobalt,
      alpha: 0.28,
      dash: [6, 5],
    });
  }

  ctx.beginPath();
  for (let index = 0; index < xs.length; index++) {
    const x = rect.x + ((xs[index] - minX) / Math.max(maxX - minX, 1e-9)) * rect.w;
    const y = rect.y + (1 - (ys[index] - minY) / (maxY - minY)) * rect.h;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = COLORS.cobalt;
  ctx.lineWidth = 2;
  ctx.stroke();

  const currentX = options.currentX ?? xs[xs.length - 1];
  const currentIndex = xs.findIndex((value) => value >= currentX);
  const yValue = currentIndex >= 0 ? ys[currentIndex] : ys[ys.length - 1];
  const cx = rect.x + ((currentX - minX) / Math.max(maxX - minX, 1e-9)) * rect.w;
  const cy = rect.y + (1 - (yValue - minY) / (maxY - minY)) * rect.h;
  Renderer.drawGlow(ctx, cx, cy, 10, COLORS.ember, 0.4);
  Renderer.drawParticle(ctx, cx, cy, 4, COLORS.ember, 0.9);

  Renderer.drawText(ctx, options.label, rect.x + 10, rect.y + 14, {
    font: `12px ${FIGURE_FONT}`,
    color: COLORS.inkLight,
    align: 'left',
    baseline: 'middle',
  });
  if (options.targetLabel) {
    Renderer.drawText(ctx, options.targetLabel, rect.x + rect.w - 10, rect.y + 14, {
      font: `12px ${FIGURE_FONT}`,
      color: COLORS.cobalt,
      align: 'right',
      baseline: 'middle',
    });
  }

  ctx.restore();
}

function drawCdfStateBox(ctx, rect, cdf) {
  const aspect = cdf.semiA > 1e-9 ? (cdf.semiB / cdf.semiA) : 1;
  const tiltDeg = (cdf.angle || 0) * 180 / Math.PI;
  const boxWidth = 258;
  const boxHeight = 116;
  const x = rect.x + rect.w - boxWidth - 12;
  const y = rect.y + 54;

  ctx.save();
  roundedRect(ctx, x, y, boxWidth, boxHeight, 14);
  ctx.fillStyle = 'rgba(255, 251, 244, 0.92)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(120, 106, 82, 0.18)';
  ctx.lineWidth = 1;
  ctx.stroke();

  Renderer.drawText(ctx, 'Current size / shape', x + 16, y + 20, {
    font: `600 14px ${FIGURE_FONT}`,
    color: COLORS.inkLight,
    align: 'left',
    baseline: 'middle',
  });
  Renderer.drawText(ctx, `size  rho = ${cdf.rho.toFixed(1)}`, x + 16, y + 48, {
    font: `15px ${FIGURE_FONT}`,
    color: COLORS.ink,
    align: 'left',
    baseline: 'middle',
  });
  Renderer.drawText(ctx, `shape  b/a = ${aspect.toFixed(2)}`, x + 16, y + 74, {
    font: `15px ${FIGURE_FONT}`,
    color: COLORS.ink,
    align: 'left',
    baseline: 'middle',
  });
  Renderer.drawText(ctx, `tilt  ${tiltDeg >= 0 ? '+' : ''}${tiltDeg.toFixed(1)}°`, x + 16, y + 100, {
    font: `15px ${FIGURE_FONT}`,
    color: COLORS.ink,
    align: 'left',
    baseline: 'middle',
  });
  ctx.restore();
}

function buildSphereBenchmarkTrace(trace, baseIndex, targetRho) {
  const baseRecord = trace?.iterations?.[baseIndex];
  if (!baseRecord) return null;
  const samples = trace?.samples || [];
  const insideMask = samples.map((sample) => Math.hypot(sample.x, sample.y) <= targetRho);
  const insideCount = insideMask.filter(Boolean).length;
  const coverage = insideMask.length ? insideCount / insideMask.length : 0.95;
  const record = {
    ...baseRecord,
    L_2d: [[1, 0], [0, 1]],
    L_next_2d: [[1, 0], [0, 1]],
    rho_hat: targetRho,
    rho: targetRho,
    tau_target: 0.95,
    coverage_cal: coverage,
    coverage_test: coverage,
    coverage,
    inside_mask: insideMask,
  };
  return {
    samples,
    iterations: [record],
  };
}

class FigureRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.time = 0;
    this._liveMarked = false;
  }

  update(dt) {
    this.time += dt;
  }

  markLive() {
    if (this._liveMarked) return;
    const slot = this.canvas.closest('.figure-slot');
    if (slot) slot.dataset.figureLive = 'true';
    this._liveMarked = true;
  }

  destroy() {}
}

class TraceShapeFigure extends FigureRenderer {
  constructor(canvas, trace, recordIndex, options = {}) {
    super(canvas);
    this.trace = trace;
    this.recordIndex = recordIndex;
    this.options = options;
  }

  getRenderState() {
    const sequenceIndices = this.options.sequenceIndices || [];
    if (!sequenceIndices.length) {
      const record = this.trace?.iterations?.[this.recordIndex];
      return {
        record,
        currentRecord: record,
        nextRecord: record,
        mix: 0,
      };
    }

    const { currentIndex, nextIndex, mix } = getSequenceState(
      this.time,
      sequenceIndices,
      this.options.stepDuration || 1.8,
    );
    const currentRecord = this.trace?.iterations?.[currentIndex];
    const nextRecord = this.trace?.iterations?.[nextIndex] || currentRecord;
    if (!currentRecord) {
      return {
        record: null,
        currentRecord: null,
        nextRecord: null,
        mix: 0,
      };
    }

    const interpolatedRecord = {
      ...currentRecord,
      L_2d: lerpMatrix(currentRecord.L_2d, nextRecord?.L_2d, mix),
      rho_hat: lerp(getRecordRho(currentRecord), getRecordRho(nextRecord), mix),
      rho: lerp(getRecordRho(currentRecord), getRecordRho(nextRecord), mix),
      coverage_cal: lerp(
        currentRecord.coverage_cal ?? getRecordCoverage(currentRecord),
        nextRecord?.coverage_cal ?? getRecordCoverage(nextRecord),
        mix,
      ),
      coverage_test: lerp(
        currentRecord.coverage_test ?? getRecordCoverage(currentRecord),
        nextRecord?.coverage_test ?? getRecordCoverage(nextRecord),
        mix,
      ),
      coverage: lerp(
        getRecordCoverage(currentRecord),
        getRecordCoverage(nextRecord),
        mix,
      ),
      tau_target: lerp(currentRecord.tau_target ?? 0.95, nextRecord?.tau_target ?? 0.95, mix),
      grad_rho_norm: lerp(currentRecord.grad_rho_norm ?? 0, nextRecord?.grad_rho_norm ?? 0, mix),
      grad_shape_norm: lerp(currentRecord.grad_shape_norm ?? 0, nextRecord?.grad_shape_norm ?? 0, mix),
      L_next_2d: currentRecord.L_next_2d || nextRecord?.L_next_2d,
    };

    return {
      record: interpolatedRecord,
      currentRecord,
      nextRecord,
      mix,
    };
  }

  render() {
    const pulse = 0.5 + 0.5 * Math.sin(this.time * 1.25);
    const { record, currentRecord } = this.getRenderState();
    if (!record) return;

    const { width, height, dpr } = ensureCanvasSize(this.canvas);
    const ctx = this.canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    drawPaperBackdrop(ctx, width, height);

    const titleOffset = this.options.panelTitle ? 30 : 10;
    const legendSpace = this.options.showLegend ? 32 : 8;
    const plotRect = {
      x: 18,
      y: titleOffset,
      w: width - 36,
      h: height - titleOffset - legendSpace - 10,
    };
    const rho = getRecordRho(record);
    const samples = this.trace?.samples || [];
    const { center, scale } = getShapeTransform(
      plotRect,
      this.options.transformTrace || this.trace,
      samples,
    );

    if (this.options.panelTitle) {
      Renderer.drawText(ctx, this.options.panelTitle, plotRect.x + 2, 16, {
        font: `600 15px ${FIGURE_FONT}`,
        color: COLORS.ink,
        align: 'left',
        baseline: 'middle',
      });
    }

    if (this.options.showCoverageLabel !== false) {
      const insideCount = (currentRecord?.inside_mask || []).filter(Boolean).length;
      const totalCount = currentRecord?.inside_mask?.length || 0;
      const visibleCoverage = totalCount ? insideCount / totalCount : getRecordCoverage(record);
      Renderer.drawText(
        ctx,
        `Visible capture ${formatPercent(visibleCoverage)} · target 95%`,
        width - 18,
        this.options.panelTitle ? 16 : 18,
        {
          font: `12px ${FIGURE_FONT}`,
          color: COLORS.inkLight,
          align: 'right',
          baseline: 'middle',
        },
      );
    }

    drawPlotPanel(ctx, plotRect);
    drawShapeGrid(ctx, plotRect, center);
    drawSamples(ctx, samples, currentRecord?.inside_mask, center, scale, pulse);

    if (this.options.showGhost !== false && currentRecord) {
      const referenceRecord = this.trace?.iterations?.[0];
      const referenceRho = getRecordRho(referenceRecord);
      Renderer.drawEllipse(ctx, center.x, center.y, referenceRecord?.L_2d || record.L_2d, scale * referenceRho, {
        strokeColor: COLORS.cobalt,
        fillColor: null,
        lineWidth: 1.5,
        alpha: 0.45,
        dash: [8, 6],
      });
    }

    drawCoverageCorrectionCue(ctx, record, center, scale, rho, pulse);
    if (this.options.showPreview !== false) {
      drawNextShapeGhost(ctx, record, center, scale, rho, pulse);
    }
    Renderer.drawEllipse(ctx, center.x, center.y, record.L_2d || [[1, 0], [0, 1]], scale * rho * (1 + 0.012 * Math.sin(this.time * 1.1)), {
      strokeColor: COLORS.teal,
      fillColor: alphaColor(COLORS.teal, 0.06),
      lineWidth: 2.2,
      alpha: 0.95,
    });

    if (this.options.showSupport !== false) {
      drawSupportPoints(ctx, currentRecord?.support_points_2d || [], currentRecord || record, center, scale, pulse);
    }
    if (this.options.showForces !== false) {
      drawReserveForceArrows(ctx, currentRecord || record, center, scale, pulse);
    }

    ctx.restore();

    if (this.options.showLegend) {
      drawShapeLegend(ctx, { x: 0, y: 0, w: width, h: height });
    }

    this.markLive();
  }
}

class TraceCdfFigure extends FigureRenderer {
  constructor(canvas, trace, recordIndex, options = {}) {
    super(canvas);
    this.trace = trace;
    this.recordIndex = recordIndex;
    this.options = options;
  }

  getInterpolatedCdf() {
    const sequenceIndices = this.options.sequenceIndices || [this.recordIndex];
    const { currentIndex, nextIndex, mix } = getSequenceState(this.time, sequenceIndices, this.options.stepDuration || 1.8);
    const current = this.trace?.iterations?.[currentIndex];
    const next = this.trace?.iterations?.[nextIndex] || current;
    if (!current) return null;

    return {
      xs: current.score_cdf_x.map((value, index) => lerp(value, next.score_cdf_x[index], mix)),
      ys: current.score_cdf_y.map((value, index) => lerp(value, next.score_cdf_y[index], mix)),
      rho: lerp(getRecordRho(current), getRecordRho(next), mix),
      tau: lerp(current.tau_target || 0.95, next.tau_target || 0.95, mix),
      semiA: lerp(current.semi_a ?? 1, next.semi_a ?? current.semi_a ?? 1, mix),
      semiB: lerp(current.semi_b ?? 1, next.semi_b ?? current.semi_b ?? 1, mix),
      angle: lerp(current.angle ?? 0, next.angle ?? current.angle ?? 0, mix),
    };
  }

  render() {
    const cdf = this.getInterpolatedCdf();
    if (!cdf) return;

    const { width, height, dpr } = ensureCanvasSize(this.canvas);
    const ctx = this.canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    drawPaperBackdrop(ctx, width, height);

    if (this.options.panelTitle) {
      Renderer.drawText(ctx, this.options.panelTitle, 18, 16, {
        font: `600 15px ${FIGURE_FONT}`,
        color: COLORS.ink,
        align: 'left',
        baseline: 'middle',
      });
    }

    drawLineChart(ctx, {
      x: 18,
      y: this.options.panelTitle ? 28 : 12,
      w: width - 36,
      h: height - (this.options.panelTitle ? 44 : 24),
    }, cdf.xs, cdf.ys, {
      label: 'Smoothed CDF',
      currentX: cdf.rho,
      targetY: cdf.tau,
      targetLabel: '95% target',
    });

    drawCdfStateBox(ctx, {
      x: 18,
      y: this.options.panelTitle ? 28 : 12,
      w: width - 36,
      h: height - (this.options.panelTitle ? 44 : 24),
    }, cdf);

    this.markLive();
  }
}

export function attachFigureSlots(slide, root, dataBundle) {
  const trace = dataBundle.storyStatic;
  const slots = [];

  if (slide.animation_mode === 'title_trace_shape') {
    const canvas = root.querySelector('[data-figure-slot="title-trace"]');
    if (canvas) {
      const traceIndex = slide.figure_config?.traceIndex ?? 0;
      slots.push(new TraceShapeFigure(canvas, trace, traceIndex, {
        panelTitle: 'Shape, Forces, and Hedge',
        sequenceIndices: slide.figure_config?.sequenceIndices || [],
        stepDuration: slide.figure_config?.stepDuration || 1.8,
        showLegend: false,
        showCoverageLabel: true,
        showGhost: true,
        showPreview: true,
        showForces: true,
        showSupport: true,
      }));
    }
  }

  if (slide.animation_mode === 'trace_shape') {
    const canvas = root.querySelector('[data-figure-slot="problem-ellipse"]');
    if (canvas) {
      const traceIndex = slide.figure_config?.traceIndex ?? 0;
      slots.push(new TraceShapeFigure(canvas, trace, traceIndex, {
        panelTitle: 'Shape, Forces, and Hedge',
        showLegend: slide.figure_config?.showLegend ?? true,
        showCoverageLabel: slide.figure_config?.showCoverageLabel ?? true,
        showGhost: slide.figure_config?.showGhost ?? true,
        showPreview: slide.figure_config?.showPreview ?? true,
        showForces: slide.figure_config?.showForces ?? true,
        showSupport: slide.figure_config?.showSupport ?? true,
      }));
    }
  }

  if (slide.animation_mode === 'trace_compare') {
    const leftCanvas = root.querySelector('[data-figure-slot="compare-left"]');
    const rightCanvas = root.querySelector('[data-figure-slot="compare-right"]');
    if (leftCanvas) {
      const leftMode = slide.figure_config?.leftMode || 'trace';
      const leftTrace = leftMode === 'sphere'
        ? buildSphereBenchmarkTrace(trace, slide.figure_config?.leftBaseIndex ?? 0, slide.figure_config?.leftRho ?? 1)
        : trace;
      const leftIndex = leftMode === 'sphere' ? 0 : (slide.figure_config?.leftIndex ?? 0);
      slots.push(new TraceShapeFigure(leftCanvas, leftTrace, leftIndex, {
        showLegend: false,
        showCoverageLabel: false,
        showGhost: false,
        showPreview: false,
        showForces: true,
        showSupport: true,
        transformTrace: trace,
      }));
    }
    if (rightCanvas) {
      slots.push(new TraceShapeFigure(rightCanvas, trace, slide.figure_config?.rightIndex ?? 0, {
        showLegend: false,
        showCoverageLabel: false,
        showGhost: false,
        showPreview: true,
        showForces: true,
        showSupport: true,
        transformTrace: trace,
      }));
    }
  }

  if (slide.animation_mode === 'trace_cdf') {
    const canvas = root.querySelector('[data-figure-slot="cdf-profile"]');
    const traceIndex = slide.figure_config?.traceIndex ?? 0;
    if (canvas) {
      slots.push(new TraceCdfFigure(canvas, trace, traceIndex, {
        panelTitle: 'Smooth CDF and 95% Threshold',
        sequenceIndices: slide.figure_config?.sequenceIndices || [],
        stepDuration: slide.figure_config?.stepDuration || 1.8,
      }));
    }
  }

  return slots;
}

export function destroyFigureSlots(slots) {
  for (const slot of slots) {
    slot.destroy?.();
  }
}
