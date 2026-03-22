// === Renderer ===
// Sets up 2D canvas, handles DPI, provides drawing utilities, runs animation loop.

const COLORS = {
  bg: '#FAF6F0',
  ink: '#2D2D2D',
  inkLight: '#6B6B6B',
  teal: '#1A7A6D',
  tealLight: '#2AA89A',
  ember: '#E8763A',
  coral: '#D94F4F',
  cobalt: '#5B7FA5',
  load: '#8B7D6B',
  solar: '#D4A843',
  wind: '#4A9B8E',
};

export { COLORS };

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.dpr = window.devicePixelRatio || 1;
    this.width = 0;
    this.height = 0;
    this.camera = { x: 0, y: 0, scale: 1, targetX: 0, targetY: 0, targetScale: 1 };
    this._lastTime = 0;
    this._running = false;
    this._updateFn = null;
    this._renderFn = null;

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    this.dpr = window.devicePixelRatio || 1;
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width * this.dpr;
    this.canvas.height = this.height * this.dpr;
    this.canvas.style.width = this.width + 'px';
    this.canvas.style.height = this.height + 'px';
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  setCallbacks(updateFn, renderFn) {
    this._updateFn = updateFn;
    this._renderFn = renderFn;
  }

  start() {
    this._running = true;
    this._lastTime = performance.now();
    this._loop(this._lastTime);
  }

  stop() {
    this._running = false;
  }

  _loop(now) {
    if (!this._running) return;
    const dt = Math.min((now - this._lastTime) / 1000, 0.05); // cap at 50ms
    this._lastTime = now;

    // Update camera lerp
    const cam = this.camera;
    cam.x += (cam.targetX - cam.x) * Math.min(4 * dt, 1);
    cam.y += (cam.targetY - cam.y) * Math.min(4 * dt, 1);
    cam.scale += (cam.targetScale - cam.scale) * Math.min(4 * dt, 1);

    if (this._updateFn) this._updateFn(dt);

    // Clear
    this.ctx.save();
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.ctx.fillStyle = COLORS.bg;
    this.ctx.fillRect(0, 0, this.width, this.height);

    // Apply camera
    this.ctx.translate(this.width / 2, this.height / 2);
    this.ctx.scale(cam.scale, cam.scale);
    this.ctx.translate(-this.width / 2 + cam.x, -this.height / 2 + cam.y);

    if (this._renderFn) this._renderFn(this.ctx, this.width, this.height);
    this.ctx.restore();

    requestAnimationFrame((t) => this._loop(t));
  }

  // === Drawing Utilities ===

  static drawEllipse(ctx, cx, cy, L, scale = 1, style = {}) {
    const {
      fillColor = null,
      strokeColor = COLORS.teal,
      lineWidth = 2,
      alpha = 1,
      dash = null,
    } = style;

    const numPoints = 64;
    const points = [];
    for (let i = 0; i <= numPoints; i++) {
      const t = (i / numPoints) * Math.PI * 2;
      const cosT = Math.cos(t);
      const sinT = Math.sin(t);
      // point = L * [cos(t), sin(t)] * scale
      const x = (L[0][0] * cosT + L[0][1] * sinT) * scale + cx;
      const y = (L[1][0] * cosT + L[1][1] * sinT) * scale + cy;
      points.push({ x, y });
    }

    ctx.save();
    ctx.globalAlpha = alpha;
    if (dash) ctx.setLineDash(dash);

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.closePath();

    if (fillColor) {
      ctx.fillStyle = fillColor;
      ctx.fill();
    }
    if (strokeColor) {
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }

    ctx.restore();
  }

  static drawArrow(ctx, x1, y1, x2, y2, style = {}) {
    const {
      color = COLORS.ink,
      lineWidth = 1.5,
      headSize = 8,
      alpha = 1,
      dash = null,
    } = style;

    const angle = Math.atan2(y2 - y1, x2 - x1);

    ctx.save();
    ctx.globalAlpha = alpha;
    if (dash) ctx.setLineDash(dash);
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = lineWidth;

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    // Arrowhead
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(
      x2 - headSize * Math.cos(angle - Math.PI / 6),
      y2 - headSize * Math.sin(angle - Math.PI / 6)
    );
    ctx.lineTo(
      x2 - headSize * Math.cos(angle + Math.PI / 6),
      y2 - headSize * Math.sin(angle + Math.PI / 6)
    );
    ctx.closePath();
    ctx.fill();

    ctx.restore();
  }

  static drawBar(ctx, x, y, width, height, style = {}) {
    const {
      color = COLORS.ember,
      alpha = 1,
      radius = 3,
      glowColor = null,
      glowIntensity = 0,
    } = style;

    ctx.save();
    ctx.globalAlpha = alpha;

    if (glowColor && glowIntensity > 0) {
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = 12 * glowIntensity;
    }

    // Rounded top bar
    const r = Math.min(radius, width / 2, Math.abs(height));
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x, y - height + r);
    ctx.quadraticCurveTo(x, y - height, x + r, y - height);
    ctx.lineTo(x + width - r, y - height);
    ctx.quadraticCurveTo(x + width, y - height, x + width, y - height + r);
    ctx.lineTo(x + width, y);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();

    ctx.shadowBlur = 0;
    ctx.restore();
  }

  static drawGlow(ctx, x, y, radius, color = COLORS.ember, intensity = 1) {
    ctx.save();
    ctx.globalAlpha = intensity * 0.6;
    const grad = ctx.createRadialGradient(x, y, 0, x, y, radius);
    grad.addColorStop(0, color);
    grad.addColorStop(1, 'transparent');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  static drawParticle(ctx, x, y, radius = 3, color = COLORS.teal, alpha = 1) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  static drawText(ctx, text, x, y, style = {}) {
    const {
      font = '14px "Manrope", sans-serif',
      color = COLORS.ink,
      align = 'left',
      baseline = 'middle',
      alpha = 1,
    } = style;

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.font = font;
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.textBaseline = baseline;
    ctx.fillText(text, x, y);
    ctx.restore();
  }

  static drawLine(ctx, x1, y1, x2, y2, style = {}) {
    const { color = COLORS.ink, lineWidth = 1, alpha = 1, dash = null } = style;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    if (dash) ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.restore();
  }
}
