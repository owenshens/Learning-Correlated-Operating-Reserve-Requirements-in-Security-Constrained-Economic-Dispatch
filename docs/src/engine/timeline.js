// === Easing Functions ===

export function linear(t) { return t; }
export function easeInQuad(t) { return t * t; }
export function easeOutQuad(t) { return t * (2 - t); }
export function easeInOutQuad(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }
export function easeInCubic(t) { return t * t * t; }
export function easeOutCubic(t) { const t1 = t - 1; return t1 * t1 * t1 + 1; }
export function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}
export function easeOutBack(t) {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}
export function easeOutElastic(t) {
  if (t === 0 || t === 1) return t;
  return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI / 3)) + 1;
}

// === Tween ===

export class Tween {
  constructor(target, props, duration, easing = easeOutCubic) {
    this.target = target;
    this.props = props;
    this.duration = duration / 1000; // convert ms to seconds
    this.easing = easing;
    this.elapsed = 0;
    this.started = false;
    this.complete = false;
    this.startValues = {};
    this._onComplete = null;
  }

  start() {
    this.started = true;
    this.elapsed = 0;
    this.complete = false;
    for (const key in this.props) {
      this.startValues[key] = this.target[key] ?? 0;
    }
    return this;
  }

  onComplete(cb) {
    this._onComplete = cb;
    return this;
  }

  update(dt) {
    if (!this.started || this.complete) return;
    this.elapsed += dt;
    const rawT = Math.min(this.elapsed / this.duration, 1);
    const t = this.easing(rawT);

    for (const key in this.props) {
      const start = this.startValues[key];
      const end = this.props[key];
      if (typeof end === 'number') {
        this.target[key] = start + (end - start) * t;
      }
    }

    if (rawT >= 1) {
      this.complete = true;
      if (this._onComplete) this._onComplete();
    }
  }

  isComplete() {
    return this.complete;
  }
}

// === Timeline ===

export class Timeline {
  constructor() {
    this.entries = []; // { tween, offset }
    this.elapsed = 0;
    this.playing = false;
    this._duration = 0;
    this._onComplete = null;
  }

  add(tween, offset = 0) {
    const offsetSec = offset / 1000;
    this.entries.push({ tween, offset: offsetSec });
    const end = offsetSec + tween.duration;
    if (end > this._duration) this._duration = end;
    return this;
  }

  onComplete(cb) {
    this._onComplete = cb;
    return this;
  }

  play() {
    this.playing = true;
    this.elapsed = 0;
    for (const entry of this.entries) {
      entry.tween.started = false;
      entry.tween.complete = false;
    }
    return this;
  }

  pause() {
    this.playing = false;
    return this;
  }

  seek(time) {
    this.elapsed = time / 1000;
    return this;
  }

  getDuration() {
    return this._duration * 1000;
  }

  update(dt) {
    if (!this.playing) return;
    this.elapsed += dt;

    let allComplete = true;
    for (const entry of this.entries) {
      if (this.elapsed >= entry.offset && !entry.tween.started) {
        entry.tween.start();
      }
      if (entry.tween.started) {
        entry.tween.update(dt);
      }
      if (!entry.tween.isComplete()) {
        allComplete = false;
      }
    }

    if (allComplete && this.entries.length > 0) {
      this.playing = false;
      if (this._onComplete) this._onComplete();
    }
  }

  isComplete() {
    return this.entries.every(e => e.tween.isComplete());
  }
}

// === Utility: animate a value smoothly ===

export class AnimatedValue {
  constructor(initial = 0) {
    this.current = initial;
    this.target = initial;
    this.velocity = 0;
    this.smoothing = 8; // higher = faster response
  }

  set(target) {
    this.target = target;
  }

  snap(value) {
    this.current = value;
    this.target = value;
    this.velocity = 0;
  }

  update(dt) {
    const diff = this.target - this.current;
    this.current += diff * Math.min(this.smoothing * dt, 1);
  }

  get() {
    return this.current;
  }
}
