// zoneMap.js — 10-Zone Schematic
// Stylized map of 10 zones in a balanced 2-row layout

const GRAPHITE = '#2D2D2D';
const TEAL = '#1A7A6D';
const EMBER_ORANGE = '#E8763A';
const CORAL_RED = '#D94F4F';
const WARM_NEUTRAL = '#8B7D6B';
const GOLD = '#D4A843';
const WIND_COLOR = '#4A9B8E';

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// Adjacency list for the 10-zone grid (1-indexed zone numbers, stored 0-indexed)
const ZONE_ADJACENCY = [
  [1, 4],    // Z1 connects to Z2, Z5
  [0, 2, 5], // Z2 connects to Z1, Z3, Z6
  [1, 3, 6], // Z3 connects to Z2, Z4, Z7
  [2, 7],    // Z4 connects to Z3, Z8
  [0, 5, 8], // Z5 connects to Z1, Z6, Z9
  [1, 4, 6, 9], // Z6 connects to Z2, Z5, Z7, Z10
  [2, 5, 7], // Z7 connects to Z3, Z6, Z8
  [3, 6],    // Z8 connects to Z4, Z7
  [4, 9],    // Z9 connects to Z5, Z10
  [5, 8],    // Z10 connects to Z6, Z9
];

export class ZoneMap {
  constructor(options = {}) {
    this.cx = options.cx || 400;
    this.cy = options.cy || 300;
    this.radius = options.radius || 200;

    // Zone data
    this.loads = new Float64Array(10);
    this.generation = new Float64Array(10);
    this.reserves = new Float64Array(10);
    this.duals = new Float64Array(10);
    this.transfers = new Float64Array(10);

    // Generator counts per zone
    this.genCounts = options.zoneData?.genCounts || [5, 6, 5, 5, 6, 7, 5, 5, 5, 5];

    // Visual state
    this.highlightedZone = -1;
    this.glows = []; // {index, intensity, color}
    for (let i = 0; i < 10; i++) {
      this.glows.push({ intensity: 0, targetIntensity: 0, color: EMBER_ORANGE });
    }

    // Coupled mode
    this.coupledMode = false;
    this.transferPressures = new Map(); // "i-j" -> value

    // Demand halo animation
    this.time = 0;

    // Compute zone positions: 2 rows of 5
    this.zonePositions = this._computeLayout();
    this.zoneSize = { w: 60, h: 50 };
  }

  _computeLayout() {
    const positions = [];
    const cols = 5;
    const rows = 2;
    const spacingX = this.radius * 2 / (cols - 1);
    const spacingY = this.radius * 0.9;
    const startX = this.cx - this.radius;
    const startY = this.cy - spacingY / 2;

    // Row 1: Z1-Z5, Row 2: Z6-Z10
    // But we use the adjacency-based layout:
    // Row 0: Z1, Z2, Z3, Z4 (4 zones)
    // Row 1: Z5, Z6, Z7, Z8 (4 zones)
    // Row 2: Z9, Z10 (2 zones)
    // Actually, let's do a clean 2-row layout: 5 top, 5 bottom
    for (let i = 0; i < 10; i++) {
      const row = Math.floor(i / cols);
      const col = i % cols;
      positions.push({
        x: startX + col * spacingX,
        y: startY + row * spacingY
      });
    }
    return positions;
  }

  setZoneData(data) {
    if (data.loads) {
      for (let i = 0; i < 10 && i < data.loads.length; i++) {
        this.loads[i] = data.loads[i];
      }
    }
    if (data.generation) {
      for (let i = 0; i < 10 && i < data.generation.length; i++) {
        this.generation[i] = data.generation[i];
      }
    }
    if (data.reserves) {
      for (let i = 0; i < 10 && i < data.reserves.length; i++) {
        this.reserves[i] = data.reserves[i];
      }
    }
    if (data.duals) {
      for (let i = 0; i < 10 && i < data.duals.length; i++) {
        this.duals[i] = data.duals[i];
        this.glows[i].targetIntensity = data.duals[i];
      }
    }
    if (data.transfers) {
      for (let i = 0; i < 10 && i < data.transfers.length; i++) {
        this.transfers[i] = data.transfers[i];
      }
    }
  }

  highlightZone(index) {
    this.highlightedZone = index;
  }

  setGlow(zoneIndex, intensity, color) {
    if (zoneIndex >= 0 && zoneIndex < 10) {
      this.glows[zoneIndex].targetIntensity = intensity;
      this.glows[zoneIndex].color = color || EMBER_ORANGE;
    }
  }

  setCoupledMode(enabled) {
    this.coupledMode = enabled;
  }

  setTransferPressure(zonePairs, values) {
    this.transferPressures.clear();
    for (let i = 0; i < zonePairs.length; i++) {
      const key = `${zonePairs[i][0]}-${zonePairs[i][1]}`;
      this.transferPressures.set(key, values[i]);
    }
  }

  getZonePosition(index) {
    if (index < 0 || index >= 10) return { x: this.cx, y: this.cy };
    return { ...this.zonePositions[index] };
  }

  getZoneRect(index) {
    const pos = this.getZonePosition(index);
    return {
      x: pos.x - this.zoneSize.w / 2,
      y: pos.y - this.zoneSize.h / 2,
      w: this.zoneSize.w,
      h: this.zoneSize.h
    };
  }

  update(dt) {
    this.time += dt;

    // Animate glows toward targets
    for (let i = 0; i < 10; i++) {
      const diff = this.glows[i].targetIntensity - this.glows[i].intensity;
      this.glows[i].intensity += diff * Math.min(1, dt * 4);
    }
  }

  render(ctx) {
    // Find max load for normalization
    let maxLoad = 0;
    for (let i = 0; i < 10; i++) {
      if (this.loads[i] > maxLoad) maxLoad = this.loads[i];
    }
    if (maxLoad === 0) maxLoad = 1;

    // Find max dual for glow normalization
    let maxDual = 0;
    for (let i = 0; i < 10; i++) {
      if (this.glows[i].intensity > maxDual) maxDual = this.glows[i].intensity;
    }
    if (maxDual === 0) maxDual = 1;

    let maxTransferByZone = 0;
    for (let i = 0; i < 10; i++) {
      if (this.transfers[i] > maxTransferByZone) maxTransferByZone = this.transfers[i];
    }
    if (maxTransferByZone === 0) maxTransferByZone = 1;

    // 4. Connections between adjacent zones (draw first, behind zones)
    this._renderConnections(ctx);

    // 6. Transfer walls in coupled mode
    if (this.coupledMode) {
      this._renderTransferWalls(ctx);
    }

    // Draw zones
    for (let i = 0; i < 10; i++) {
      this._renderZone(ctx, i, maxLoad, maxDual, maxTransferByZone);
    }
  }

  _renderConnections(ctx) {
    ctx.save();
    const drawn = new Set();

    for (let i = 0; i < 10; i++) {
      const neighbors = ZONE_ADJACENCY[i];
      for (let k = 0; k < neighbors.length; k++) {
        const j = neighbors[k];
        const key = Math.min(i, j) + '-' + Math.max(i, j);
        if (drawn.has(key)) continue;
        drawn.add(key);

        const p1 = this.zonePositions[i];
        const p2 = this.zonePositions[j];

        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = `rgba(45, 45, 45, 0.12)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  _renderTransferWalls(ctx) {
    ctx.save();
    // Find max transfer for normalization
    let maxTransfer = 0;
    for (const val of this.transferPressures.values()) {
      if (Math.abs(val) > maxTransfer) maxTransfer = Math.abs(val);
    }
    if (maxTransfer === 0) maxTransfer = 1;

    for (const [key, value] of this.transferPressures) {
      const parts = key.split('-');
      const i = parseInt(parts[0]);
      const j = parseInt(parts[1]);
      const p1 = this.zonePositions[i];
      const p2 = this.zonePositions[j];

      const intensity = Math.abs(value) / maxTransfer;
      const lineWidth = 2 + intensity * 4;

      // Color: blend from teal (low) to coral (high)
      const r = Math.round(lerp(26, 217, intensity));
      const g = Math.round(lerp(122, 79, intensity));
      const b = Math.round(lerp(109, 79, intensity));

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.4 + intensity * 0.4})`;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
    ctx.restore();
  }

  _renderZone(ctx, index, maxLoad, maxDual, maxTransferByZone) {
    const pos = this.zonePositions[index];
    const w = this.zoneSize.w;
    const h = this.zoneSize.h;
    const x = pos.x - w / 2;
    const y = pos.y - h / 2;
    const isHighlighted = (index === this.highlightedZone);
    const loadNorm = maxLoad > 0 ? this.loads[index] / maxLoad : 0;
    const glowInfo = this.glows[index];
    const glowNorm = maxDual > 0 ? glowInfo.intensity / maxDual : 0;
    const transferNorm = this.coupledMode && maxTransferByZone > 0 ? this.transfers[index] / maxTransferByZone : 0;
    const cornerRadius = 8;

    ctx.save();

    // 7. Demand halo: soft warm glow sized by load
    if (loadNorm > 0.01) {
      const haloRadius = w * 0.5 + loadNorm * 20;
      const haloAlpha = loadNorm * 0.12;
      const gradient = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, haloRadius);
      gradient.addColorStop(0, `rgba(139, 125, 107, ${haloAlpha})`);
      gradient.addColorStop(1, 'rgba(139, 125, 107, 0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, haloRadius, 0, Math.PI * 2);
      ctx.fill();
    }

    // 5. Shadow price glow
    if (glowNorm > 0.01) {
      const glowRadius = w * 0.7 + glowNorm * 25;
      const pulsePhase = Math.sin(this.time * 2.1 + index * 0.7) * 0.15 + 0.85;
      const glowAlpha = glowNorm * 0.35 * pulsePhase;

      // Parse glow color
      const gc = glowInfo.color;
      const gr = parseInt(gc.slice(1, 3), 16);
      const gg = parseInt(gc.slice(3, 5), 16);
      const gb = parseInt(gc.slice(5, 7), 16);

      const gradient = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowRadius);
      gradient.addColorStop(0, `rgba(${gr}, ${gg}, ${gb}, ${glowAlpha})`);
      gradient.addColorStop(0.6, `rgba(${gr}, ${gg}, ${gb}, ${glowAlpha * 0.3})`);
      gradient.addColorStop(1, `rgba(${gr}, ${gg}, ${gb}, 0)`);
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2);
      ctx.fill();
    }

    // 1. Zone shape: rounded rectangle
    const fillBrightness = 245 - Math.round(loadNorm * 25);
    ctx.fillStyle = `rgb(${fillBrightness}, ${fillBrightness - 3}, ${fillBrightness - 8})`;
    this._roundedRect(ctx, x, y, w, h, cornerRadius);
    ctx.fill();

    if (this.coupledMode && transferNorm > 0.01) {
      const capWidth = w * (0.38 + transferNorm * 0.42);
      const capHeight = 6 + transferNorm * 5;
      const capX = pos.x - capWidth / 2;
      const capY = y - 7 - capHeight;
      ctx.fillStyle = `rgba(217, 79, 79, ${0.28 + transferNorm * 0.42})`;
      this._roundedRect(ctx, capX, capY, capWidth, capHeight, capHeight / 2);
      ctx.fill();

      ctx.strokeStyle = `rgba(217, 79, 79, ${0.24 + transferNorm * 0.34})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(pos.x, capY + capHeight);
      ctx.lineTo(pos.x, y - 2);
      ctx.stroke();
    }

    // Border
    if (isHighlighted) {
      ctx.strokeStyle = TEAL;
      ctx.lineWidth = 2.5;
      ctx.shadowColor = `rgba(26, 122, 109, 0.4)`;
      ctx.shadowBlur = 8;
    } else {
      ctx.strokeStyle = `rgba(45, 45, 45, 0.25)`;
      ctx.lineWidth = 1;
      ctx.shadowBlur = 0;
    }
    this._roundedRect(ctx, x, y, w, h, cornerRadius);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // 2. Zone label
    ctx.fillStyle = GRAPHITE;
    ctx.font = `bold 13px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(`Z${index + 1}`, pos.x, y + 5);

    if (this.coupledMode && transferNorm > 0.01) {
      ctx.fillStyle = CORAL_RED;
      ctx.font = `600 10px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.textBaseline = 'bottom';
      ctx.fillText(`lam ${this.transfers[index].toFixed(1)}`, pos.x, y - 8);
    }

    // 3. Generator dots inside zone
    const genCount = this.genCounts[index];
    const dotRadius = 2;
    const dotsPerRow = Math.min(genCount, 5);
    const dotRows = Math.ceil(genCount / dotsPerRow);
    const dotSpacing = 8;
    const dotsStartX = pos.x - (Math.min(genCount, dotsPerRow) - 1) * dotSpacing / 2;
    const dotsStartY = pos.y + 4;

    ctx.fillStyle = `rgba(26, 122, 109, 0.5)`;
    let dotIndex = 0;
    for (let row = 0; row < dotRows && dotIndex < genCount; row++) {
      const dotsInThisRow = Math.min(dotsPerRow, genCount - dotIndex);
      const rowStartX = pos.x - (dotsInThisRow - 1) * dotSpacing / 2;
      for (let col = 0; col < dotsInThisRow; col++) {
        ctx.beginPath();
        ctx.arc(rowStartX + col * dotSpacing, dotsStartY + row * dotSpacing, dotRadius, 0, Math.PI * 2);
        ctx.fill();
        dotIndex++;
      }
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
