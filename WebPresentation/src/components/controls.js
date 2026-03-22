// controls.js — UI Controls Manager
// Creates and manages DOM-based interactive controls

const TEAL = '#1A7A6D';
const EMBER_ORANGE = '#E8763A';
const GRAPHITE = '#2D2D2D';
const IVORY = '#FAF6F0';

export class Controls {
  constructor(options = {}) {
    this.container = options.container || null;

    // State
    this._method = 'box';
    this._coupled = false;
    this._context = { load: 0.5, solar: 0.5, wind: 0.5, timeOfDay: 12, month: 6 };
    this._selectedZone = null;
    this._currentScene = 0;
    this._sceneCount = 1;
    this._playing = true;

    // Callbacks
    this._onMethodChange = null;
    this._onCoupledToggle = null;
    this._onContextChange = null;
    this._onZoneSelect = null;
    this._onPlayPause = null;
    this._onSceneChange = null;

    // DOM references
    this._els = {};
    this._sandboxVisible = false;
  }

  init() {
    if (!this.container) return;

    // Build control panel DOM
    const panel = document.createElement('div');
    panel.style.cssText = `
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: ${GRAPHITE};
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      background: rgba(250, 246, 240, 0.95);
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      max-width: 280px;
      font-size: 13px;
      user-select: none;
    `;
    this._els.panel = panel;

    // Scene navigation
    this._buildSceneNav(panel);

    // Play/pause
    this._buildPlayPause(panel);

    // Method selector
    this._buildMethodSelector(panel);

    // Coupled toggle
    this._buildCoupledToggle(panel);

    // Zone selector
    this._buildZoneSelector(panel);

    // Sandbox controls (hidden by default)
    this._buildSandboxControls(panel);

    this.container.appendChild(panel);
  }

  _buildSceneNav(parent) {
    const row = this._makeRow(parent, 'Scene');

    const prevBtn = document.createElement('button');
    prevBtn.textContent = '\u25C0';
    this._styleButton(prevBtn);
    prevBtn.addEventListener('click', () => {
      if (this._currentScene > 0) {
        this._currentScene--;
        this._updateSceneLabel();
        if (this._onSceneChange) this._onSceneChange(this._currentScene);
      }
    });

    const label = document.createElement('span');
    label.textContent = '1 / 1';
    label.style.cssText = 'min-width: 50px; text-align: center; font-variant-numeric: tabular-nums;';
    this._els.sceneLabel = label;

    const nextBtn = document.createElement('button');
    nextBtn.textContent = '\u25B6';
    this._styleButton(nextBtn);
    nextBtn.addEventListener('click', () => {
      if (this._currentScene < this._sceneCount - 1) {
        this._currentScene++;
        this._updateSceneLabel();
        if (this._onSceneChange) this._onSceneChange(this._currentScene);
      }
    });

    const controls = document.createElement('div');
    controls.style.cssText = 'display: flex; align-items: center; gap: 8px;';
    controls.appendChild(prevBtn);
    controls.appendChild(label);
    controls.appendChild(nextBtn);
    row.appendChild(controls);
  }

  _buildPlayPause(parent) {
    const row = this._makeRow(parent, '');

    const btn = document.createElement('button');
    btn.textContent = 'Pause';
    btn.style.cssText = `
      padding: 4px 16px;
      border: 1px solid ${TEAL};
      border-radius: 4px;
      background: white;
      color: ${TEAL};
      cursor: pointer;
      font-size: 12px;
      font-family: inherit;
      transition: background 0.15s, color 0.15s;
    `;
    btn.addEventListener('mouseenter', () => {
      btn.style.background = TEAL;
      btn.style.color = 'white';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.background = 'white';
      btn.style.color = TEAL;
    });
    btn.addEventListener('click', () => {
      this._playing = !this._playing;
      btn.textContent = this._playing ? 'Pause' : 'Play';
      if (this._onPlayPause) this._onPlayPause(this._playing);
    });
    this._els.playBtn = btn;
    row.appendChild(btn);
  }

  _buildMethodSelector(parent) {
    const section = document.createElement('div');
    section.style.cssText = 'display: flex; flex-direction: column; gap: 4px;';

    const label = document.createElement('div');
    label.textContent = 'Method';
    label.style.cssText = 'font-size: 11px; color: rgba(45,45,45,0.6); text-transform: uppercase; letter-spacing: 0.5px;';
    section.appendChild(label);

    const methods = [
      { value: 'box', label: 'Box' },
      { value: 'samplecov', label: 'Sample Cov' },
      { value: 'staticl', label: 'Static L' },
      { value: 'contextual', label: 'Contextual' }
    ];

    const btnGroup = document.createElement('div');
    btnGroup.style.cssText = 'display: flex; gap: 2px; border-radius: 6px; overflow: hidden; border: 1px solid rgba(45,45,45,0.15);';

    this._els.methodBtns = [];

    for (const m of methods) {
      const btn = document.createElement('button');
      btn.textContent = m.label;
      btn.dataset.value = m.value;
      btn.style.cssText = `
        flex: 1;
        padding: 5px 4px;
        border: none;
        background: ${m.value === this._method ? TEAL : 'white'};
        color: ${m.value === this._method ? 'white' : GRAPHITE};
        cursor: pointer;
        font-size: 11px;
        font-family: inherit;
        transition: background 0.15s, color 0.15s;
      `;

      btn.addEventListener('click', () => {
        this._method = m.value;
        this._updateMethodButtons();
        if (this._onMethodChange) this._onMethodChange(m.value);
      });

      this._els.methodBtns.push(btn);
      btnGroup.appendChild(btn);
    }

    section.appendChild(btnGroup);
    parent.appendChild(section);
  }

  _buildCoupledToggle(parent) {
    const row = this._makeRow(parent, 'Coupled Reserves');

    const toggle = document.createElement('div');
    toggle.style.cssText = `
      width: 36px; height: 20px;
      border-radius: 10px;
      background: rgba(45,45,45,0.15);
      cursor: pointer;
      position: relative;
      transition: background 0.2s;
    `;

    const knob = document.createElement('div');
    knob.style.cssText = `
      width: 16px; height: 16px;
      border-radius: 8px;
      background: white;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
      position: absolute;
      top: 2px; left: 2px;
      transition: left 0.2s;
    `;
    toggle.appendChild(knob);

    toggle.addEventListener('click', () => {
      this._coupled = !this._coupled;
      toggle.style.background = this._coupled ? TEAL : 'rgba(45,45,45,0.15)';
      knob.style.left = this._coupled ? '18px' : '2px';
      if (this._onCoupledToggle) this._onCoupledToggle(this._coupled);
    });

    this._els.coupledToggle = toggle;
    this._els.coupledKnob = knob;
    row.appendChild(toggle);
  }

  _buildZoneSelector(parent) {
    const section = document.createElement('div');
    section.style.cssText = 'display: flex; flex-direction: column; gap: 4px;';

    const label = document.createElement('div');
    label.textContent = 'Focus Zone';
    label.style.cssText = 'font-size: 11px; color: rgba(45,45,45,0.6); text-transform: uppercase; letter-spacing: 0.5px;';
    section.appendChild(label);

    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; grid-template-columns: repeat(5, 1fr); gap: 3px;';

    this._els.zoneBtns = [];

    for (let i = 0; i < 10; i++) {
      const btn = document.createElement('button');
      btn.textContent = `Z${i + 1}`;
      btn.dataset.zone = i;
      btn.style.cssText = `
        padding: 4px 0;
        border: 1px solid rgba(45,45,45,0.15);
        border-radius: 4px;
        background: white;
        color: ${GRAPHITE};
        cursor: pointer;
        font-size: 11px;
        font-family: inherit;
        transition: background 0.15s, color 0.15s, border-color 0.15s;
      `;

      btn.addEventListener('click', () => {
        const zone = parseInt(btn.dataset.zone);
        if (this._selectedZone === zone) {
          this._selectedZone = null;
        } else {
          this._selectedZone = zone;
        }
        this._updateZoneButtons();
        if (this._onZoneSelect) this._onZoneSelect(this._selectedZone);
      });

      this._els.zoneBtns.push(btn);
      grid.appendChild(btn);
    }

    section.appendChild(grid);
    parent.appendChild(section);
  }

  _buildSandboxControls(parent) {
    const section = document.createElement('div');
    section.style.cssText = 'display: none; flex-direction: column; gap: 8px;';
    this._els.sandboxSection = section;

    const sliders = [
      { key: 'load', label: 'Load', min: 0, max: 1, step: 0.01 },
      { key: 'solar', label: 'Solar', min: 0, max: 1, step: 0.01 },
      { key: 'wind', label: 'Wind', min: 0, max: 1, step: 0.01 },
      { key: 'timeOfDay', label: 'Hour', min: 0, max: 23, step: 1 },
      { key: 'month', label: 'Month', min: 1, max: 12, step: 1 }
    ];

    this._els.sliders = {};

    for (const s of sliders) {
      const row = document.createElement('div');
      row.style.cssText = 'display: flex; align-items: center; gap: 8px;';

      const lbl = document.createElement('span');
      lbl.textContent = s.label;
      lbl.style.cssText = 'font-size: 11px; min-width: 40px; color: rgba(45,45,45,0.7);';

      const input = document.createElement('input');
      input.type = 'range';
      input.min = s.min;
      input.max = s.max;
      input.step = s.step;
      input.value = this._context[s.key];
      input.style.cssText = `flex: 1; accent-color: ${TEAL};`;

      const valLabel = document.createElement('span');
      valLabel.textContent = this._context[s.key];
      valLabel.style.cssText = 'font-size: 11px; min-width: 30px; text-align: right; font-variant-numeric: tabular-nums;';

      input.addEventListener('input', () => {
        const val = parseFloat(input.value);
        this._context[s.key] = val;
        valLabel.textContent = Number.isInteger(val) ? val : val.toFixed(2);
        if (this._onContextChange) this._onContextChange({ ...this._context });
      });

      this._els.sliders[s.key] = { input, valLabel };
      row.appendChild(lbl);
      row.appendChild(input);
      row.appendChild(valLabel);
      section.appendChild(row);
    }

    parent.appendChild(section);
  }

  // Helper: make a labeled row
  _makeRow(parent, labelText) {
    const row = document.createElement('div');
    row.style.cssText = 'display: flex; align-items: center; justify-content: space-between;';
    if (labelText) {
      const label = document.createElement('span');
      label.textContent = labelText;
      label.style.cssText = 'font-size: 12px; color: rgba(45,45,45,0.7);';
      row.appendChild(label);
    }
    parent.appendChild(row);
    return row;
  }

  _styleButton(btn) {
    btn.style.cssText = `
      width: 28px; height: 28px;
      border: 1px solid rgba(45,45,45,0.15);
      border-radius: 4px;
      background: white;
      color: ${GRAPHITE};
      cursor: pointer;
      font-size: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
    `;
    btn.addEventListener('mouseenter', () => { btn.style.background = '#f0f0f0'; });
    btn.addEventListener('mouseleave', () => { btn.style.background = 'white'; });
  }

  _updateMethodButtons() {
    for (const btn of this._els.methodBtns) {
      const active = btn.dataset.value === this._method;
      btn.style.background = active ? TEAL : 'white';
      btn.style.color = active ? 'white' : GRAPHITE;
    }
  }

  _updateZoneButtons() {
    for (const btn of this._els.zoneBtns) {
      const zone = parseInt(btn.dataset.zone);
      const active = zone === this._selectedZone;
      btn.style.background = active ? TEAL : 'white';
      btn.style.color = active ? 'white' : GRAPHITE;
      btn.style.borderColor = active ? TEAL : 'rgba(45,45,45,0.15)';
    }
  }

  _updateSceneLabel() {
    if (this._els.sceneLabel) {
      this._els.sceneLabel.textContent = `${this._currentScene + 1} / ${this._sceneCount}`;
    }
  }

  // Public getters
  getMethod() {
    return this._method;
  }

  isCoupled() {
    return this._coupled;
  }

  getContext() {
    return { ...this._context };
  }

  getSelectedZone() {
    return this._selectedZone;
  }

  // Callback setters
  onMethodChange(cb) { this._onMethodChange = cb; }
  onCoupledToggle(cb) { this._onCoupledToggle = cb; }
  onContextChange(cb) { this._onContextChange = cb; }
  onZoneSelect(cb) { this._onZoneSelect = cb; }
  onPlayPause(cb) { this._onPlayPause = cb; }
  onSceneChange(cb) { this._onSceneChange = cb; }

  // Scene management
  setSceneCount(n) {
    this._sceneCount = n;
    this._updateSceneLabel();
  }

  setCurrentScene(index) {
    this._currentScene = index;
    this._updateSceneLabel();
  }

  // Sandbox controls visibility
  showSandboxControls() {
    if (this._els.sandboxSection) {
      this._els.sandboxSection.style.display = 'flex';
      this._sandboxVisible = true;
    }
  }

  hideSandboxControls() {
    if (this._els.sandboxSection) {
      this._els.sandboxSection.style.display = 'none';
      this._sandboxVisible = false;
    }
  }

  // Update from external state
  update(state) {
    if (state && state.method !== undefined && state.method !== this._method) {
      this._method = state.method;
      this._updateMethodButtons();
    }
    if (state && state.coupled !== undefined && state.coupled !== this._coupled) {
      this._coupled = state.coupled;
      if (this._els.coupledToggle) {
        this._els.coupledToggle.style.background = this._coupled ? TEAL : 'rgba(45,45,45,0.15)';
        this._els.coupledKnob.style.left = this._coupled ? '18px' : '2px';
      }
    }
    if (state && state.selectedZone !== undefined) {
      this._selectedZone = state.selectedZone;
      this._updateZoneButtons();
    }
  }
}
