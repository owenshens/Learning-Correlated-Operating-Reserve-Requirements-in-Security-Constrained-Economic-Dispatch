const rawCheckpoints = [0, 20, 40, 60, 80, 100, 120, 140, 160, 180];
const learnedCheckpointIndex = rawCheckpoints[rawCheckpoints.length - 1];

function formatCurrency(value) {
  return '$' + Math.round(value || 0).toLocaleString('en-US');
}

function formatMw(value) {
  return Math.round(value || 0).toLocaleString('en-US') + ' MW';
}

function formatPercentDelta(start, end) {
  if (!start) return '0.0%';
  return `${(((start - end) / start) * 100).toFixed(1)}%`;
}

function quantile(values, p) {
  if (!values?.length) return 0;
  const sorted = values.slice().sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * p) - 1));
  return sorted[index];
}

function checkpointSlides() {
  return rawCheckpoints.map((iterationIndex, index) => ({
    id: `appendix-${index + 1}`,
    label: `8.${index + 1}`,
    title: 'Training trace appendix',
    source_frame: 'appendix-checkpoint-trace',
    layout: 'appendix-canvas',
    animation_mode: 'checkpoint_trace',
    katex_blocks: [],
    static_html: '',
    iterationIndex,
  }));
}

function buildTitleSlide({ id, label }) {
  return {
    id,
    label,
    title: '',
    source_frame: 'title',
    layout: 'plain-title',
    animation_mode: 'title_trace_shape',
    figure_config: {
      traceIndex: rawCheckpoints[1],
      sequenceIndices: rawCheckpoints,
      stepDuration: 1.7,
    },
    katex_blocks: [],
    static_html: `
      <article class="slide slide-title-page">
        <section class="title-page__left">
          <div class="title-page__heading">
            <div class="title-page__headline">Differentiable Robust Optimization with Conformal Coverage</div>
          </div>
          <div class="title-page__people">
            <figure class="author-card">
              <img src="assets/authors/owen.png" alt="Owen Shen" class="author-card__photo" />
              <figcaption class="author-card__caption">
                <div class="author-card__name">Owen Shen</div>
                <div class="author-card__role">PhD Candidate</div>
                <div class="author-card__org">ORC, MIT</div>
              </figcaption>
            </figure>
            <figure class="author-card">
              <img src="assets/authors/patrick.jpeg" alt="Patrick Jaillet" class="author-card__photo" />
              <figcaption class="author-card__caption">
                <div class="author-card__name">Patrick Jaillet</div>
                <div class="author-card__role">Dugald C. Jackson Professor</div>
                <div class="author-card__org">EECS, MIT</div>
              </figcaption>
            </figure>
            <figure class="author-card">
              <img src="assets/authors/chao.jpg" alt="Hung-po Chao" class="author-card__photo" />
              <figcaption class="author-card__caption">
                <div class="author-card__name">Hung-po Chao</div>
                <div class="author-card__role">President &amp; CEO</div>
                <div class="author-card__org">Energy Trading Analytics, LLC</div>
              </figcaption>
            </figure>
            <figure class="author-card">
              <img src="assets/authors/haihao.jpeg" alt="Haihao Lu" class="author-card__photo" />
              <figcaption class="author-card__caption">
                <div class="author-card__name">Haihao Lu</div>
                <div class="author-card__role">Assistant Professor</div>
                <div class="author-card__org">Sloan School, MIT</div>
              </figcaption>
            </figure>
          </div>
        </section>
        <section class="title-page__right">
          <div class="figure-slot figure-slot--title">
            <img class="figure-fallback" src="assets/fallback/title-trace.png" alt="Training trace shape, forces, and hedge fallback" />
            <canvas data-figure-slot="title-trace" aria-label="Training trace shape, forces, and hedge"></canvas>
          </div>
        </section>
      </article>
    `,
  };
}

export function buildSlides(data = {}) {
  const trace = data.storyStatic;
  const methods = data.methods?.methods || {};
  const samples = trace?.samples || [];
  const startRecord = trace?.iterations?.[0] || {};
  const learnedRecord = trace?.iterations?.[learnedCheckpointIndex] || {};
  const compareLeftIndex = rawCheckpoints[1];
  const compareRightIndex = rawCheckpoints[2];
  const compareRightRecord = trace?.iterations?.[compareRightIndex] || {};
  const radii = samples.map((sample) => Math.hypot(sample.x, sample.y));
  const q95 = quantile(radii, 0.95);
  const boxCoverage = methods.box?.coverage ?? 0.986;
  const qBox = quantile(radii, boxCoverage);
  const sphereScale = qBox > 0 ? q95 / qBox : 1;
  const sphereReserve = (methods.box?.reserve_total ?? 0) * sphereScale;
  const sphereReserveCost = (methods.box?.reserve_cost ?? 0) * sphereScale;
  const sphereCost = (methods.box?.energy_cost ?? 0) + sphereReserveCost;

  return [
    buildTitleSlide({ id: 'title', label: '1' }),
    {
      id: 'problem-region',
      label: '2',
      title: 'Problem: the robust region is itself a decision',
      source_frame: 'problem',
      layout: 'two-column-problem',
      animation_mode: 'trace_shape',
      figure_config: {
        traceIndex: learnedCheckpointIndex,
        showLegend: true,
        showCoverageLabel: true,
        showGhost: true,
        showPreview: true,
        showForces: true,
        showSupport: true,
      },
      katex_blocks: [
        { key: 's2-inline-tau', tex: String.raw`\tau=0.95`, displayMode: false },
        {
          key: 's2-eq-set',
          tex: String.raw`\cU_{\bL,\rho}=\set{\bu\in\R^d:\norm{\bL^{-1}\bu}_2\le \rho}`,
          displayMode: true,
        },
        {
          key: 's2-eq-problem',
          tex: String.raw`\min_{\bL,\rho>0} V(\bL,\rho)\qquad \text{s.t.}\qquad \Prob(U\in \cU_{\bL,\rho}) \ge \tau,\quad \tau=0.95`,
          displayMode: true,
        },
      ],
      static_html: `
        <article class="slide">
          <div class="columns columns--problem">
            <section class="problem-text">
              <ul class="bullet-list bullet-list--compact">
                <li>
                  Robust dispatch is standard, and operators often target a coverage level such as
                  <span data-katex-key="s2-inline-tau"></span>.
                </li>
                <li>
                  The missing design choice is the geometry of the uncertainty region:
                  <strong>which joint error directions should be hedged?</strong>
                </li>
              </ul>
              <div class="display-block" data-katex-key="s2-eq-set"></div>
              <div class="display-block" data-katex-key="s2-eq-problem"></div>
              <p class="key-message">
                <strong>Key message.</strong> At a fixed 95% target, the uncertainty set is itself the learning problem.
              </p>
            </section>
            <section>
              <div class="figure-slot figure-slot--problem">
                <img class="figure-fallback" src="assets/fallback/problem-trace.png" alt="Robust region figure fallback" />
                <canvas data-figure-slot="problem-ellipse" aria-label="Animated robust region figure"></canvas>
              </div>
            </section>
          </div>
        </article>
      `,
    },
    {
      id: 'geometry-matters',
      label: '3',
      title: 'Why geometry matters',
      source_frame: 'why-geometry-matters',
      layout: 'two-column-compare',
      animation_mode: 'trace_compare',
      figure_config: {
        leftMode: 'sphere',
        leftBaseIndex: compareLeftIndex,
        leftRho: q95,
        rightIndex: compareRightIndex,
      },
      katex_blocks: [
        { key: 's3-inline-tau', tex: String.raw`\tau=0.95`, displayMode: false },
      ],
      static_html: `
        <article class="slide">
          <p class="frame-note">
            Both shapes are calibrated to roughly <span data-katex-key="s3-inline-tau"></span> coverage.
            The difference is the geometry.
          </p>
          <div class="columns columns--compare">
            <section class="compare-card">
              <div class="compare-card__title">Shape A</div>
              <div class="compare-card__subtitle">isotropic spherical hedge at about 95% coverage</div>
              <div class="figure-slot figure-slot--compare">
                <img class="figure-fallback" src="assets/fallback/compare-left.png" alt="Initial training checkpoint fallback" />
                <canvas data-figure-slot="compare-left" aria-label="Initial training checkpoint"></canvas>
              </div>
              <table class="metrics-table">
                <tr><td>Cost</td><td>${formatCurrency(sphereCost)}/hr</td></tr>
                <tr><td>Reserve</td><td>${formatMw(sphereReserve)}</td></tr>
              </table>
            </section>

            <section class="compare-card">
              <div class="compare-card__title">Shape B</div>
              <div class="compare-card__subtitle">learned correlated shape from the real training trace</div>
              <div class="figure-slot figure-slot--compare">
                <img class="figure-fallback" src="assets/fallback/compare-right.png" alt="Learned training checkpoint fallback" />
                <canvas data-figure-slot="compare-right" aria-label="Learned training checkpoint"></canvas>
              </div>
              <table class="metrics-table">
                <tr><td>Cost</td><td>${formatCurrency(compareRightRecord.cost)}/hr</td></tr>
                <tr><td>Reserve</td><td>${formatMw(compareRightRecord.reserve_total)}</td></tr>
              </table>
            </section>
          </div>
        </article>
      `,
    },
    {
      id: 'two-stage',
      label: '4',
      title: 'Two-stage optimization: geometry outside, dispatch inside',
      source_frame: 'two-stage-optimization',
      layout: 'two-stage-formulation',
      animation_mode: 'none',
      katex_blocks: [
        {
          key: 's4-outer-problem',
          tex: String.raw`\min_{\bL,\rho>0} V(\bL,\rho)\qquad \text{s.t.}\qquad \Prob(U\in \cU_{\bL,\rho}) \ge \tau`,
          displayMode: true,
        },
        {
          key: 's4-inner-value',
          tex: String.raw`\begin{aligned}
V(\bL,\rho)=\min_{\bg,\br}\quad
& \sum_{i\in\cG} \big(c_i^g g_i + c_i^r r_i\big) \\
\text{s.t.}\quad
& (\bg,\br)\in \cX,\\
& \sum_{i\in \cG_z} r_i \ge \rho \norm{\bL^\top A_z}_2,\qquad \forall z\in\cZ .
\end{aligned}`,
          displayMode: true,
        },
        {
          key: 's4-softbox',
          tex: String.raw`R_z^{\min}(\bL,\rho)=\rho\,\norm{\bL^\top A_z}_2.`,
          displayMode: true,
        },
        { key: 's4-inline-L', tex: String.raw`\bL`, displayMode: false },
        { key: 's4-inline-rho', tex: String.raw`\rho`, displayMode: false },
        { key: 's4-inline-gr', tex: String.raw`(\bg,\br)`, displayMode: false },
        { key: 's4-inline-U', tex: String.raw`\cU_{\bL,\rho}`, displayMode: false },
        { key: 's4-bullet-L', tex: String.raw`\bL`, displayMode: false },
        { key: 's4-bullet-rho', tex: String.raw`\rho`, displayMode: false },
      ],
      static_html: `
        <article class="slide">
          <div class="columns columns--stage">
            <section class="stage-text">
              <p class="section-label">Outer problem</p>
              <div class="display-block" data-katex-key="s4-outer-problem"></div>
              <p class="section-label">Inner value function</p>
              <div class="display-block" data-katex-key="s4-inner-value"></div>
              <div class="soft-box">
                <div>Only one term carries the uncertainty geometry:</div>
                <div data-katex-key="s4-softbox"></div>
              </div>
            </section>

            <section class="stage-side">
              <div class="flow-stack">
                <div class="flow-card flow-card--blue">
                  <strong>Shape <span data-katex-key="s4-inline-L"></span></strong>
                  orientation and relative axis lengths
                </div>
                <div class="flow-arrow flow-arrow--blue"></div>
                <div class="flow-card flow-card--orange">
                  <strong>Size <span data-katex-key="s4-inline-rho"></span></strong>
                  overall conservatism
                </div>
                <div class="flow-arrow flow-arrow--orange"></div>
                <div class="flow-card flow-card--green">
                  <strong>Robust dispatch</strong>
                  least-cost <span data-katex-key="s4-inline-gr"></span> consistent with
                  <span data-katex-key="s4-inline-U"></span>
                </div>
              </div>
              <ul class="bullet-list bullet-list--compact">
                <li><span data-katex-key="s4-bullet-L"></span> determines <em>where</em> the hedge is placed.</li>
                <li><span data-katex-key="s4-bullet-rho"></span> determines <em>how large</em> the hedge is.</li>
              </ul>
            </section>
          </div>
        </article>
      `,
    },
    {
      id: 'profile-out-size',
      label: '5',
      title: 'If the CDF is known, profile out the size',
      source_frame: 'profile-out-size',
      layout: 'profile-cdf',
      animation_mode: 'trace_cdf',
      figure_config: {
        traceIndex: learnedCheckpointIndex,
        sequenceIndices: rawCheckpoints,
        stepDuration: 1.7,
      },
      katex_blocks: [
        {
          key: 's5-problem',
          tex: String.raw`\min_{\bL,\rho>0} V(\bL,\rho)\qquad \text{s.t.}\qquad F_{\bL}(\rho)\ge \tau`,
          displayMode: true,
        },
        {
          key: 's5-cdf-def',
          tex: String.raw`F_{\bL}(r)=\Prob\!\left(\norm{\bL^{-1}U}_2 \le r\right)`,
          displayMode: true,
        },
        {
          key: 's5-rho',
          tex: String.raw`\rho_P(\bL)=\inf\set{r>0:F_{\bL}(r)\ge \tau}`,
          displayMode: true,
        },
        {
          key: 's5-boxed',
          tex: String.raw`\min_{\bL} V\big(\bL,\rho_P(\bL)\big)`,
          displayMode: true,
        },
        {
          key: 's5-inline-L',
          tex: String.raw`\bL`,
          displayMode: false,
        },
      ],
      static_html: `
        <article class="slide">
          <div class="columns columns--profile">
            <section class="profile-text">
              <p class="section-label">Start from the original constrained problem</p>
              <div class="display-block" data-katex-key="s5-problem"></div>
              <div class="display-block" data-katex-key="s5-cdf-def"></div>
              <p class="section-label">For each fixed shape, choose the smallest feasible radius</p>
              <div class="display-block" data-katex-key="s5-rho"></div>
              <div class="soft-box">
                <div data-katex-key="s5-boxed"></div>
              </div>
              <p class="operational-note">
                <strong>Operationally.</strong> Once <span data-katex-key="s5-inline-L"></span> is fixed, the CDF picks the smallest radius that reaches the target coverage.
              </p>
            </section>
            <section>
              <div class="figure-slot figure-slot--cdf">
                <img class="figure-fallback" src="assets/fallback/cdf-trace.png" alt="CDF profile fallback" />
                <canvas data-figure-slot="cdf-profile" aria-label="CDF profile figure"></canvas>
              </div>
            </section>
          </div>
        </article>
      `,
    },
    {
      id: 'profiled-gradient',
      label: '6',
      title: 'Gradient of <span data-katex-key="s6-title"></span>',
      source_frame: 'gradient',
      layout: 'gradient',
      animation_mode: 'none',
      katex_blocks: [
        {
          key: 's6-title',
          tex: String.raw`V\big(\bL,\rho_P(\bL)\big)`,
          displayMode: false,
        },
        {
          key: 's6-envelope',
          tex: String.raw`\nabla_{\bL}V(\bL,\rho)
=
\rho\sum_{z\in\cZ}\mu_z^*\frac{A_zA_z^\top\bL}{\norm{\bL^\top A_z}_2},
\qquad
\partial_\rho V(\bL,\rho)
=
\sum_{z\in\cZ}\mu_z^*\norm{\bL^\top A_z}_2`,
          displayMode: true,
        },
        {
          key: 's6-chain',
          tex: String.raw`\nabla_{\bL}V\big(\bL,\rho_P(\bL)\big)
=
\left.\nabla_{\bL}V(\bL,\rho)\right|_{\rho=\rho_P(\bL)}
+
\left.\partial_\rho V(\bL,\rho)\right|_{\rho=\rho_P(\bL)}
\,\nabla_{\bL}\rho_P(\bL)`,
          displayMode: true,
        },
        {
          key: 's6-rho-grad',
          tex: String.raw`\nabla_{\bL}\rho_P(\bL)
=
-\,\frac{\nabla_{\bL}F_{\bL}\big(\rho_P(\bL)\big)}{f_{\bL}\big(\rho_P(\bL)\big)}`,
          displayMode: true,
        },
        { key: 's6-inline-mu', tex: String.raw`\mu_z^*`, displayMode: false },
      ],
      static_html: `
        <article class="slide gradient-slide">
          <p class="section-label">Envelope derivatives from the dispatch solve</p>
          <div class="display-block" data-katex-key="s6-envelope"></div>
          <p class="section-label">Chain rule at the profiled radius</p>
          <div class="display-block" data-katex-key="s6-chain"></div>
          <div class="display-block" data-katex-key="s6-rho-grad"></div>
          <ul class="bullet-list bullet-list--compact">
            <li>First term: direct effect of reshaping the robust region at fixed radius.</li>
            <li>Second term: quantile-sensitivity correction because the required radius changes with shape.</li>
            <li><span data-katex-key="s6-inline-mu"></span> are dispatch shadow prices, so no differentiation through the optimizer is needed.</li>
          </ul>
        </article>
      `,
    },
    {
      id: 'implementation',
      label: '7',
      title: 'Implementation with data: estimate the CDF, then calibrate',
      source_frame: 'implementation',
      layout: 'implementation',
      animation_mode: 'none',
      katex_blocks: [
        { key: 's7-inline-Lk', tex: String.raw`\bL_k`, displayMode: false },
        { key: 's7-inline-Lnext', tex: String.raw`\bL_{k+1}`, displayMode: false },
        { key: 's7-inline-hatL', tex: String.raw`\hat{\bL}`, displayMode: false },
        { key: 's7-inline-hatF', tex: String.raw`\hat F_{\bL,\varepsilon}`, displayMode: false },
        { key: 's7-inline-tau', tex: String.raw`\tau`, displayMode: false },
        {
          key: 's7-score',
          tex: String.raw`S_i(\bL_k)=\norm{\bL_k^{-1}u_i}_2`,
          displayMode: true,
        },
        {
          key: 's7-cdf',
          tex: String.raw`\hat F_{\bL_k,\varepsilon}(r)=
\frac{1}{n_{\mathrm{tune}}}\sum_{i=1}^{n_{\mathrm{tune}}}
\Phi\!\left(\frac{r-S_i(\bL_k)}{\varepsilon}\right)`,
          displayMode: true,
        },
        {
          key: 's7-rhoeps-eq',
          tex: String.raw`\hat F_{\bL_k,\varepsilon}(\hat\rho_{\varepsilon}(\bL_k))=\tau`,
          displayMode: false,
        },
        {
          key: 's7-rhoeps-inline',
          tex: String.raw`\hat\rho_{\varepsilon}(\bL_k)`,
          displayMode: false,
        },
        {
          key: 's7-grad',
          tex: String.raw`\hat g_{\varepsilon}(\bL_k)`,
          displayMode: false,
        },
        {
          key: 's7-step',
          tex: String.raw`\bL_{k+1}=\Pi_{\Theta}\!\left(\bL_k-\eta_k\,\hat g_{\varepsilon}(\bL_k)\right)`,
          displayMode: true,
        },
        {
          key: 's7-cal-score',
          tex: String.raw`S_i=\norm{\hat{\bL}^{-1}u_i}_2`,
          displayMode: true,
        },
        {
          key: 's7-cal-rho',
          tex: String.raw`\hat\rho_{\tau}=S_{(k)},\qquad k=\lceil(n_{\mathrm{cal}}+1)\tau\rceil`,
          displayMode: true,
        },
        {
          key: 's7-deploy-set',
          tex: String.raw`\cU_{\hat{\bL},\hat\rho_{\tau}}`,
          displayMode: false,
        },
        {
          key: 's7-guarantee',
          tex: String.raw`\Prob\!\left(U_{\mathrm{new}}\in \cU_{\hat{\bL},\hat\rho_{\tau}}\right)\ge \tau`,
          displayMode: true,
        },
      ],
      static_html: `
        <article class="slide implementation-layout">
          <div class="implementation-note">
            Training alternates between two objects: the current shape and the score CDF induced by that shape.
            When the shape changes, the scores change; when the scores change, the training radius and the next gradient change too.
          </div>

          <div class="split-ribbon">
            <div class="split-ribbon__cell split-ribbon__cell--train">Train<small>dispatch + gradient step</small></div>
            <div class="split-ribbon__cell split-ribbon__cell--tune">Tune<small>scores + empirical CDF</small></div>
            <div class="split-ribbon__cell split-ribbon__cell--cal">Calibrate<small>final conformal radius</small></div>
            <div class="split-ribbon__cell split-ribbon__cell--test">Test<small>cost + coverage</small></div>
          </div>

          <div class="implementation-grid">
            <section class="impl-card impl-card--tune">
              <div class="impl-card__title">1. At the current shape, fit the score CDF</div>
              <p>
                Start from the current iterate <span data-katex-key="s7-inline-Lk"></span>. On the tuning split,
                convert each uncertainty sample into one scalar score:
              </p>
              <div data-katex-key="s7-score"></div>
              <p>
                A small score means the point is well inside the ellipsoid; a large score means it is near or beyond the boundary.
              </p>
              <div data-katex-key="s7-cdf"></div>
              <p>
                Choose the training radius so that <span data-katex-key="s7-rhoeps-eq"></span>.
              </p>
              <p>
                In words, <span data-katex-key="s7-rhoeps-inline"></span> is the current training-time
                <span data-katex-key="s7-inline-tau"></span>-quantile of the tuning scores.
              </p>
            </section>

            <section class="impl-card impl-card--train">
              <div class="impl-card__title">2. Compute the gradient and take a step</div>
              <p>
                Solve dispatch at the current shape and current training radius, then compute the profiled gradient
                <span data-katex-key="s7-grad"></span>.
              </p>
              <div data-katex-key="s7-step"></div>
              <p>
                This produces a new shape <span data-katex-key="s7-inline-Lnext"></span>.
              </p>
              <p>
                The key point is that the update changes the geometry, so it also changes the score distribution.
              </p>
            </section>

            <section class="impl-card impl-card--tune">
              <div class="impl-card__title">3. Refit the CDF for the new shape, then repeat</div>
              <p>
                After the update, recompute the scores using <span data-katex-key="s7-inline-Lnext"></span>.
              </p>
              <p>
                Refit the empirical CDF, get a new training radius, compute the next gradient, and repeat this loop.
              </p>
              <p>
                So the algorithm is: <strong>fit CDF → compute gradient → take a step → refit CDF → repeat</strong>.
              </p>
            </section>

            <section class="impl-card impl-card--cal">
              <div class="impl-card__title">4. After training, calibrate once for deployment</div>
              <p>
                Freeze the learned shape <span data-katex-key="s7-inline-hatL"></span> and compute fresh calibration scores:
              </p>
              <div data-katex-key="s7-cal-score"></div>
              <div data-katex-key="s7-cal-rho"></div>
              <p>
                Deploy the final set <span data-katex-key="s7-deploy-set"></span>.
              </p>
              <div data-katex-key="s7-guarantee"></div>
              <p>
                The test split is used only to report out-of-sample cost and empirical coverage.
              </p>
            </section>
          </div>
        </article>
      `,
    },
    ...checkpointSlides(),
    buildTitleSlide({ id: 'closing', label: '9' }),
  ];
}
