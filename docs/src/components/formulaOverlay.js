// === Formula Overlay ===
// Renders per-scene mathematical formulas in a DOM panel using Unicode + HTML.

const FORMULAS = [
  // Scene 0: "The Grid & Its Uncertainty" — no formula
  null,

  // Scene 1: "Uncertainty Has Shape"
  {
    lines: [
      '<span class="math-highlight">U</span><sub>\u03b8,\u03c1</sub> = { <b>u</b> : \u2016<span class="math-highlight">L</span><sup>\u22121</sup><b>u</b>\u2016 \u2264 <span class="math-accent">\u03c1</span> }',
    ],
    label: 'Ellipsoidal uncertainty set',
  },

  // Scene 2: "From Shape to Reserves"
  {
    lines: [
      '<span class="math-highlight">R</span><sub>z</sub> = <span class="math-accent">\u03c1</span> \u00b7 \u2016<span class="math-highlight">L</span><sup>\u22a4</sup><b>w</b><sub>z</sub>\u2016',
    ],
    label: 'Reserve = support function along exposure direction',
  },

  // Scene 3: "The Cost of Protection"
  {
    lines: [
      'min \u2211 c<sub>g</sub> p<sub>g</sub>',
      's.t.  r<sub>z</sub> \u2265 <span class="math-highlight">R<sub>z</sub></span>',
      '<span class="math-accent">\u03bc</span><sub>z</sub> = \u2202Cost / \u2202R<sub>z</sub>',
    ],
    label: 'Shadow price = marginal cost of protection',
  },

  // Scene 4: "The Gradient Flows Backward"
  {
    lines: [
      '<span class="math-accent">\u2202Cost / \u2202L</span> = \u2211<sub>z</sub> <span class="math-accent">\u03bc</span><sub>z</sub> \u00b7 \u2202<span class="math-highlight">R</span><sub>z</sub> / \u2202<span class="math-highlight">L</span>',
    ],
    label: 'Envelope gradient: duals reshape the uncertainty set',
  },

  // Scene 5: "Learning Reshapes Uncertainty"
  {
    lines: [
      '<span class="math-highlight">L</span><sup>(k+1)</sup> = <span class="math-highlight">L</span><sup>(k)</sup> \u2212 \u03b7 <span class="math-accent">\u2207</span><sub>L</sub> Cost',
    ],
    label: 'Gradient descent on the shape factor',
  },

  // Scene 6: "Methods Compared"
  {
    lines: [
      '<span class="math-dim">Box:</span> L = diag(\u03c3)',
      '<span class="math-dim">Sample:</span> L = chol(\u03a3\u0302)',
      '<span class="math-highlight">Learned:</span> L = argmin E[Cost]',
    ],
    label: 'Fixed vs. learned uncertainty geometry',
  },

  // Scene 7: "Interactive Sandbox" — no formula
  null,
];

let elPanel = null;
let elContent = null;

export function initFormulaOverlay() {
  elPanel = document.getElementById('formula-panel');
  elContent = document.getElementById('formula-content');
}

export function updateFormula(sceneIndex) {
  if (!elPanel || !elContent) return;

  const formula = FORMULAS[sceneIndex] || null;

  if (!formula) {
    elPanel.classList.remove('visible');
    return;
  }

  let html = '';
  for (const line of formula.lines) {
    html += `<div class="formula-line">${line}</div>`;
  }
  if (formula.label) {
    html += `<div class="formula-label">${formula.label}</div>`;
  }

  elContent.innerHTML = html;
  elPanel.classList.remove('visible');
  // Trigger reflow for transition
  requestAnimationFrame(() => {
    requestAnimationFrame(() => elPanel.classList.add('visible'));
  });
}
