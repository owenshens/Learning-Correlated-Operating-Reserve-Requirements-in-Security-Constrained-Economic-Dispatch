// ellipsoid.js — The Uncertainty Shape
// Animated 2D ellipse representing the gauge-based uncertainty set U_{theta,rho}

const TEAL = '#1A7A6D';
const TEAL_FILL = 'rgba(26, 122, 109, 0.08)';
const AXIS_COLOR = 'rgba(26, 122, 109, 0.12)';

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

// Decompose a 2x2 Cholesky factor into ellipse parameters
function choleskyToEllipse(L) {
  // L is [[a, 0], [b, c]]
  // M = L * L^T
  const a = L[0][0], b = L[1][0], c = L[1][1];
  const m00 = a * a;
  const m01 = a * b;
  const m10 = a * b;
  const m11 = b * b + c * c;

  // Eigenvalues of M give squared semi-axes
  const trace = m00 + m11;
  const det = m00 * m11 - m01 * m10;
  const disc = Math.sqrt(Math.max(0, trace * trace - 4 * det));
  const lam1 = (trace + disc) / 2;
  const lam2 = (trace - disc) / 2;

  const semiA = Math.sqrt(Math.max(0.01, lam1));
  const semiB = Math.sqrt(Math.max(0.01, lam2));

  // Rotation angle from eigenvector of larger eigenvalue
  let angle = 0;
  if (Math.abs(m01) > 1e-10) {
    angle = Math.atan2(lam1 - m00, m01);
  } else if (m11 > m00) {
    angle = Math.PI / 2;
  }

  return { semiA, semiB, angle };
}

class Particle {
  constructor(phaseOffset, speedFactor) {
    this.phase = phaseOffset;
    this.speed = 0.3 + speedFactor * 0.4; // radians per second
    this.drift = 0; // perpendicular drift for breathing
    this.driftTarget = 0;
    this.driftSpeed = 0.5 + Math.random() * 0.5;
    this.alpha = 0.5 + Math.random() * 0.4;
    this.radius = 1.5 + Math.random() * 1.5;
    this.nextDriftChange = Math.random() * 2;
  }

  update(dt) {
    this.phase += this.speed * dt;
    if (this.phase > Math.PI * 2) this.phase -= Math.PI * 2;

    this.nextDriftChange -= dt;
    if (this.nextDriftChange <= 0) {
      this.driftTarget = (Math.random() - 0.5) * 6;
      this.nextDriftChange = 1 + Math.random() * 2;
    }

    this.drift += (this.driftTarget - this.drift) * dt * this.driftSpeed;
  }
}

export class Ellipsoid {
  constructor(options = {}) {
    this.cx = options.cx || 300;
    this.cy = options.cy || 300;
    this.scale = options.scale || 100;
    this.color = options.color || TEAL;
    const particleCount = options.particleCount || 10;

    // Current ellipse params
    this.currentL = [[1, 0], [0, 1]];
    this.currentParams = { semiA: 1, semiB: 1, angle: 0 };

    // Morph animation state
    this.morphing = false;
    this.morphStartParams = { semiA: 1, semiB: 1, angle: 0 };
    this.morphEndParams = { semiA: 1, semiB: 1, angle: 0 };
    this.morphElapsed = 0;
    this.morphDuration = 0.6;

    // Particle pool
    this.particles = [];
    for (let i = 0; i < particleCount; i++) {
      const phaseOffset = (i / particleCount) * Math.PI * 2;
      const speedFactor = Math.random();
      this.particles.push(new Particle(phaseOffset, speedFactor));
    }

    // Highlight state
    this.highlightDirection = null;
    this.highlightPulse = 0;

    // Principal axes visibility
    this.showAxes = true;
  }

  setL(L_2x2) {
    this.currentL = L_2x2;
    this.currentParams = choleskyToEllipse(L_2x2);
    this.morphing = false;
  }

  morphTo(L_2x2, duration = 600) {
    this.morphStartParams = { ...this.currentParams };
    this.morphEndParams = choleskyToEllipse(L_2x2);
    this.currentL = L_2x2;
    this.morphElapsed = 0;
    this.morphDuration = duration / 1000; // convert ms to seconds
    this.morphing = true;

    // Handle angle wrapping for smooth rotation
    let dAngle = this.morphEndParams.angle - this.morphStartParams.angle;
    if (dAngle > Math.PI) dAngle -= 2 * Math.PI;
    if (dAngle < -Math.PI) dAngle += 2 * Math.PI;
    this.morphEndParams.angle = this.morphStartParams.angle + dAngle;
  }

  highlightSupportPoint(direction) {
    // direction: {x, y} unit vector
    this.highlightDirection = direction;
    this.highlightPulse = 0;
  }

  clearHighlight() {
    this.highlightDirection = null;
  }

  getPointOnBoundary(angle) {
    const p = this.currentParams;
    // Point on unit circle
    const ux = Math.cos(angle);
    const uy = Math.sin(angle);
    // Scale by semi-axes
    const rx = ux * p.semiA;
    const ry = uy * p.semiB;
    // Rotate to world
    const cosA = Math.cos(p.angle);
    const sinA = Math.sin(p.angle);
    const wx = rx * cosA - ry * sinA;
    const wy = rx * sinA + ry * cosA;
    return {
      x: this.cx + wx * this.scale,
      y: this.cy + wy * this.scale
    };
  }

  getBoundaryPoints(count = 64) {
    const points = [];
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      points.push(this.getPointOnBoundary(angle));
    }
    return points;
  }

  update(dt) {
    // Update morph animation
    if (this.morphing) {
      this.morphElapsed += dt;
      const t = Math.min(1, this.morphElapsed / this.morphDuration);
      const ease = easeOutCubic(t);

      this.currentParams.semiA = this.morphStartParams.semiA +
        (this.morphEndParams.semiA - this.morphStartParams.semiA) * ease;
      this.currentParams.semiB = this.morphStartParams.semiB +
        (this.morphEndParams.semiB - this.morphStartParams.semiB) * ease;
      this.currentParams.angle = this.morphStartParams.angle +
        (this.morphEndParams.angle - this.morphStartParams.angle) * ease;

      if (t >= 1) {
        this.morphing = false;
        this.currentParams = { ...this.morphEndParams };
      }
    }

    // Update particles
    for (let i = 0; i < this.particles.length; i++) {
      this.particles[i].update(dt);
    }

    // Update highlight pulse
    if (this.highlightDirection) {
      this.highlightPulse += dt;
    }
  }

  render(ctx) {
    const p = this.currentParams;
    const cx = this.cx;
    const cy = this.cy;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(p.angle);

    // 1. Fill: subtle semi-transparent teal
    ctx.beginPath();
    ctx.ellipse(0, 0, p.semiA * this.scale, p.semiB * this.scale, 0, 0, Math.PI * 2);
    ctx.fillStyle = TEAL_FILL;
    ctx.fill();

    // 4. Faint grid lines showing principal axes
    if (this.showAxes) {
      ctx.strokeStyle = AXIS_COLOR;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);

      // Major axis
      ctx.beginPath();
      ctx.moveTo(-p.semiA * this.scale, 0);
      ctx.lineTo(p.semiA * this.scale, 0);
      ctx.stroke();

      // Minor axis
      ctx.beginPath();
      ctx.moveTo(0, -p.semiB * this.scale);
      ctx.lineTo(0, p.semiB * this.scale);
      ctx.stroke();

      ctx.setLineDash([]);
    }

    // 2. Boundary: smooth ellipse outline
    ctx.beginPath();
    ctx.ellipse(0, 0, p.semiA * this.scale, p.semiB * this.scale, 0, 0, Math.PI * 2);
    ctx.strokeStyle = this.color;
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.restore();

    // 3. Particles drifting along boundary
    for (let i = 0; i < this.particles.length; i++) {
      const part = this.particles[i];
      const angle = part.phase;

      // Point on ellipse in local coords
      const lx = Math.cos(angle) * p.semiA * this.scale;
      const ly = Math.sin(angle) * p.semiB * this.scale;

      // Normal direction at this point (for drift)
      const nx = Math.cos(angle) / p.semiA;
      const ny = Math.sin(angle) / p.semiB;
      const nLen = Math.sqrt(nx * nx + ny * ny);
      const nnx = nx / nLen;
      const nny = ny / nLen;

      // Apply drift along normal
      const dlx = lx + nnx * part.drift;
      const dly = ly + nny * part.drift;

      // Rotate to world coords
      const cosA = Math.cos(p.angle);
      const sinA = Math.sin(p.angle);
      const wx = dlx * cosA - dly * sinA + cx;
      const wy = dlx * sinA + dly * cosA + cy;

      ctx.beginPath();
      ctx.arc(wx, wy, part.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(26, 122, 109, ${part.alpha})`;
      ctx.fill();
    }

    // Highlight support point
    if (this.highlightDirection) {
      const dir = this.highlightDirection;
      // Find the support point: argmax <dir, L*u> over ||u||=1
      // = L^T * dir / ||L^T * dir||, then multiply by L
      const L = this.currentL;
      // L^T * dir
      const ltd_x = L[0][0] * dir.x + L[1][0] * dir.y;
      const ltd_y = L[0][1] * dir.x + L[1][1] * dir.y;
      const ltdLen = Math.sqrt(ltd_x * ltd_x + ltd_y * ltd_y);

      if (ltdLen > 1e-10) {
        // Unit vector
        const u_x = ltd_x / ltdLen;
        const u_y = ltd_y / ltdLen;
        // Support point = L * u (in local coords, pre-scale)
        const sp_x = (L[0][0] * u_x + L[0][1] * u_y) * this.scale;
        const sp_y = (L[1][0] * u_x + L[1][1] * u_y) * this.scale;

        const pulseAlpha = 0.6 + 0.4 * Math.sin(this.highlightPulse * 4);
        const pulseRadius = 4 + 2 * Math.sin(this.highlightPulse * 3);

        // Draw the support point
        ctx.beginPath();
        ctx.arc(cx + sp_x, cy + sp_y, pulseRadius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(26, 122, 109, ${pulseAlpha})`;
        ctx.fill();

        // Outer glow ring
        ctx.beginPath();
        ctx.arc(cx + sp_x, cy + sp_y, pulseRadius + 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(26, 122, 109, ${pulseAlpha * 0.3})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
  }
}
