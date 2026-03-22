// gradientFlow.js — Backward Gradient Animation
// Particles/energy flowing backward from shadow prices through the optimization chain

const EMBER_ORANGE = '#E8763A';
const GRAPHITE = '#2D2D2D';

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// Evaluate a cubic bezier at parameter t
function bezierPoint(p0, p1, p2, p3, t) {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const t2 = t * t;
  return {
    x: mt2 * mt * p0.x + 3 * mt2 * t * p1.x + 3 * mt * t2 * p2.x + t2 * t * p3.x,
    y: mt2 * mt * p0.y + 3 * mt2 * t * p1.y + 3 * mt * t2 * p2.y + t2 * t * p3.y
  };
}

// Pre-allocated particle for pool
class FlowParticle {
  constructor() {
    this.active = false;
    this.pathIndex = 0;
    this.progress = 0;     // 0 to 1 along path
    this.speed = 0;
    this.alpha = 1;
    this.size = 2;
    this.trailPositions = []; // circular buffer of recent positions
    this.trailIndex = 0;
    this.isPulse = false;
    this.brightness = 1;
  }

  reset(pathIndex, speed, size, trailLength, isPulse) {
    this.active = true;
    this.pathIndex = pathIndex;
    this.progress = 0;
    this.speed = speed;
    this.alpha = 1;
    this.size = size;
    this.isPulse = isPulse || false;
    this.brightness = isPulse ? 1.5 : 1;

    // Initialize trail buffer
    this.trailPositions = [];
    for (let i = 0; i < trailLength; i++) {
      this.trailPositions.push({ x: 0, y: 0, active: false });
    }
    this.trailIndex = 0;
  }

  recordTrailPosition(x, y) {
    this.trailPositions[this.trailIndex] = { x, y, active: true };
    this.trailIndex = (this.trailIndex + 1) % this.trailPositions.length;
  }
}

// Precomputed bezier path from waypoints
class FlowPath {
  constructor(from, waypoints, to, intensity) {
    this.from = from;
    this.to = to;
    this.intensity = intensity || 1;

    // Build bezier control points from from -> waypoints -> to
    const allPoints = [from, ...waypoints, to];
    this.segments = [];

    if (allPoints.length === 2) {
      // Straight line — add simple bezier
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      this.segments.push({
        p0: from,
        p1: { x: from.x + dx * 0.33, y: from.y + dy * 0.33 },
        p2: { x: from.x + dx * 0.66, y: from.y + dy * 0.66 },
        p3: to
      });
    } else {
      // Create smooth bezier segments through waypoints
      for (let i = 0; i < allPoints.length - 1; i++) {
        const p0 = allPoints[i];
        const p3 = allPoints[i + 1];
        const dx = p3.x - p0.x;
        const dy = p3.y - p0.y;

        // Compute tangent-based control points for smoothness
        let tangentIn = { x: dx, y: dy };
        let tangentOut = { x: dx, y: dy };

        if (i > 0) {
          const prev = allPoints[i - 1];
          tangentIn = { x: (p3.x - prev.x) * 0.25, y: (p3.y - prev.y) * 0.25 };
        }
        if (i < allPoints.length - 2) {
          const next = allPoints[i + 2];
          tangentOut = { x: (next.x - p0.x) * 0.25, y: (next.y - p0.y) * 0.25 };
        }

        this.segments.push({
          p0: p0,
          p1: { x: p0.x + tangentIn.x * 0.5, y: p0.y + tangentIn.y * 0.5 },
          p2: { x: p3.x - tangentOut.x * 0.5, y: p3.y - tangentOut.y * 0.5 },
          p3: p3
        });
      }
    }

    this.totalSegments = this.segments.length;
  }

  // Evaluate position at t in [0, 1]
  evaluate(t) {
    if (this.totalSegments === 0) return { ...this.from };
    const scaledT = t * this.totalSegments;
    const segIndex = Math.min(Math.floor(scaledT), this.totalSegments - 1);
    const localT = scaledT - segIndex;
    const seg = this.segments[segIndex];
    return bezierPoint(seg.p0, seg.p1, seg.p2, seg.p3, localT);
  }
}

export class GradientFlow {
  constructor(options = {}) {
    this.color = options.color || EMBER_ORANGE;
    this.particleSize = options.particleSize || 3;
    this.trailLength = options.trailLength || 5;

    // Parse base color for alpha manipulation
    this.colorR = parseInt(this.color.slice(1, 3), 16);
    this.colorG = parseInt(this.color.slice(3, 5), 16);
    this.colorB = parseInt(this.color.slice(5, 7), 16);

    // Flow paths
    this.paths = [];

    // Particle pool
    this.poolSize = 200;
    this.particles = [];
    for (let i = 0; i < this.poolSize; i++) {
      this.particles.push(new FlowParticle());
    }

    // Flow mode
    this.constantFlow = false;
    this.spawnTimers = []; // one per path
    this.spawnInterval = 0.3; // seconds between spawns per path

    // Pulse state
    this.pulseActive = false;
    this.pulseElapsed = 0;
    this.pulseDuration = 1;
    this.pulseWaveProgress = 0;

    // Impact ripples at endpoints
    this.ripples = []; // {x, y, radius, maxRadius, alpha}
    this.maxRipples = 20;
    for (let i = 0; i < this.maxRipples; i++) {
      this.ripples.push({ active: false, x: 0, y: 0, radius: 0, maxRadius: 0, alpha: 0 });
    }
  }

  setFlowPath(paths) {
    this.paths = paths.map(p => new FlowPath(p.from, p.waypoints || [], p.to, p.intensity));
    this.spawnTimers = this.paths.map(() => Math.random() * this.spawnInterval);
  }

  triggerPulse(duration = 1000) {
    this.pulseActive = true;
    this.pulseElapsed = 0;
    this.pulseDuration = duration / 1000;
    this.pulseWaveProgress = 0;

    // Spawn a burst of pulse particles on all paths
    for (let pi = 0; pi < this.paths.length; pi++) {
      const count = Math.ceil(3 * this.paths[pi].intensity);
      for (let k = 0; k < count; k++) {
        const particle = this._acquireParticle();
        if (!particle) break;
        const speed = 0.6 + Math.random() * 0.3;
        particle.reset(pi, speed, this.particleSize * 1.5, this.trailLength, true);
        particle.progress = k * 0.05;
      }
    }
  }

  setConstantFlow(enabled) {
    this.constantFlow = enabled;
  }

  _acquireParticle() {
    for (let i = 0; i < this.poolSize; i++) {
      if (!this.particles[i].active) return this.particles[i];
    }
    return null;
  }

  _spawnRipple(x, y) {
    for (let i = 0; i < this.maxRipples; i++) {
      if (!this.ripples[i].active) {
        this.ripples[i].active = true;
        this.ripples[i].x = x;
        this.ripples[i].y = y;
        this.ripples[i].radius = 2;
        this.ripples[i].maxRadius = 15 + Math.random() * 10;
        this.ripples[i].alpha = 0.6;
        return;
      }
    }
  }

  update(dt) {
    // Spawn particles for constant flow
    if (this.constantFlow) {
      for (let pi = 0; pi < this.paths.length; pi++) {
        this.spawnTimers[pi] -= dt;
        if (this.spawnTimers[pi] <= 0) {
          const interval = this.spawnInterval / Math.max(0.1, this.paths[pi].intensity);
          this.spawnTimers[pi] = interval;
          const particle = this._acquireParticle();
          if (particle) {
            const speed = 0.3 + Math.random() * 0.2;
            particle.reset(pi, speed, this.particleSize, this.trailLength, false);
          }
        }
      }
    }

    // Update pulse
    if (this.pulseActive) {
      this.pulseElapsed += dt;
      this.pulseWaveProgress = this.pulseElapsed / this.pulseDuration;
      if (this.pulseElapsed >= this.pulseDuration) {
        this.pulseActive = false;
      }
    }

    // Update particles
    for (let i = 0; i < this.poolSize; i++) {
      const p = this.particles[i];
      if (!p.active) continue;

      // Record current position for trail before moving
      if (p.pathIndex < this.paths.length) {
        const pos = this.paths[p.pathIndex].evaluate(p.progress);
        p.recordTrailPosition(pos.x, pos.y);
      }

      // Move backward along path (progress goes 0 -> 1, which is from -> to)
      p.progress += p.speed * dt;

      // Fade near end
      if (p.progress > 0.85) {
        p.alpha = Math.max(0, (1 - p.progress) / 0.15);
      }

      if (p.progress >= 1) {
        p.active = false;
        // Spawn ripple at endpoint
        if (p.pathIndex < this.paths.length) {
          const endPos = this.paths[p.pathIndex].to;
          this._spawnRipple(endPos.x, endPos.y);
        }
      }
    }

    // Update ripples
    for (let i = 0; i < this.maxRipples; i++) {
      const r = this.ripples[i];
      if (!r.active) continue;
      r.radius += dt * 40;
      r.alpha -= dt * 1.5;
      if (r.alpha <= 0 || r.radius >= r.maxRadius) {
        r.active = false;
      }
    }
  }

  render(ctx) {
    ctx.save();

    // 1. Draw flow path lines (subtle curved bezier)
    for (let pi = 0; pi < this.paths.length; pi++) {
      const path = this.paths[pi];
      ctx.beginPath();
      const steps = 30;
      for (let s = 0; s <= steps; s++) {
        const t = s / steps;
        const pt = path.evaluate(t);
        if (s === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.strokeStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${0.08 * path.intensity})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // 2-6. Draw particles with trails
    for (let i = 0; i < this.poolSize; i++) {
      const p = this.particles[i];
      if (!p.active || p.pathIndex >= this.paths.length) continue;

      const path = this.paths[p.pathIndex];
      const pos = path.evaluate(p.progress);

      // 5. Trail: afterimage particles with decreasing alpha
      const trailLen = p.trailPositions.length;
      for (let t = 0; t < trailLen; t++) {
        // Read trail in reverse order (most recent first)
        const idx = (p.trailIndex - 1 - t + trailLen * 2) % trailLen;
        const tp = p.trailPositions[idx];
        if (!tp.active) continue;

        const trailAlpha = p.alpha * (1 - (t + 1) / (trailLen + 1)) * 0.5;
        const trailSize = p.size * (1 - (t + 1) / (trailLen + 1)) * 0.8;

        if (trailAlpha < 0.01) continue;

        ctx.beginPath();
        ctx.arc(tp.x, tp.y, trailSize, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${trailAlpha})`;
        ctx.fill();
      }

      // 3-4. Main particle: glowing dot
      const intensityMult = path.intensity * p.brightness;
      const mainAlpha = Math.min(1, p.alpha * intensityMult);

      // Outer glow
      const glowRadius = p.size * 2.5;
      const glowGrad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowRadius);
      glowGrad.addColorStop(0, `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${mainAlpha * 0.4})`);
      glowGrad.addColorStop(1, `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, 0)`);
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2);
      ctx.fill();

      // Core dot
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${mainAlpha})`;
      ctx.fill();
    }

    // 6. Pulse wave origin glow
    if (this.pulseActive) {
      for (let pi = 0; pi < this.paths.length; pi++) {
        const path = this.paths[pi];
        const origin = path.from;
        const waveAlpha = Math.max(0, 1 - this.pulseWaveProgress) * 0.5;
        const waveRadius = 10 + this.pulseWaveProgress * 30;

        const grad = ctx.createRadialGradient(origin.x, origin.y, 0, origin.x, origin.y, waveRadius);
        grad.addColorStop(0, `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${waveAlpha})`);
        grad.addColorStop(1, `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, 0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(origin.x, origin.y, waveRadius, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 7. Impact ripples at endpoints
    for (let i = 0; i < this.maxRipples; i++) {
      const r = this.ripples[i];
      if (!r.active) continue;

      ctx.beginPath();
      ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${this.colorR}, ${this.colorG}, ${this.colorB}, ${r.alpha})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    ctx.restore();
  }
}
