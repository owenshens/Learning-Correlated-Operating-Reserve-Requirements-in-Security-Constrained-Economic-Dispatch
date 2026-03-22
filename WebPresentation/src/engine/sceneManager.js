// === Scene Manager ===
// Manages 8 consolidated scenes for a 10-minute presentation.

const SCENE_TITLES = [
  'The Grid & Its Uncertainty',
  'Uncertainty Has Shape',
  'From Shape to Reserves',
  'The Cost of Protection',
  'The Gradient Flows Backward',
  'Learning Reshapes Uncertainty',
  'Methods Compared',
  'Interactive Sandbox',
];

const DEFAULT_SCENE_DURATION = 8; // seconds

export class SceneManager {
  constructor() {
    this.scenes = [];
    this.currentIndex = 0;
    this.previousIndex = -1;
    this.transitioning = false;
    this.transitionAlpha = 1; // 1 = fully showing current scene
    this.transitionDuration = 0.6;
    this.transitionElapsed = 0;

    this.playing = false;
    this.sceneElapsed = 0;
    this.sceneDurations = new Array(8).fill(DEFAULT_SCENE_DURATION);

    // Customize durations for consolidated scenes
    this.sceneDurations[0] = 10;  // Grid + Uncertainty (composite, internal split)
    this.sceneDurations[1] = 8;   // Uncertainty shape with dots
    this.sceneDurations[2] = 10;  // Exposure + Reserves (composite)
    this.sceneDurations[3] = 10;  // Dispatch + Shadow (composite)
    this.sceneDurations[4] = 12;  // Gradient backward — signature, longer
    this.sceneDurations[5] = 10;  // Learning iterations
    this.sceneDurations[6] = 10;  // Method comparison
    this.sceneDurations[7] = 60;  // Sandbox — stay until manually advanced

    this.listeners = {};
  }

  addScene(scene) {
    this.scenes.push(scene);
  }

  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
  }

  _emit(event, data) {
    if (this.listeners[event]) {
      for (const cb of this.listeners[event]) cb(data);
    }
  }

  getSceneCount() {
    return this.scenes.length;
  }

  getCurrentIndex() {
    return this.currentIndex;
  }

  getTitle(index) {
    return SCENE_TITLES[index] || `Scene ${index + 1}`;
  }

  getCurrentTitle() {
    return this.getTitle(this.currentIndex);
  }

  goToScene(index, state) {
    if (index < 0 || index >= this.scenes.length) return;
    if (index === this.currentIndex && !this.transitioning) return;

    this.previousIndex = this.currentIndex;
    this.currentIndex = index;
    this.transitioning = true;
    this.transitionElapsed = 0;
    this.sceneElapsed = 0;

    // Exit previous scene
    const prevScene = this.scenes[this.previousIndex];
    if (prevScene && prevScene.exit) {
      prevScene.exit(state);
    }
    this._emit('scene-exit', { index: this.previousIndex });

    // Enter new scene
    const newScene = this.scenes[this.currentIndex];
    if (newScene && newScene.enter) {
      newScene.enter(state);
    }
    this._emit('scene-enter', { index: this.currentIndex, title: this.getCurrentTitle() });
  }

  nextScene(state) {
    if (this.currentIndex < this.scenes.length - 1) {
      this.goToScene(this.currentIndex + 1, state);
    }
  }

  prevScene(state) {
    if (this.currentIndex > 0) {
      this.goToScene(this.currentIndex - 1, state);
    }
  }

  play() {
    this.playing = true;
  }

  pause() {
    this.playing = false;
  }

  isPlaying() {
    return this.playing;
  }

  update(dt, state) {
    // Handle transition
    if (this.transitioning) {
      this.transitionElapsed += dt;
      const t = Math.min(this.transitionElapsed / this.transitionDuration, 1);
      this.transitionAlpha = t;
      if (t >= 1) {
        this.transitioning = false;
        this.transitionAlpha = 1;
        this._emit('scene-transition', { index: this.currentIndex });
      }
    }

    // Update current scene
    const scene = this.scenes[this.currentIndex];
    if (scene && scene.update) {
      scene.update(dt, state);
    }

    // Guided mode auto-advance
    if (this.playing && !this.transitioning && state.mode === 'guided') {
      this.sceneElapsed += dt;
      const dur = this.sceneDurations[this.currentIndex] || DEFAULT_SCENE_DURATION;
      if (this.sceneElapsed >= dur) {
        this.nextScene(state);
      }
    }
  }

  render(ctx, state, width, height) {
    const scene = this.scenes[this.currentIndex];

    // During transition, fade in
    if (this.transitioning && this.previousIndex >= 0) {
      const prevScene = this.scenes[this.previousIndex];
      if (prevScene && prevScene.render) {
        ctx.save();
        ctx.globalAlpha = 1 - this.transitionAlpha;
        prevScene.render(ctx, state, width, height);
        ctx.restore();
      }
    }

    if (scene && scene.render) {
      ctx.save();
      ctx.globalAlpha = this.transitioning ? this.transitionAlpha : 1;
      scene.render(ctx, state, width, height);
      ctx.restore();
    }
  }

  onInteraction(event, state) {
    const scene = this.scenes[this.currentIndex];
    if (scene && scene.onInteraction) {
      scene.onInteraction(event, state);
    }
  }
}

export { SCENE_TITLES };
