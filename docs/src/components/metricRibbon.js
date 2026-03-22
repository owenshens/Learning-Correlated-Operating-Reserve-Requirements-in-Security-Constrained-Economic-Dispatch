// metricRibbon.js — Persistent Metrics Display
// Compact metrics strip always visible at top or bottom

const GRAPHITE = '#2D2D2D';
const EMBER_ORANGE = '#E8763A';
const IVORY = '#FAF6F0';

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function formatCurrency(value) {
  return '$' + Math.round(value).toLocaleString('en-US');
}

function formatNumber(value, decimals) {
  if (decimals === undefined) decimals = 0;
  if (decimals === 0) return Math.round(value).toLocaleString('en-US');
  return value.toFixed(decimals);
}

class AnimatedMetric {
  constructor(label, unit, decimals) {
    this.label = label;
    this.unit = unit;
    this.decimals = decimals || 0;
    this.current = 0;
    this.target = 0;
    this.previous = 0;
    this.animProgress = 1;
    this.animDuration = 0.6;
    this.highlightTimer = 0; // time remaining for highlight
    this.formatter = null;   // custom formatter
    this.visible = true;
  }

  setValue(v) {
    if (Math.abs(v - this.target) < 0.001) return;
    this.previous = this.current;
    this.target = v;
    this.animProgress = 0;
    this.highlightTimer = 0.8; // highlight for 0.8s after change
  }

  update(dt) {
    if (this.animProgress < 1) {
      this.animProgress = Math.min(1, this.animProgress + dt / this.animDuration);
      const ease = easeOutCubic(this.animProgress);
      this.current = lerp(this.previous, this.target, ease);
    }
    if (this.highlightTimer > 0) {
      this.highlightTimer = Math.max(0, this.highlightTimer - dt);
    }
  }

  getDisplayValue() {
    if (this.formatter) return this.formatter(this.current);
    if (this.unit === '$') return formatCurrency(this.current);
    return formatNumber(this.current, this.decimals);
  }

  isHighlighted() {
    return this.highlightTimer > 0;
  }

  getHighlightAlpha() {
    return Math.min(1, this.highlightTimer / 0.3);
  }
}

export class MetricRibbon {
  constructor(options = {}) {
    this.x = options.x || 0;
    this.y = options.y || 0;
    this.width = options.width || 800;
    this.height = 36;
    this.padding = 16;

    // Metric definitions
    this.metrics = {
      totalCost: new AnimatedMetric('Cost', '$'),
      reserveCost: new AnimatedMetric('Reserve', '$'),
      reserveMW: new AnimatedMetric('Reserve', 'MW'),
      bottleneckZone: new AnimatedMetric('Bottleneck', ''),
      shadowPressure: new AnimatedMetric('\u03BC_max', '', 1),
      coverage: new AnimatedMetric('Coverage', '', 3),
      transferPressure: new AnimatedMetric('\u03BB_max', '', 1)
    };

    // Bottleneck zone has a custom formatter
    this.metrics.bottleneckZone.formatter = (v) => `Z${Math.round(v)}`;
    this.metrics.coverage.formatter = (v) => v.toFixed(3);

    // Show/hide transfer
    this.showCoupled = false;

    // Display order
    this.displayOrder = ['totalCost', 'reserveMW', 'bottleneckZone', 'shadowPressure', 'coverage'];
  }

  setMetrics(data) {
    if (data.totalCost !== undefined) this.metrics.totalCost.setValue(data.totalCost);
    if (data.reserveCost !== undefined) this.metrics.reserveCost.setValue(data.reserveCost);
    if (data.reserveMW !== undefined) this.metrics.reserveMW.setValue(data.reserveMW);
    if (data.bottleneckZone !== undefined) this.metrics.bottleneckZone.setValue(data.bottleneckZone);
    if (data.shadowPressure !== undefined) this.metrics.shadowPressure.setValue(data.shadowPressure);
    if (data.coverage !== undefined) this.metrics.coverage.setValue(data.coverage);
    if (data.transferPressure !== undefined) this.metrics.transferPressure.setValue(data.transferPressure);
  }

  setCoupled(enabled) {
    this.showCoupled = enabled;
    if (enabled && this.displayOrder.indexOf('transferPressure') === -1) {
      this.displayOrder.push('transferPressure');
    } else if (!enabled) {
      const idx = this.displayOrder.indexOf('transferPressure');
      if (idx >= 0) this.displayOrder.splice(idx, 1);
    }
  }

  update(dt) {
    for (const key in this.metrics) {
      this.metrics[key].update(dt);
    }
  }

  render(ctx) {
    ctx.save();

    // 1. Semi-transparent dark background strip
    ctx.fillStyle = 'rgba(45, 45, 45, 0.85)';
    this._roundedRect(ctx, this.x, this.y, this.width, this.height, 6);
    ctx.fill();

    // Build display strings and measure
    const items = [];
    for (let i = 0; i < this.displayOrder.length; i++) {
      const key = this.displayOrder[i];
      const m = this.metrics[key];
      if (!m.visible) continue;

      const label = m.label;
      const value = m.getDisplayValue();
      const unit = m.unit === '$' ? '/hr' : (m.unit ? ' ' + m.unit : '');
      items.push({
        label: label,
        value: value,
        unit: unit,
        highlighted: m.isHighlighted(),
        highlightAlpha: m.getHighlightAlpha()
      });
    }

    if (items.length === 0) {
      ctx.restore();
      return;
    }

    // Layout: evenly distribute items across the ribbon width
    const usableWidth = this.width - this.padding * 2;
    const itemWidth = usableWidth / items.length;
    const centerY = this.y + this.height / 2;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const itemCenterX = this.x + this.padding + itemWidth * (i + 0.5);

      // Separator line (except before first)
      if (i > 0) {
        const sepX = this.x + this.padding + itemWidth * i;
        ctx.beginPath();
        ctx.moveTo(sepX, this.y + 8);
        ctx.lineTo(sepX, this.y + this.height - 8);
        ctx.strokeStyle = 'rgba(250, 246, 240, 0.15)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // 5. Label (sans-serif)
      ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(250, 246, 240, 0.5)';

      const labelText = item.label + ' ';
      const labelWidth = ctx.measureText(labelText).width;

      // 5. Value (monospace numbers)
      ctx.font = 'bold 13px "SF Mono", "Menlo", "Monaco", monospace';
      const valueText = item.value + item.unit;
      const valueWidth = ctx.measureText(valueText).width;

      const totalTextWidth = labelWidth + valueWidth;
      const textStartX = itemCenterX - totalTextWidth / 2;

      // Draw label
      ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(250, 246, 240, 0.5)';
      ctx.fillText(labelText, textStartX, centerY);

      // 4. Changed values briefly highlight in ember orange
      if (item.highlighted) {
        const highlightR = 232, highlightG = 118, highlightB = 58;
        const baseR = 250, baseG = 246, baseB = 240;
        const a = item.highlightAlpha;
        const r = Math.round(lerp(baseR, highlightR, a));
        const g = Math.round(lerp(baseG, highlightG, a));
        const b = Math.round(lerp(baseB, highlightB, a));
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
      } else {
        ctx.fillStyle = 'rgba(250, 246, 240, 0.9)';
      }

      // Draw value
      ctx.font = 'bold 13px "SF Mono", "Menlo", "Monaco", monospace';
      ctx.fillText(valueText, textStartX + labelWidth, centerY);
    }

    ctx.restore();
  }

  _roundedRect(ctx, x, y, w, h, r) {
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
}
