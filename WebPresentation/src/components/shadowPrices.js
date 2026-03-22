// shadowPrices.js — Zone Pressure Overlay
// Visualizes dual variables as heat/pressure on zones

const EMBER_ORANGE = '#E8763A';
const CORAL_RED = '#D94F4F';

function lerp(a, b, t) {
  return a + (b - a) * t;
}

class ZoneDualState {
  constructor() {
    this.reserveDual = 0;
    this.targetReserveDual = 0;
    this.transferDual = 0;
    this.targetTransferDual = 0;
    this.x = 0;
    this.y = 0;
    this.radius = 40;
  }
}

export class ShadowPrices {
  constructor(options = {}) {
    this.maxIntensity = options.maxIntensity || 10;
    this.reserveColor = options.colors?.reserve || EMBER_ORANGE;
    this.transferColor = options.colors?.transfer || CORAL_RED;

    // Parse colors
    this.reserveR = parseInt(this.reserveColor.slice(1, 3), 16);
    this.reserveG = parseInt(this.reserveColor.slice(3, 5), 16);
    this.reserveB = parseInt(this.reserveColor.slice(5, 7), 16);

    this.transferR = parseInt(this.transferColor.slice(1, 3), 16);
    this.transferG = parseInt(this.transferColor.slice(3, 5), 16);
    this.transferB = parseInt(this.transferColor.slice(5, 7), 16);

    // Zone states (pre-allocated)
    this.zones = [];
    for (let i = 0; i < 10; i++) {
      this.zones.push(new ZoneDualState());
    }

    // Animation time
    this.time = 0;

    // Pulsing period
    this.pulsePeriod = 3.0; // seconds

    // Label visibility
    this.showLabels = true;

    // Smoothing speed
    this.smoothSpeed = 3;
  }

  setDuals(reserveDuals, transferDuals) {
    // Update max intensity for normalization
    let max = 0;
    for (let i = 0; i < 10; i++) {
      if (reserveDuals && i < reserveDuals.length) {
        this.zones[i].targetReserveDual = reserveDuals[i];
        if (reserveDuals[i] > max) max = reserveDuals[i];
      }
      if (transferDuals && i < transferDuals.length) {
        this.zones[i].targetTransferDual = transferDuals[i];
        if (transferDuals[i] > max) max = transferDuals[i];
      }
    }
    if (max > 0) this.maxIntensity = max;
  }

  // Set zone positions (called by orchestrator to align with zoneMap)
  setZonePositions(positions) {
    for (let i = 0; i < 10 && i < positions.length; i++) {
      this.zones[i].x = positions[i].x;
      this.zones[i].y = positions[i].y;
    }
  }

  // Set zone radii for glow sizing
  setZoneRadii(radii) {
    for (let i = 0; i < 10 && i < radii.length; i++) {
      this.zones[i].radius = radii[i];
    }
  }

  update(dt) {
    this.time += dt;

    // Smooth interpolation of dual values
    for (let i = 0; i < 10; i++) {
      const z = this.zones[i];
      const rate = Math.min(1, dt * this.smoothSpeed);
      z.reserveDual += (z.targetReserveDual - z.reserveDual) * rate;
      z.transferDual += (z.targetTransferDual - z.transferDual) * rate;
    }
  }

  render(ctx) {
    ctx.save();

    const maxI = this.maxIntensity > 0 ? this.maxIntensity : 1;

    for (let i = 0; i < 10; i++) {
      const z = this.zones[i];
      const reserveNorm = Math.min(1, z.reserveDual / maxI);
      const transferNorm = Math.min(1, z.transferDual / maxI);

      // Skip zones with no dual pressure
      if (reserveNorm < 0.005 && transferNorm < 0.005) continue;

      // 4. Gentle pulsing (sinusoidal alpha modulation, period ~3s)
      const pulsePhase = Math.sin((this.time / this.pulsePeriod) * Math.PI * 2 + i * 0.6);
      const pulseMult = 0.8 + 0.2 * pulsePhase;

      // 1-2. Reserve dual glow (ember orange)
      if (reserveNorm > 0.005) {
        const glowRadius = z.radius + reserveNorm * 30;
        const alpha = reserveNorm * 0.45 * pulseMult;

        const grad = ctx.createRadialGradient(z.x, z.y, 0, z.x, z.y, glowRadius);
        grad.addColorStop(0, `rgba(${this.reserveR}, ${this.reserveG}, ${this.reserveB}, ${alpha})`);
        grad.addColorStop(0.5, `rgba(${this.reserveR}, ${this.reserveG}, ${this.reserveB}, ${alpha * 0.4})`);
        grad.addColorStop(1, `rgba(${this.reserveR}, ${this.reserveG}, ${this.reserveB}, 0)`);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(z.x, z.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Transfer dual glow (coral red), rendered as a second layer
      if (transferNorm > 0.005) {
        const glowRadius = z.radius + transferNorm * 25;
        const alpha = transferNorm * 0.35 * pulseMult;

        const grad = ctx.createRadialGradient(z.x, z.y, 0, z.x, z.y, glowRadius);
        grad.addColorStop(0, `rgba(${this.transferR}, ${this.transferG}, ${this.transferB}, ${alpha})`);
        grad.addColorStop(0.5, `rgba(${this.transferR}, ${this.transferG}, ${this.transferB}, ${alpha * 0.35})`);
        grad.addColorStop(1, `rgba(${this.transferR}, ${this.transferG}, ${this.transferB}, 0)`);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(z.x, z.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();
      }

      // 5. Optional dual value labels
      if (this.showLabels) {
        const totalDual = z.reserveDual + z.transferDual;
        if (totalDual > 0.1) {
          const labelText = `\u03BC = ${z.reserveDual.toFixed(1)}`;
          const labelAlpha = Math.min(1, Math.max(reserveNorm, transferNorm) * 1.5) * pulseMult;

          ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillStyle = `rgba(${this.reserveR}, ${this.reserveG}, ${this.reserveB}, ${labelAlpha * 0.8})`;
          ctx.fillText(labelText, z.x, z.y + z.radius * 0.6 + 4);

          if (z.transferDual > 0.1) {
            const tLabel = `\u03BB = ${z.transferDual.toFixed(1)}`;
            ctx.fillStyle = `rgba(${this.transferR}, ${this.transferG}, ${this.transferB}, ${labelAlpha * 0.8})`;
            ctx.fillText(tLabel, z.x, z.y + z.radius * 0.6 + 16);
          }
        }
      }
    }

    ctx.restore();
  }
}
