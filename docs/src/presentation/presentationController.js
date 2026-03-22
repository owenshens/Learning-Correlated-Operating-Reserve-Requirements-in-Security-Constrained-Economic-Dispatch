export class PresentationController {
  constructor(slides) {
    this.slides = slides;
    this.state = {
      index: 0,
      playState: 'paused',
    };
    this.elapsed = 0;
  }

  getSlides() {
    return this.slides;
  }

  getSlideCount() {
    return this.slides.length;
  }

  getState() {
    return this.state;
  }

  getCurrentSlide() {
    return this.slides[this.state.index] || this.slides[0] || null;
  }

  getCurrentIndex() {
    return this.state.index;
  }

  getCounterLabel() {
    return `${this.state.index + 1} / ${this.getSlideCount()}`;
  }

  setIndex(index) {
    const maxIndex = Math.max(0, this.getSlideCount() - 1);
    this.state.index = Math.max(0, Math.min(maxIndex, index));
    this.elapsed = 0;
  }

  next() {
    if (this.state.index < this.getSlideCount() - 1) {
      this.setIndex(this.state.index + 1);
      return;
    }
    this.pause();
  }

  prev() {
    if (this.state.index > 0) {
      this.setIndex(this.state.index - 1);
    }
  }

  togglePlay() {
    this.state.playState = this.state.playState === 'playing' ? 'paused' : 'playing';
  }

  pause() {
    this.state.playState = 'paused';
  }

  update(dt) {
    if (this.state.playState !== 'playing') return false;
    const slide = this.getCurrentSlide();
    const duration = slide?.autoplayDuration ?? 8;
    this.elapsed += dt;
    if (this.elapsed >= duration) {
      this.next();
      return true;
    }
    return false;
  }
}
