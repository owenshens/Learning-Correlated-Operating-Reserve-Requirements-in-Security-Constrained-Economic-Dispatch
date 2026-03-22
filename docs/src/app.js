import { StageRenderer } from './runtime/stageRenderer.js?v=20260321u';
import { PresentationController } from './presentation/presentationController.js?v=20260321u';
import { buildSlides } from './presentation/slideManifest.js?v=20260321u';
import { renderKatexBlocks } from './presentation/mathRenderer.js?v=20260321u';
import { attachFigureSlots, destroyFigureSlots } from './presentation/figureSlotRenderers.js?v=20260321u';

function loadJson(path) {
  return fetch(path).then((response) => {
    if (!response.ok) {
      throw new Error(`Failed to load ${path}: ${response.status}`);
    }
    return response.json();
  });
}

async function waitForKatex() {
  const timeoutMs = 8000;
  const start = performance.now();
  while (!window.katex) {
    if (performance.now() - start > timeoutMs) {
      throw new Error('KaTeX failed to load.');
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

async function loadData() {
  const [storyStatic, storyToy, methods, zones, network] = await Promise.all([
    loadJson('data/precomputed/story_static_decoupled.json'),
    loadJson('data/precomputed/story_toy.json'),
    loadJson('data/precomputed/methods.json'),
    loadJson('data/zones.json'),
    loadJson('data/network.json'),
  ]);

  return { storyStatic, storyToy, methods, zones, network };
}

const stageEl = document.getElementById('deck-stage');
const frameTitleEl = document.getElementById('frame-title');
const frameFootLeftEl = document.getElementById('frame-foot-left');
const frameLabelEl = document.getElementById('frame-label');
const frameProgressFillEl = document.getElementById('frame-progress-fill');
const slideContentEl = document.getElementById('slide-content');
const appendixCanvasEl = document.getElementById('appendix-canvas');
const btnPrev = document.getElementById('btn-prev');
const btnNext = document.getElementById('btn-next');

let dataBundle = null;
let controller = null;
let stageRenderer = null;
let activeFigureSlots = [];
let activeSlideId = null;
let animationFrameId = null;
let lastTimestamp = 0;

function getCurrentSlide() {
  return controller?.getCurrentSlide() || null;
}

function getCheckpointFrame(slide) {
  const trace = dataBundle.storyStatic;
  const record = trace.iterations[slide.iterationIndex];
  const nextRecord = trace.iterations[Math.min(slide.iterationIndex + 1, trace.iterations.length - 1)];

  return {
    state: {
      selectedZone: null,
      playState: 'paused',
      method: 'staticl',
      coupled: false,
    },
    slide,
    act: 'real-static',
    mode: 'story',
    loopStep: 'shape',
    record,
    nextRecord,
    historyTrace: trace,
    currentIndex: slide.iterationIndex,
    currentTraceIndex: slide.iterationIndex,
    slideIndex: controller.getCurrentIndex(),
    totalSlides: controller.getSlideCount(),
    samples: trace.samples || [],
  };
}

function syncNavButtons() {
  const currentIndex = controller.getCurrentIndex();
  btnPrev.disabled = currentIndex <= 0;
  btnNext.disabled = currentIndex >= controller.getSlideCount() - 1;
}

function syncShell(force = false) {
  const slide = getCurrentSlide();
  if (!slide) return;

  if (!force && slide.id === activeSlideId) {
    syncNavButtons();
    return;
  }

  destroyFigureSlots(activeFigureSlots);
  activeFigureSlots = [];
  activeSlideId = slide.id;

  stageEl.classList.toggle('is-plain', slide.layout === 'plain-title');
  stageEl.classList.toggle('is-appendix', slide.animation_mode === 'checkpoint_trace');
  stageEl.dataset.slideTitle = slide.title
    ? slide.title.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()
    : '';
  stageEl.dataset.slideLabel = slide.label || '';

  frameTitleEl.innerHTML = slide.title;
  slideContentEl.innerHTML = slide.static_html || '';
  frameFootLeftEl.textContent = slide.layout === 'plain-title'
    ? ''
    : 'Differentiable Robust Optimization with Conformal Coverage';
  frameLabelEl.textContent = slide.label;

  const progress = controller.getSlideCount() <= 1
    ? 1
    : controller.getCurrentIndex() / (controller.getSlideCount() - 1);
  frameProgressFillEl.style.width = `${Math.max(0, Math.min(1, progress)) * 100}%`;

  renderKatexBlocks(frameTitleEl, slide.katex_blocks);
  renderKatexBlocks(slideContentEl, slide.katex_blocks);

  if (slide.animation_mode !== 'checkpoint_trace') {
    activeFigureSlots = attachFigureSlots(slide, slideContentEl, dataBundle);
  }

  syncNavButtons();
}

function renderLoop(timestamp) {
  const dt = lastTimestamp ? (timestamp - lastTimestamp) / 1000 : 0;
  lastTimestamp = timestamp;

  const slide = getCurrentSlide();
  if (slide) {
    if (slide.animation_mode === 'checkpoint_trace') {
      const rect = appendixCanvasEl.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        const dpr = window.devicePixelRatio || 1;
        const targetWidth = Math.max(1, Math.round(rect.width * dpr));
        const targetHeight = Math.max(1, Math.round(rect.height * dpr));
        if (appendixCanvasEl.width !== targetWidth || appendixCanvasEl.height !== targetHeight) {
          appendixCanvasEl.width = targetWidth;
          appendixCanvasEl.height = targetHeight;
        }

        const ctx = appendixCanvasEl.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
        stageRenderer.update(dt);
        stageRenderer.render(ctx, rect.width, rect.height, getCheckpointFrame(slide));
      }
    } else {
      for (const slot of activeFigureSlots) {
        slot.update?.(dt);
        slot.render?.();
      }
    }
  }

  animationFrameId = window.requestAnimationFrame(renderLoop);
}

function move(delta) {
  if (!controller) return;
  if (delta > 0) {
    controller.next();
  } else {
    controller.prev();
  }
  syncShell();
}

function bindEvents() {
  btnPrev.addEventListener('click', () => move(-1));
  btnNext.addEventListener('click', () => move(1));

  document.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      move(1);
    }

    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      move(-1);
    }
  });

  window.addEventListener('resize', () => {
    for (const slot of activeFigureSlots) {
      slot.render?.();
    }
  });
}

function showError(error) {
  stageEl.classList.remove('is-appendix');
  stageEl.classList.remove('is-plain');
  frameTitleEl.textContent = 'Presentation Load Error';
  slideContentEl.innerHTML = `
    <div class="status-card">
      <p><strong>Unable to load the presentation.</strong></p>
      <p>${error.message}</p>
    </div>
  `;
  frameLabelEl.textContent = '';
  frameProgressFillEl.style.width = '0%';
  console.error(error);
}

async function init() {
  await waitForKatex();
  dataBundle = await loadData();
  controller = new PresentationController(buildSlides(dataBundle));
  stageRenderer = new StageRenderer({ zones: dataBundle.zones, network: dataBundle.network });

  bindEvents();
  syncShell(true);
  animationFrameId = window.requestAnimationFrame(renderLoop);
}

init().catch(showError);

window.addEventListener('beforeunload', () => {
  if (animationFrameId !== null) {
    window.cancelAnimationFrame(animationFrameId);
  }
});
