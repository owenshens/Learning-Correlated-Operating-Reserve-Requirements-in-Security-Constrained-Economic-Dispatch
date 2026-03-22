import { Renderer, COLORS } from '../engine/renderer.js';
import { AnimatedValue } from '../engine/timeline.js';
import { Ellipsoid } from '../components/ellipsoid.js';
import { ReserveBars } from '../components/reserveBars.js';
import { ZoneMap } from '../components/zoneMap.js';
import { GradientFlow } from '../components/gradientFlow.js';

function roundedRect(ctx, x, y, w, h, r = 18) {
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

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function alphaColor(color, alpha) {
  if (color.startsWith('#')) {
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  return color;
}

function formatCurrency(value) {
  return '$' + Math.round(value).toLocaleString('en-US');
}

function formatPercent(value) {
  return (value * 100).toFixed(1) + '%';
}

function getRecordRho(record) {
  return record?.rho_hat ?? record?.rho ?? 1;
}

function getRecordCoverage(record) {
  return record?.coverage_test ?? record?.coverage ?? 0;
}

export class StageRenderer {
  constructor({ zones, network }) {
    this.zones = zones;
    this.network = network;
    this.zoneLoads = zones.map((zone) => zone.load_mw);
    this.zoneRects = [];

    this.ellipsoid = new Ellipsoid({ particleCount: 0 });
    this.ellipsoid.showAxes = false;

    this.reserveBars = new ReserveBars({ zoneCount: zones.length });
    this.zoneMap = new ZoneMap({
      zoneData: { genCounts: zones.map((zone) => zone.num_generators) },
    });
    this.gradientFlow = new GradientFlow({ particleSize: 3.2, trailLength: 7 });

    this.displayRho = new AnimatedValue(1);
    this.lastEllipseKey = '';
    this.lastDataKey = '';
    this.lastGradientKey = '';
    this.traceExtentCache = new WeakMap();
  }

  update(dt) {
    this.displayRho.update(dt);
    this.ellipsoid.update(dt);
    this.reserveBars.update(dt);
    this.zoneMap.update(dt);
    this.gradientFlow.update(dt);
  }

  hitTestZone(x, y) {
    for (let index = 0; index < this.zoneRects.length; index++) {
      const rect = this.zoneRects[index];
      if (
        rect &&
        x >= rect.x &&
        x <= rect.x + rect.w &&
        y >= rect.y &&
        y <= rect.y + rect.h
      ) {
        return index;
      }
    }
    return null;
  }

  render(ctx, width, height, frame) {
    const layout = this.getLayout(width, height);
    this.syncFrame(frame, layout);

    this.drawBackdrop(ctx, width, height);
    this.drawPanel(ctx, layout.shapeRect, alphaColor(COLORS.teal, 0.12));
    this.drawPanel(ctx, layout.rightRect, alphaColor(COLORS.cobalt, 0.08));
    this.drawPanel(ctx, layout.historyRect, alphaColor(COLORS.ink, 0.08));

    this.renderShapePanel(ctx, layout.shapeRect, frame);
    this.renderRightPanel(ctx, layout.rightRect, frame);
    this.renderHistoryRail(ctx, layout.historyRect, frame);
  }

  getLayout(width, height) {
    const margin = Math.max(22, width * 0.024);
    const top = Math.max(96, height * 0.12);
    const bottomGap = 28;
    const stageHeight = height - top - bottomGap;
    const historyH = Math.max(134, stageHeight * 0.24);
    const mainH = stageHeight - historyH - 18;
    const shapeW = width * 0.53;
    const rightW = width - margin * 3 - shapeW;

    return {
      shapeRect: { x: margin, y: top, w: shapeW, h: mainH },
      rightRect: { x: margin * 2 + shapeW, y: top, w: rightW, h: mainH },
      historyRect: { x: margin, y: top + mainH + 18, w: width - margin * 2, h: historyH },
    };
  }

  syncFrame(frame, layout) {
    const record = frame.record;
    const recordKey = `${frame.act}:${frame.mode}:${frame.currentIndex}:${frame.loopStep}:${frame.state.method}:${frame.state.coupled}`;
    const rho = getRecordRho(record);
    const dominantZone = (frame.state.selectedZone ?? ((record?.dominant_zones?.[0] || record?.dominant_zone || 1) - 1));
    const mapRect = this.getZoneMapRect(layout.rightRect, frame.loopStep);

    if (recordKey !== this.lastDataKey && record) {
      this.layoutZoneMap(mapRect);
      this.reserveBars.setReserves(record.reserves_per_zone || []);
      this.reserveBars.setDuals(record.combined_duals || record.mu_z || []);
      this.zoneMap.setZoneData({
        loads: this.zoneLoads,
        reserves: record.reserves_per_zone || [],
        duals: record.combined_duals || record.mu_z || [],
        transfers: record.lambda_z || [],
      });
      this.displayRho.set(rho);
      this.lastDataKey = recordKey;
    }

    this.reserveBars.highlightZone(dominantZone);
    this.zoneMap.highlightZone(dominantZone);

    const ellipseKey = `${frame.act}:${frame.currentIndex}:${rho.toFixed(4)}`;
    if (record && ellipseKey !== this.lastEllipseKey) {
      if (!this.lastEllipseKey) {
        this.ellipsoid.setL(record.L_2d || [[1, 0], [0, 1]]);
        this.displayRho.snap(rho);
      } else {
        this.ellipsoid.morphTo(record.L_2d || [[1, 0], [0, 1]], 700);
        this.displayRho.set(rho);
      }
      this.lastEllipseKey = ellipseKey;
    }

    if (frame.loopStep === 'gradient') {
      const gradientKey = `${recordKey}:gradient`;
      if (gradientKey !== this.lastGradientKey) {
        this.layoutZoneMap(mapRect);
        const paths = this.buildGradientPaths(frame, layout);
        this.gradientFlow.setFlowPath(paths);
        this.gradientFlow.triggerPulse(1200);
        this.lastGradientKey = gradientKey;
      }
    }
  }

  drawBackdrop(ctx, width, height) {
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, '#f4efe3');
    gradient.addColorStop(0.55, '#fbf7ef');
    gradient.addColorStop(1, '#efe4cf');
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
  }

  drawPanel(ctx, rect, accent) {
    ctx.save();
    const shadow = ctx.createLinearGradient(rect.x, rect.y, rect.x, rect.y + rect.h);
    shadow.addColorStop(0, 'rgba(255,255,255,0.7)');
    shadow.addColorStop(1, 'rgba(255,255,255,0.32)');
    roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 24);
    ctx.fillStyle = shadow;
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = accent;
    ctx.stroke();
    ctx.restore();
  }

  renderShapePanel(ctx, rect, frame) {
    const record = frame.record;
    if (!record) return;

    const inset = 20;
    const plotRect = {
      x: rect.x + inset,
      y: rect.y + 30,
      w: rect.w - inset * 2,
      h: rect.h - 64,
    };
    const rho = this.displayRho.get();
    const samples = frame.samples || [];
    const supportPoints = record.support_points_2d || [];

    Renderer.drawText(ctx, 'Shape, Forces, and Hedge', plotRect.x + 2, rect.y + 18, {
      font: '600 15px "Manrope", sans-serif',
      color: COLORS.ink,
      align: 'left',
      baseline: 'middle',
    });

    const { center, scale } = this.getShapeTransform(plotRect, frame);

    this.ellipsoid.cx = center.x;
    this.ellipsoid.cy = center.y;
    this.ellipsoid.scale = scale * rho;

    ctx.save();
    roundedRect(ctx, plotRect.x, plotRect.y, plotRect.w, plotRect.h, 18);
    ctx.clip();

    this.drawShapeGrid(ctx, plotRect, center, scale);
    this.drawSamples(ctx, samples, record.inside_mask, center, scale);

    if (frame.historyTrace?.iterations?.length && frame.currentIndex > 0) {
      const referenceRecord = frame.historyTrace.iterations[0];
      const ghostRho = referenceRecord?.rho_hat || referenceRecord?.rho || rho;
      Renderer.drawEllipse(ctx, center.x, center.y, referenceRecord?.L_2d || record.L_2d, scale * ghostRho, {
        strokeColor: COLORS.cobalt,
        fillColor: null,
        lineWidth: 1.5,
        alpha: 0.45,
        dash: [8, 6],
      });
    }

    this.drawCoverageCorrectionCue(ctx, frame, center);
    this.drawNextShapeGhost(ctx, frame, center, scale, rho);
    this.ellipsoid.render(ctx);
    this.drawSupportPoints(ctx, supportPoints, frame, center, scale);
    this.drawReserveForceArrows(ctx, frame, center, scale);
    ctx.restore();

    const insideCount = (record.inside_mask || []).filter(Boolean).length;
    const totalCount = record.inside_mask?.length || 0;
    const visibleCoverage = totalCount ? insideCount / totalCount : getRecordCoverage(record);

    Renderer.drawText(
      ctx,
      `Visible capture ${formatPercent(visibleCoverage)} · target 95%`,
      rect.x + rect.w - 18,
      rect.y + 18,
      {
        font: '12px "Manrope", sans-serif',
        color: COLORS.inkLight,
        align: 'right',
        baseline: 'middle',
      },
    );

    this.drawShapeLegend(ctx, rect, record);
  }

  getShapeTransform(plotRect, frame) {
    const extents = this.getTraceExtents(frame.historyTrace, frame.samples || []);
    const scale = Math.min(
      plotRect.w / Math.max(extents.width * 2.2, 1),
      plotRect.h / Math.max(extents.height * 2.2, 1),
    );
    const center = {
      x: plotRect.x + plotRect.w * 0.52,
      y: plotRect.y + plotRect.h * 0.52,
    };
    return { center, scale, extents };
  }

  getTraceExtents(trace, samples) {
    if (trace && this.traceExtentCache.has(trace)) {
      return this.traceExtentCache.get(trace);
    }

    let maxX = 1;
    let maxY = 1;

    for (const sample of samples) {
      maxX = Math.max(maxX, Math.abs(sample.x));
      maxY = Math.max(maxY, Math.abs(sample.y));
    }

    const iterations = trace?.iterations || [];
    for (const iteration of iterations) {
      const ellipseExtent = this.getEllipseExtents(iteration);
      maxX = Math.max(maxX, ellipseExtent.width);
      maxY = Math.max(maxY, ellipseExtent.height);

      for (const point of iteration.support_points_2d || []) {
        maxX = Math.max(maxX, Math.abs(point.x));
        maxY = Math.max(maxY, Math.abs(point.y));
      }
    }

    const extents = { width: maxX, height: maxY };
    if (trace) {
      this.traceExtentCache.set(trace, extents);
    }
    return extents;
  }

  getEllipseExtents(record) {
    const L = record?.L_2d || [[1, 0], [0, 1]];
    const rho = getRecordRho(record);
    const row0 = L[0] || [1, 0];
    const row1 = L[1] || [0, 1];
    return {
      width: rho * Math.hypot(row0[0] || 0, row0[1] || 0),
      height: rho * Math.hypot(row1[0] || 0, row1[1] || 0),
    };
  }

  drawShapeGrid(ctx, rect, center, scale) {
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

  drawSamples(ctx, samples, insideMask, center, scale) {
    if (!samples || !samples.length) return;
    for (let i = 0; i < samples.length; i++) {
      const sample = samples[i];
      const inside = insideMask ? insideMask[i] : true;
      const x = center.x + sample.x * scale;
      const y = center.y - sample.y * scale;
      Renderer.drawParticle(ctx, x, y, inside ? 2.2 : 2.6, inside ? COLORS.teal : COLORS.ember, inside ? 0.34 : 0.52);
    }
  }

  drawSupportPoints(ctx, supportPoints, frame, center, scale) {
    const highlightedZones = new Set((frame.record.dominant_zones || []).slice(0, 3));
    for (const point of supportPoints) {
      const x = center.x + point.x * scale;
      const y = center.y - point.y * scale;
      const highlighted = highlightedZones.has(point.zone) || frame.state.selectedZone === point.zone - 1;
      if (frame.loopStep === 'shape' || frame.loopStep === 'reserves' || frame.loopStep === 'gradient' || frame.loopStep === 'update') {
        Renderer.drawLine(ctx, center.x, center.y, x, y, {
          color: highlighted ? COLORS.ember : COLORS.cobalt,
          alpha: highlighted ? 0.38 : 0.15,
          lineWidth: highlighted ? 1.8 : 1,
          dash: highlighted ? null : [6, 6],
        });
      }
      Renderer.drawGlow(ctx, x, y, highlighted ? 14 : 8, highlighted ? COLORS.ember : COLORS.cobalt, highlighted ? 0.5 : 0.22);
      Renderer.drawParticle(ctx, x, y, highlighted ? 4.2 : 2.6, highlighted ? COLORS.ember : COLORS.cobalt, highlighted ? 0.9 : 0.48);
      if (highlighted) {
        Renderer.drawText(ctx, `Z${point.zone}`, x + 8, y - 8, {
          font: '11px "Manrope", sans-serif',
          color: COLORS.ink,
          align: 'left',
          baseline: 'middle',
          alpha: 0.84,
        });
      }
    }
  }

  drawCoverageCorrectionCue(ctx, frame, center) {
    const record = frame.record;
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
    Renderer.drawEllipse(ctx, center.x, center.y, record?.L_2d || [[1, 0], [0, 1]], this.ellipsoid.scale * correctionScale, {
      strokeColor: COLORS.tealLight,
      fillColor: null,
      lineWidth: 1.25,
      alpha: 0.16 + strength * 0.2,
      dash: [5, 6],
    });

    const arrowAngles = [-1.15, -0.2, 0.75, 1.9];
    for (const angle of arrowAngles) {
      const boundary = this.getEllipsePoint(angle, 1);
      const corrected = this.getEllipsePoint(angle, correctionScale);
      Renderer.drawArrow(ctx, boundary.x, boundary.y, corrected.x, corrected.y, {
        color: COLORS.tealLight,
        alpha: 0.24 + strength * 0.38,
        lineWidth: 1.4,
        headSize: 6,
      });
    }
  }

  drawNextShapeGhost(ctx, frame, center, scale, rho) {
    const nextL = frame.record?.L_next_2d;
    if (!nextL) return;
    Renderer.drawEllipse(ctx, center.x, center.y, nextL, scale * rho, {
      strokeColor: COLORS.ember,
      fillColor: null,
      lineWidth: 1.35,
      alpha: 0.24,
      dash: [4, 5],
    });
  }

  drawReserveForceArrows(ctx, frame, center, scale) {
    const contributions = (frame.record?.zone_contributions || [])
      .slice()
      .sort((a, b) => b.total_contribution - a.total_contribution)
      .slice(0, 3);
    if (!contributions.length) return;

    const supportByZone = new Map((frame.record?.support_points_2d || []).map((point) => [point.zone, point]));
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
      const length = 12 + 24 * clamp(row.total_contribution / maxContribution, 0.15, 1);
      const alpha = 0.78 - rank * 0.14;

      Renderer.drawArrow(ctx, x, y, x + ux * length, y + uy * length, {
        color: COLORS.ember,
        alpha,
        lineWidth: rank === 0 ? 2.1 : 1.7,
        headSize: 7,
      });
    });
  }

  getEllipsePoint(angle, scaleFactor = 1) {
    const params = this.ellipsoid.currentParams;
    const localX = Math.cos(angle) * params.semiA * this.ellipsoid.scale * scaleFactor;
    const localY = Math.sin(angle) * params.semiB * this.ellipsoid.scale * scaleFactor;
    const cosA = Math.cos(params.angle);
    const sinA = Math.sin(params.angle);
    return {
      x: this.ellipsoid.cx + localX * cosA - localY * sinA,
      y: this.ellipsoid.cy + localX * sinA + localY * cosA,
    };
  }

  drawShapeLegend(ctx, rect, record) {
    Renderer.drawText(
      ctx,
      'Orange arrows: reserve pull  ·  Teal cue: coverage correction  ·  dotted: one-step shape preview',
      rect.x + 18,
      rect.y + rect.h - 18,
      {
        font: '11px "Manrope", sans-serif',
        color: COLORS.inkLight,
        align: 'left',
        baseline: 'middle',
        alpha: 0.88,
      },
    );
  }

  renderRightPanel(ctx, rect, frame) {
    const cdfRect = {
      x: rect.x + 18,
      y: rect.y + 26,
      w: rect.w - 36,
      h: rect.h * 0.36,
    };
    const dualRect = {
      x: rect.x + 18,
      y: rect.y + rect.h * 0.43,
      w: rect.w - 36,
      h: rect.h * 0.48,
    };

    this.renderCalibrationSnapshot(ctx, cdfRect, frame);
    this.renderDualSnapshot(ctx, dualRect, frame);
  }

  renderCalibrationSnapshot(ctx, rect, frame) {
    const record = frame.record;
    Renderer.drawText(ctx, 'Smooth CDF and 95% Threshold', rect.x, rect.y - 10, {
      font: '600 15px "Manrope", sans-serif',
      color: COLORS.ink,
      align: 'left',
      baseline: 'middle',
    });
    this.drawLineChart(ctx, rect, record.score_cdf_x || [], record.score_cdf_y || [], {
      label: 'Smoothed CDF',
      currentX: getRecordRho(record),
      targetY: record.tau_target || 0.95,
      currentLabel: `ρ = ${getRecordRho(record).toFixed(2)}`,
      targetLabel: '95% target',
    });
  }

  renderDualSnapshot(ctx, rect, frame) {
    Renderer.drawText(ctx, 'Zone Dual Values', rect.x, rect.y - 10, {
      font: '600 15px "Manrope", sans-serif',
      color: COLORS.ink,
      align: 'left',
      baseline: 'middle',
    });
    this.renderDualBars(ctx, {
      x: rect.x,
      y: rect.y + 8,
      w: rect.w,
      h: rect.h - 12,
    }, frame.record);
  }

  renderDualBars(ctx, rect, record) {
    const duals = record?.mu_z?.length ? record.mu_z : (record?.combined_duals || []);
    if (!duals.length) return;

    const maxDual = Math.max(...duals, 1e-6);
    const rowGap = 10;
    const rowCount = duals.length;
    const rowHeight = Math.max(18, (rect.h - rowGap * (rowCount - 1)) / rowCount);
    const labelW = 36;
    const valueW = 54;
    const barX = rect.x + labelW;
    const barW = Math.max(40, rect.w - labelW - valueW - 12);
    const topZones = new Set((record?.dominant_zones || []).slice(0, 3));

    for (let index = 0; index < duals.length; index++) {
      const value = duals[index];
      const y = rect.y + index * (rowHeight + rowGap);
      const isDominant = topZones.has(index + 1);
      const fillW = clamp((value / maxDual) * barW, 0, barW);
      const barColor = isDominant ? COLORS.ember : COLORS.cobalt;

      Renderer.drawText(ctx, `Z${index + 1}`, rect.x, y + rowHeight * 0.5, {
        font: '12px "Manrope", sans-serif',
        color: isDominant ? COLORS.ember : COLORS.ink,
        align: 'left',
        baseline: 'middle',
      });

      ctx.save();
      roundedRect(ctx, barX, y, barW, rowHeight, 9);
      ctx.fillStyle = 'rgba(45, 45, 45, 0.06)';
      ctx.fill();

      roundedRect(ctx, barX, y, fillW, rowHeight, 9);
      ctx.fillStyle = alphaColor(barColor, isDominant ? 0.72 : 0.42);
      ctx.fill();
      ctx.restore();

      Renderer.drawText(ctx, value.toFixed(2), rect.x + rect.w, y + rowHeight * 0.5, {
        font: '12px "Manrope", sans-serif',
        color: COLORS.inkLight,
        align: 'right',
        baseline: 'middle',
      });
    }
  }

  renderZoneMap(ctx, rect, frame) {
    this.layoutZoneMap(rect);
    this.zoneMap.setZoneData({
      loads: this.zoneLoads,
      reserves: frame.record?.reserves_per_zone || [],
      duals: frame.record?.combined_duals || frame.record?.mu_z || [],
      transfers: frame.record?.lambda_z || [],
    });
    this.zoneMap.setCoupledMode(frame.state.coupled || frame.act === 'advanced-coupled');
    this.zoneMap.render(ctx);
    this.zoneRects = this.zones.map((_, index) => this.zoneMap.getZoneRect(index));
  }

  layoutZoneMap(rect) {
    this.zoneMap.cx = rect.x + rect.w / 2;
    this.zoneMap.cy = rect.y + rect.h / 2;
    this.zoneMap.radius = Math.min(rect.w * 0.42, rect.h * 0.44);
    this.zoneMap.zoneSize = { w: 58, h: 48 };
    this.zoneMap.zonePositions = this.zones.map((zone) => ({
      x: rect.x + zone.x * rect.w,
      y: rect.y + zone.y * rect.h,
    }));
  }

  getZoneMapRect(rect, loopStep) {
    let heightRatio = 0.46;
    if (loopStep === 'duals') heightRatio = 0.54;
    if (loopStep === 'gradient') heightRatio = 0.52;
    return {
      x: rect.x + 18,
      y: rect.y + 34,
      w: rect.w - 36,
      h: rect.h * heightRatio,
    };
  }

  buildGradientPaths(frame, layout) {
    const record = frame.record;
    const shapeRect = layout.shapeRect;
    const plotRect = {
      x: shapeRect.x + 20,
      y: shapeRect.y + 30,
      w: shapeRect.w - 40,
      h: shapeRect.h - 64,
    };
    const supportPoints = record.support_points_2d || [];
    const { center, scale } = this.getShapeTransform(plotRect, frame);

    const topZones = new Set((record.dominant_zones || []).slice(0, 3));
    return supportPoints
      .filter((point) => topZones.has(point.zone))
      .map((point) => {
        const zonePos = this.zoneMap.getZonePosition(point.zone - 1);
        const target = {
          x: center.x + point.x * scale,
          y: center.y - point.y * scale,
        };
        return {
          from: { x: zonePos.x, y: zonePos.y },
          waypoints: [
            { x: zonePos.x - 28, y: lerp(zonePos.y, target.y, 0.35) },
            { x: target.x + 28, y: lerp(zonePos.y, target.y, 0.72) },
          ],
          to: target,
          intensity: clamp(point.support / Math.max(record.reserve_total, 1), 0.35, 1.2),
        };
      });
  }

  renderContributionRows(ctx, rect, contributions, dualFocus) {
    const rows = contributions.slice().sort((a, b) => b.total_contribution - a.total_contribution).slice(0, 4);
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const y = rect.y + 16 + i * 24;
      const value = dualFocus ? row.combined_dual.toFixed(2) : row.shape_contribution_norm.toFixed(2);
      const rightLabel = dualFocus
        ? row.lambda > 1e-6
          ? `mu ${row.mu.toFixed(2)} + lam ${row.lambda.toFixed(2)}`
          : `dual ${value}`
        : `shape ${value}`;
      Renderer.drawText(ctx, row.label, rect.x + 4, y, {
        font: '12px "Manrope", sans-serif',
        color: i === 0 ? COLORS.ember : COLORS.ink,
        align: 'left',
        baseline: 'middle',
      });
      Renderer.drawText(ctx, rightLabel, rect.x + rect.w - 4, y, {
        font: '12px "Manrope", sans-serif',
        color: COLORS.inkLight,
        align: 'right',
        baseline: 'middle',
      });
      const barW = clamp(row.total_contribution / Math.max(rows[0].total_contribution, 1e-9), 0.12, 1) * (rect.w - 16);
      ctx.save();
      ctx.fillStyle = alphaColor(i === 0 ? COLORS.ember : COLORS.cobalt, i === 0 ? 0.6 : 0.32);
      roundedRect(ctx, rect.x + 4, y + 8, barW, 8, 5);
      ctx.fill();
      ctx.restore();
    }
  }

  renderHistoryRail(ctx, rect, frame) {
    const trace = frame.historyTrace;
    if (!trace || !trace.iterations || !trace.iterations.length) return;
    Renderer.drawText(ctx, 'Training History', rect.x + 18, rect.y + 16, {
      font: '600 15px "Manrope", sans-serif',
      color: COLORS.ink,
      align: 'left',
      baseline: 'middle',
    });

    const chartW = (rect.w - 36) / 2;
    const chartY = rect.y + 34;
    const chartH = rect.h - 50;
    const metrics = [
      {
        key: 'cost',
        label: 'Cost',
        values: trace.iterations.map((item) => item.cost),
        color: COLORS.ember,
        currentValue: frame.record?.cost,
      },
      {
        key: 'coverage_test',
        label: 'Coverage',
        values: trace.iterations.map((item) => item.coverage_test ?? item.coverage),
        color: COLORS.teal,
        currentValue: getRecordCoverage(frame.record),
        targetValue: 0.95,
      },
    ];

    metrics.forEach((metric, index) => {
      const chartRect = {
        x: rect.x + 16 + index * chartW,
        y: chartY,
        w: chartW - 12,
        h: chartH,
      };
      const selectedIndex = frame.currentTraceIndex;
      this.drawMiniHistoryChart(ctx, chartRect, metric, selectedIndex);
    });
  }

  drawMiniHistoryChart(ctx, rect, metric, selectedIndex) {
    const values = metric.values;
    const minValue = Math.min(...values, metric.targetValue ?? Infinity, metric.currentValue ?? Infinity);
    const maxValue = Math.max(...values, metric.targetValue ?? -Infinity, metric.currentValue ?? -Infinity);
    const range = Math.max(maxValue - minValue, 1e-9);

    Renderer.drawText(ctx, metric.label, rect.x, rect.y + 10, {
      font: '12px "Manrope", sans-serif',
      color: COLORS.inkLight,
      align: 'left',
      baseline: 'middle',
    });

    ctx.save();
    roundedRect(ctx, rect.x, rect.y + 22, rect.w, rect.h - 26, 12);
    ctx.fillStyle = 'rgba(255,255,255,0.45)';
    ctx.fill();
    ctx.clip();

    if (metric.targetValue !== undefined) {
      const ty = rect.y + 22 + (1 - (metric.targetValue - minValue) / range) * (rect.h - 26);
      Renderer.drawLine(ctx, rect.x + 8, ty, rect.x + rect.w - 8, ty, {
        color: COLORS.cobalt,
        alpha: 0.3,
        dash: [6, 5],
      });
    }

    ctx.beginPath();
    for (let i = 0; i < values.length; i++) {
      const x = rect.x + 8 + (i / Math.max(values.length - 1, 1)) * (rect.w - 16);
      const y = rect.y + 22 + (1 - (values[i] - minValue) / range) * (rect.h - 26);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = metric.color;
    ctx.lineWidth = 2.2;
    ctx.stroke();

    const highlightIndex = selectedIndex != null ? clamp(selectedIndex, 0, values.length - 1) : null;
    if (highlightIndex != null) {
      const x = rect.x + 8 + (highlightIndex / Math.max(values.length - 1, 1)) * (rect.w - 16);
      const y = rect.y + 22 + (1 - (values[highlightIndex] - minValue) / range) * (rect.h - 26);
      Renderer.drawGlow(ctx, x, y, 12, metric.color, 0.45);
      Renderer.drawParticle(ctx, x, y, 4, metric.color, 0.95);
    } else if (metric.currentValue !== undefined) {
      const x = rect.x + rect.w - 16;
      const y = rect.y + 22 + (1 - (metric.currentValue - minValue) / range) * (rect.h - 26);
      Renderer.drawGlow(ctx, x, y, 10, COLORS.ember, 0.32);
      Renderer.drawParticle(ctx, x, y, 4, COLORS.ember, 0.9);
    }
    ctx.restore();
  }

  drawHistogram(ctx, rect, bins, counts, rho) {
    const maxCount = Math.max(...counts, 1);
    const minBin = Math.min(...bins, rho);
    const maxBin = Math.max(...bins, rho);
    const range = Math.max(maxBin - minBin, 1e-9);

    ctx.save();
    roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 18);
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.fill();
    ctx.clip();

    for (let i = 0; i < counts.length; i++) {
      const x = rect.x + ((bins[i] - minBin) / range) * rect.w;
      const w = rect.w / Math.max(counts.length, 1) - 2;
      const h = (counts[i] / maxCount) * (rect.h - 24);
      const y = rect.y + rect.h - h - 12;
      ctx.fillStyle = alphaColor(COLORS.teal, 0.42);
      roundedRect(ctx, x, y, w, h, 6);
      ctx.fill();
    }

    const rhoX = rect.x + ((rho - minBin) / range) * rect.w;
    Renderer.drawLine(ctx, rhoX, rect.y + 8, rhoX, rect.y + rect.h - 8, {
      color: COLORS.ember,
      lineWidth: 2,
    });
    Renderer.drawText(ctx, `rho ${rho.toFixed(2)}`, rhoX + 6, rect.y + 16, {
      font: '12px "Manrope", sans-serif',
      color: COLORS.ember,
      align: 'left',
      baseline: 'middle',
    });
    ctx.restore();
  }

  drawLineChart(ctx, rect, xs, ys, options) {
    if (!xs.length || !ys.length) return;
    const minX = Math.min(...xs, options.currentX ?? Infinity);
    const maxX = Math.max(...xs, options.currentX ?? -Infinity);
    const minY = 0;
    const maxY = 1;

    ctx.save();
    roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 18);
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.fill();
    ctx.clip();

    if (options.targetY !== undefined) {
      const y = rect.y + (1 - (options.targetY - minY) / (maxY - minY)) * rect.h;
      Renderer.drawLine(ctx, rect.x + 8, y, rect.x + rect.w - 8, y, {
        color: COLORS.cobalt,
        alpha: 0.28,
        dash: [6, 5],
      });
    }

    ctx.beginPath();
    for (let i = 0; i < xs.length; i++) {
      const x = rect.x + ((xs[i] - minX) / Math.max(maxX - minX, 1e-9)) * rect.w;
      const y = rect.y + (1 - (ys[i] - minY) / (maxY - minY)) * rect.h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = COLORS.cobalt;
    ctx.lineWidth = 2;
    ctx.stroke();

    const currentX = options.currentX ?? xs[xs.length - 1];
    const idx = xs.findIndex((value) => value >= currentX);
    const yValue = idx >= 0 ? ys[idx] : ys[ys.length - 1];
    const cx = rect.x + ((currentX - minX) / Math.max(maxX - minX, 1e-9)) * rect.w;
    const cy = rect.y + (1 - (yValue - minY) / (maxY - minY)) * rect.h;
    Renderer.drawGlow(ctx, cx, cy, 10, COLORS.ember, 0.4);
    Renderer.drawParticle(ctx, cx, cy, 4, COLORS.ember, 0.9);

    Renderer.drawText(ctx, options.label, rect.x + 10, rect.y + 14, {
      font: '12px "Manrope", sans-serif',
      color: COLORS.inkLight,
      align: 'left',
      baseline: 'middle',
    });
    if (options.targetLabel) {
      Renderer.drawText(ctx, options.targetLabel, rect.x + rect.w - 10, rect.y + 14, {
        font: '12px "Manrope", sans-serif',
        color: COLORS.cobalt,
        align: 'right',
        baseline: 'middle',
      });
    }
    ctx.restore();
  }
}
