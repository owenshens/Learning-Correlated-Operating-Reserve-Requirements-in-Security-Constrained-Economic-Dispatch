const MACROS = {
  '\\R': '\\mathbb{R}',
  '\\Prob': '\\mathbb{P}',
  '\\cU': '\\mathcal{U}',
  '\\cX': '\\mathcal{X}',
  '\\cG': '\\mathcal{G}',
  '\\cD': '\\mathcal{D}',
  '\\cZ': '\\mathcal{Z}',
  '\\bL': '\\bm{L}',
  '\\bg': '\\bm{g}',
  '\\br': '\\bm{r}',
  '\\bu': '\\bm{u}',
  '\\bmu': '\\bm{\\mu}',
  '\\norm': '\\left\\lVert #1 \\right\\rVert',
  '\\set': '\\left\\{#1\\right\\}',
};

export function renderKatexBlocks(root, blocks) {
  if (!root || !window.katex || !Array.isArray(blocks)) return;

  for (const block of blocks) {
    const nodes = root.querySelectorAll(`[data-katex-key="${block.key}"]`);
    if (!nodes.length) continue;

    for (const node of nodes) {
      window.katex.render(block.tex, node, {
        displayMode: Boolean(block.displayMode),
        throwOnError: false,
        strict: 'ignore',
        macros: MACROS,
      });
    }
  }
}
