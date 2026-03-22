// reserveBars.js — Per-Zone Reserve Bars
// Animated vertical bars showing reserve requirement per zone

const EMBER_ORANGE = '#E8763A';
const CORAL_RED = '#D94F4F';
const GRAPHITE = '#2D2D2D';
const TEAL = '#1A7A6D';

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

export class ReserveBars {
  constructor(options = {}) {
    this.x = options.x || 50;
    this.y = options.y || 400;
    this.width = options.width || 400;
    this.height = options.height || 200;
    this.zoneCount = options.zoneCount || 10;

    // Default zone colors: teal gradient
    this.colors = options.colors || this._generateZoneColors(this.zoneCount);

    // Reserve values (target)
    this.targetReserves = new Float64Array(this.zoneCount);
    // Current animated values
    this.currentReserves = new Float64Array(this.zoneCount);
    // Previous values (for animation start)
    this.previousReserves = new Float64Array(this.zoneCount);

    // Dual prices (glow intensity)
    this.duals = new Float64Array(this.zoneCount);

    // Animation state
    this.animProgress = new Float64Array(this.zoneCount);
    for (let i = 0; i < this.zoneCount; i++) {
      this.animProgress[i] = 1; // start fully converged
    }
    this.animDuration = 0.5; // seconds

    // Highlight
    this.highlightedZone = -1;

    // Max value for normalization
    this.maxReserve = 100;
    this.activeZoneCount = this.zoneCount;
  }

  _generateZoneColors(count) {
    const colors = [];
    for (let i = 0; i < count; i++) {
      const t = i / (count - 1);
      const r = Math.round(lerp(26, 42, t));
      const g = Math.round(lerp(122, 140, t));
      const b = Math.round(lerp(109, 120, t));
      colors.push(`rgb(${r}, ${g}, ${b})`);
    }
    return colors;
  }

  setReserves(values) {
    this.activeZoneCount = Math.max(1, Math.min(this.zoneCount, values.length));
    for (let i = 0; i < this.zoneCount && i < values.length; i++) {
      this.previousReserves[i] = this.currentReserves[i];
      this.targetReserves[i] = values[i];
      this.animProgress[i] = 0;
    }
    for (let i = values.length; i < this.zoneCount; i++) {
      this.previousReserves[i] = this.currentReserves[i];
      this.targetReserves[i] = 0;
      this.animProgress[i] = 0;
    }
    // Recompute max
    let max = 0;
    for (let i = 0; i < this.activeZoneCount; i++) {
      if (this.targetReserves[i] > max) max = this.targetReserves[i];
    }
    this.maxReserve = max > 0 ? max * 1.2 : 100;
  }

  setDuals(values) {
    for (let i = 0; i < this.zoneCount && i < values.length; i++) {
      this.duals[i] = values[i];
    }
    for (let i = values.length; i < this.zoneCount; i++) {
      this.duals[i] = 0;
    }
  }

  highlightZone(index) {
    this.highlightedZone = index;
  }

  update(dt) {
    for (let i = 0; i < this.zoneCount; i++) {
      if (this.animProgress[i] < 1) {
        this.animProgress[i] = Math.min(1, this.animProgress[i] + dt / this.animDuration);
        const ease = easeOutCubic(this.animProgress[i]);
        this.currentReserves[i] = lerp(this.previousReserves[i], this.targetReserves[i], ease);
      }
    }
  }

  render(ctx) {
    const count = Math.max(1, this.activeZoneCount);
    const barSpacing = this.width / count;
    const barWidth = barSpacing * 0.6;
    const barGap = barSpacing * 0.4;
    const baselineY = this.y + this.height;
    const cornerRadius = 3;

    // Find max dual for normalization
    let maxDual = 0;
    for (let i = 0; i < count; i++) {
      if (this.duals[i] > maxDual) maxDual = this.duals[i];
    }
    if (maxDual === 0) maxDual = 1;

    // 1. Baseline
    ctx.beginPath();
    ctx.moveTo(this.x, baselineY);
    ctx.lineTo(this.x + this.width, baselineY);
    ctx.strokeStyle = GRAPHITE;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3;
    ctx.stroke();
    ctx.globalAlpha = 1;

    for (let i = 0; i < count; i++) {
      const barX = this.x + i * barSpacing + barGap / 2;
      const barH = (this.currentReserves[i] / this.maxReserve) * this.height;
      const barY = baselineY - barH;
      const isHighlighted = (i === this.highlightedZone);

      // 3. Glow effect for high dual prices
      if (this.duals[i] > 0.01) {
        const glowIntensity = this.duals[i] / maxDual;
        const glowRadius = barWidth * 0.8 + glowIntensity * 12;

        // Determine glow color: orange for moderate, red for high
        const glowR = Math.round(lerp(232, 217, glowIntensity));
        const glowG = Math.round(lerp(118, 79, glowIntensity));
        const glowB = Math.round(lerp(58, 79, glowIntensity));

        ctx.save();
        ctx.shadowColor = `rgba(${glowR}, ${glowG}, ${glowB}, ${glowIntensity * 0.6})`;
        ctx.shadowBlur = glowRadius;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;

        // Draw glow source rect (invisible, just for shadow)
        ctx.fillStyle = `rgba(${glowR}, ${glowG}, ${glowB}, ${glowIntensity * 0.15})`;
        this._roundedRectTop(ctx, barX, barY, barWidth, barH, cornerRadius);
        ctx.fill();
        ctx.restore();
      }

      // 2. Bar body with rounded top
      const barColor = isHighlighted ? TEAL : this.colors[i];

      // Gradient fill for bar
      if (barH > 0) {
        const grad = ctx.createLinearGradient(barX, barY, barX, baselineY);

        if (this.duals[i] > 0.5) {
          const dualNorm = Math.min(1, this.duals[i] / maxDual);
          // Blend toward ember orange/red based on dual
          grad.addColorStop(0, this._blendColor(barColor, EMBER_ORANGE, dualNorm * 0.6));
          grad.addColorStop(1, barColor);
        } else {
          grad.addColorStop(0, barColor);
          grad.addColorStop(1, this._darken(barColor, 0.15));
        }

        ctx.fillStyle = grad;
        this._roundedRectTop(ctx, barX, barY, barWidth, barH, cornerRadius);
        ctx.fill();
      }

      // Highlight border
      if (isHighlighted) {
        ctx.strokeStyle = TEAL;
        ctx.lineWidth = 2;
        this._roundedRectTop(ctx, barX, barY, barWidth, barH, cornerRadius);
        ctx.stroke();
      }

      // 4. Zone labels below bars
      ctx.fillStyle = GRAPHITE;
      ctx.font = '11px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.globalAlpha = isHighlighted ? 1 : 0.6;
      ctx.fillText(`Z${i + 1}`, barX + barWidth / 2, baselineY + 6);
      ctx.globalAlpha = 1;

      // 5. Value labels above highlighted bars
      if (isHighlighted && this.currentReserves[i] > 0) {
        const valueText = this.currentReserves[i].toFixed(1);
        ctx.fillStyle = GRAPHITE;
        ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(valueText, barX + barWidth / 2, barY - 6);
      }
    }
  }

  _roundedRectTop(ctx, x, y, w, h, r) {
    if (h < r * 2) r = h / 2;
    if (r < 0) r = 0;
    ctx.beginPath();
    ctx.moveTo(x, y + h);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h);
    ctx.closePath();
  }

  _darken(colorStr, amount) {
    const match = colorStr.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (!match) return colorStr;
    const r = Math.max(0, Math.round(parseInt(match[1]) * (1 - amount)));
    const g = Math.max(0, Math.round(parseInt(match[2]) * (1 - amount)));
    const b = Math.max(0, Math.round(parseInt(match[3]) * (1 - amount)));
    return `rgb(${r}, ${g}, ${b})`;
  }

  _blendColor(colorStr, targetHex, t) {
    const match = colorStr.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (!match) return colorStr;
    const r1 = parseInt(match[1]), g1 = parseInt(match[2]), b1 = parseInt(match[3]);
    const r2 = parseInt(targetHex.slice(1, 3), 16);
    const g2 = parseInt(targetHex.slice(3, 5), 16);
    const b2 = parseInt(targetHex.slice(5, 7), 16);
    const r = Math.round(lerp(r1, r2, t));
    const g = Math.round(lerp(g1, g2, t));
    const b = Math.round(lerp(b1, b2, t));
    return `rgb(${r}, ${g}, ${b})`;
  }
}
