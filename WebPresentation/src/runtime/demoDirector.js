export const LOOP_STEPS = ['shape', 'calibrate', 'reserves', 'solve', 'duals', 'gradient', 'update'];

const SLIDE_DURATION = 3.2;

function buildSlides(data) {
  const real = data.storyStatic;
  const checkpointIndices = Array.from({ length: 10 }, (_, index) => index * 20);

  return checkpointIndices.map((iterationIndex, slideIndex) => ({
    storyKey: 'real-static',
    iterationIndex,
    loopStep: 'shape',
    chapter: 'Real Experiment · Snapshots Every 20 Iterations',
    title: `Iteration ${iterationIndex + 1}`,
    narration:
      slideIndex === 0
        ? 'Start from the real initial iterate. The same four views will stay fixed on every slide so the only moving part is the optimization state itself.'
        : 'This is a real checkpoint from the training trace. Compare the shape, 95% capture, cost history, smooth CDF, and dual pressure against the earlier snapshots.',
  }));
}

export class DemoDirector {
  constructor(data) {
    this.data = data;
    this.slides = buildSlides(data);
    this.state = {
      mode: 'story',
      act: this.slides[0]?.storyKey || 'toy',
      loopStepIndex: LOOP_STEPS.indexOf(this.slides[0]?.loopStep || 'shape'),
      iterationIndex: this.slides[0]?.iterationIndex || 0,
      slideIndex: 0,
      selectedZone: null,
      playState: 'paused',
      method: 'staticl',
      coupled: false,
    };
    this.stepElapsed = 0;
  }

  getState() {
    return this.state;
  }

  getSlides() {
    return this.slides;
  }

  getSlideCount() {
    return this.slides.length;
  }

  getCurrentSlide() {
    return this.slides[this.state.slideIndex] || this.slides[0];
  }

  syncStateFromSlide() {
    const slide = this.getCurrentSlide();
    if (!slide) return;
    this.state.act = slide.storyKey;
    this.state.iterationIndex = slide.iterationIndex;
    this.state.loopStepIndex = Math.max(0, LOOP_STEPS.indexOf(slide.loopStep));
  }

  getLoopStep() {
    return this.getCurrentSlide()?.loopStep || LOOP_STEPS[0];
  }

  getActiveTrace() {
    return this.data.storyStatic;
  }

  getIterationCount() {
    return this.getSlideCount();
  }

  getCurrentRecord() {
    const trace = this.getActiveTrace();
    const iterationIndex = this.getCurrentSlide()?.iterationIndex ?? 0;
    if (!trace?.iterations?.length) return null;
    return trace.iterations[iterationIndex] || trace.iterations[trace.iterations.length - 1];
  }

  getNextRecord() {
    const trace = this.getActiveTrace();
    const iterationIndex = this.getCurrentSlide()?.iterationIndex ?? 0;
    if (!trace?.iterations?.length) return null;
    const nextIndex = Math.min(iterationIndex + 1, trace.iterations.length - 1);
    return trace.iterations[nextIndex];
  }

  getReferenceTrace() {
    return this.getActiveTrace();
  }

  setIteration(index) {
    this.setSlide(index);
  }

  setSlide(index) {
    const maxIndex = Math.max(0, this.getSlideCount() - 1);
    this.state.slideIndex = Math.max(0, Math.min(maxIndex, index));
    this.syncStateFromSlide();
    this.stepElapsed = 0;
  }

  setLoopStep(step) {
    const slide = this.getCurrentSlide();
    if (!slide) return;
    const targetStep = typeof step === 'string' ? step : LOOP_STEPS[step];
    if (!targetStep || targetStep === slide.loopStep) return;

    const sameCheckpoint = this.slides.findIndex(
      (candidate) =>
        candidate.storyKey === slide.storyKey &&
        candidate.iterationIndex === slide.iterationIndex &&
        candidate.loopStep === targetStep,
    );
    if (sameCheckpoint >= 0) {
      this.setSlide(sameCheckpoint);
      return;
    }

    const sameStory = this.slides.findIndex(
      (candidate) => candidate.storyKey === slide.storyKey && candidate.loopStep === targetStep,
    );
    if (sameStory >= 0) {
      this.setSlide(sameStory);
    }
  }

  togglePlay() {
    this.state.playState = this.state.playState === 'playing' ? 'paused' : 'playing';
  }

  pause() {
    this.state.playState = 'paused';
  }

  nextStep() {
    if (this.state.slideIndex < this.getSlideCount() - 1) {
      this.setSlide(this.state.slideIndex + 1);
      return;
    }
    this.pause();
  }

  prevStep() {
    if (this.state.slideIndex > 0) {
      this.setSlide(this.state.slideIndex - 1);
    }
  }

  setSelectedZone(zoneIndex) {
    this.state.selectedZone = zoneIndex;
  }

  update(dt) {
    if (this.state.playState !== 'playing') return;
    this.stepElapsed += dt;
    if (this.stepElapsed >= SLIDE_DURATION) {
      this.nextStep();
    }
  }
}
