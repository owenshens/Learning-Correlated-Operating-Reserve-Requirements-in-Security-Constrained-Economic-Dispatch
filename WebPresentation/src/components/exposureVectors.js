// exposureVectors.js — Luminous Direction Vectors
// Arrows from zones into the uncertainty ellipsoid showing exposure directions

const TEAL = '#1A7A6D';
const TEAL_HIGHLIGHT = 'rgba(26, 122, 109, 0.95)';
const GRAPHITE = '#2D2D2D';
const EMBER_ORANGE = '#E8763A';

function lerp(a, b, t) {
  return a + (b - a) * t;
}

class VectorState {
  constructor() {
    this.fromX = 0;
    this.fromY = 0;
    this.toX = 0;
    this.toY = 0;
    this.zoneIndex = -1;
    this.supportX = 0;
    this.supportY = 0;
    this.hasSupportPoint = false;
  }
}

export class ExposureVectors {
  constructor(options = {}) {
    this.color = options.color || TEAL;
    this.lineWidth = options.lineWidth || 1.5;

    // Parse color
    this.colorR = parseInt(this.color.slice(1, 3), 16);
    this.colorG = parseInt(this.color.slice(3, 5), 16);
    this.colorB = parseInt(this.color.slice(5, 7), 16);

    // Pre-allocated vector pool
    this.maxVectors = 20;
    this.vectors = [];
    for (let i = 0; i < this.maxVectors; i++) {
      this.vectors.push(new VectorState());
    }
    this.activeCount = 0;

    // Highlight state
    this.highlightedZone = -1;

    // Animation
    this.time = 0;
    this.pulseSpeed = 3; // radians per second

    // Support point pulse particles
    this.supportPulses = []; // {x, y, targetX, targetY, progress, active}
    this.maxPulses = 20;
    for (let i = 0; i < this.maxPulses; i++) {
      this.supportPulses.push({ active: false, x: 0, y: 0, targetX: 0, targetY: 0, progress: 0 });
    }
    this.pulseSpawnTimer = 0;
    this.pulseSpawnInterval = 0.8;

    // Arrowhead size
    this.arrowSize = 8;
    this.arrowAngle = Math.PI / 7;
  }

  setVectors(vectors) {
    this.activeCount = Math.min(vectors.length, this.maxVectors);
    for (let i = 0; i < this.activeCount; i++) {
      const v = this.vectors[i];
      const src = vectors[i];
      v.fromX = src.fromX;
      v.fromY = src.fromY;
      v.toX = src.toX;
      v.toY = src.toY;
      v.zoneIndex = src.zoneIndex !== undefined ? src.zoneIndex : i;
      v.hasSupportPoint = false;
    }
  }

  highlightVector(zoneIndex) {
    this.highlightedZone = zoneIndex;
  }

  setSupportPoints(points) {
    for (let i = 0; i < this.activeCount && i < points.length; i++) {
      this.vectors[i].supportX = points[i].x;
      this.vectors[i].supportY = points[i].y;
      this.vectors[i].hasSupportPoint = true;
    }
  }

  update(dt) {
    this.time += dt;

    // Spawn support point pulses for highlighted vector
    this.pulseSpawnTimer -= dt;
    if (this.pulseSpawnTimer <= 0 && this.highlightedZone >= 0) {
      this.pulseSpawnTimer = this.pulseSpawnInterval;

      // Find the highlighted vector
      for (let i = 0; i < this.activeCount; i++) {
        const v = this.vectors[i];
        if (v.zoneIndex === this.highlightedZone && v.hasSupportPoint) {
          this._spawnPulse(v.supportX, v.supportY, v.fromX, v.fromY);
          break;
        }
      }
    }

    // Update pulses
    for (let i = 0; i < this.maxPulses; i++) {
      const p = this.supportPulses[i];
      if (!p.active) continue;
      p.progress += dt * 0.8;
      p.x = lerp(p.startX, p.targetX, p.progress);
      p.y = lerp(p.startY, p.targetY, p.progress);
      if (p.progress >= 1) {
        p.active = false;
      }
    }
  }

  _spawnPulse(fromX, fromY, toX, toY) {
    for (let i = 0; i < this.maxPulses; i++) {
      if (!this.supportPulses[i].active) {
        this.supportPulses[i].active = true;
        this.supportPulses[i].startX = fromX;
        this.supportPulses[i].startY = fromY;
        this.supportPulses[i].x = fromX;
        this.supportPulses[i].y = fromY;
        this.supportPulses[i].targetX = toX;
        this.supportPulses[i].targetY = toY;
        this.supportPulses[i].progress = 0;
        return;
      }
    }
  }

  render(ctx) {
    ctx.save();

    // Draw vectors
    for (let i = 0; i < this.activeCount; i++) {
      const v = this.vectors[i];
      const isHighlighted = (v.zoneIndex === this.highlightedZone);

      // Compute direction vector
      const dx = v.toX - v.fromX;
      const dy = v.toY - v.fromY;
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len < 1) continue;

      const dirX = dx / len;
      const dirY = dy / len;

      if (isHighlighted) {
        this._renderHighlightedVector(ctx, v, dirX, dirY, len);
      } else {
        this._renderDefaultVector(ctx, v, dirX, dirY, len);
      }
    }

    // Draw support point pulses
    for (let i = 0; i < this.maxPulses; i++) {
      const p = this.supportPulses[i];
      if (!p.active) continue;

      const alpha = Math.max(0, 1 - p.progress);
      const size = 2 + p.progress * 1;

      ctx.beginPath();
      ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${alpha * 0.6})`;
      ctx.fill();
    }

    ctx.restore();
  }

  _renderDefaultVector(ctx, v, dirX, dirY, len) {
    // 2. Default: thin, semi-transparent graphite
    ctx.beginPath();
    ctx.moveTo(v.fromX, v.fromY);
    ctx.lineTo(v.toX, v.toY);
    ctx.strokeStyle = 'rgba(45, 45, 45, 0.15)';
    ctx.lineWidth = this.lineWidth * 0.7;
    ctx.stroke();

    // Support point dot (small)
    if (v.hasSupportPoint) {
      ctx.beginPath();
      ctx.arc(v.supportX, v.supportY, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, 0.3)`;
      ctx.fill();
    }
  }

  _renderHighlightedVector(ctx, v, dirX, dirY, len) {
    // 3. Highlighted: thicker, bright teal, with arrowhead
    const pulseAlpha = 0.7 + 0.3 * Math.sin(this.time * this.pulseSpeed);

    // Main line
    ctx.beginPath();
    ctx.moveTo(v.fromX, v.fromY);
    ctx.lineTo(v.toX, v.toY);
    ctx.strokeStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${pulseAlpha})`;
    ctx.lineWidth = this.lineWidth * 1.8;
    ctx.stroke();

    // Arrowhead at the to-end
    const angle = Math.atan2(dirY, dirX);
    const aSize = this.arrowSize;

    ctx.beginPath();
    ctx.moveTo(v.toX, v.toY);
    ctx.lineTo(
      v.toX - aSize * Math.cos(angle - this.arrowAngle),
      v.toY - aSize * Math.sin(angle - this.arrowAngle)
    );
    ctx.lineTo(
      v.toX - aSize * Math.cos(angle + this.arrowAngle),
      v.toY - aSize * Math.sin(angle + this.arrowAngle)
    );
    ctx.closePath();
    ctx.fillStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${pulseAlpha})`;
    ctx.fill();

    // 4. Support point: bright pulsing dot
    if (v.hasSupportPoint) {
      const spPulse = 0.6 + 0.4 * Math.sin(this.time * 4);
      const spRadius = 4 + spPulse * 1.5;

      // Glow
      const grad = ctx.createRadialGradient(v.supportX, v.supportY, 0, v.supportX, v.supportY, spRadius * 3);
      grad.addColorStop(0, `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${spPulse * 0.3})`);
      grad.addColorStop(1, `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(v.supportX, v.supportY, spRadius * 3, 0, Math.PI * 2);
      ctx.fill();

      // Core dot
      ctx.beginPath();
      ctx.arc(v.supportX, v.supportY, spRadius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${spPulse})`;
      ctx.fill();
    }

    // 5. Faint dashed extension beyond support point
    if (v.hasSupportPoint) {
      const extLen = 30;
      const extEndX = v.supportX + dirX * extLen;
      const extEndY = v.supportY + dirY * extLen;

      ctx.beginPath();
      ctx.moveTo(v.supportX, v.supportY);
      ctx.lineTo(extEndX, extEndY);
      ctx.strokeStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, 0.2)`;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
}
