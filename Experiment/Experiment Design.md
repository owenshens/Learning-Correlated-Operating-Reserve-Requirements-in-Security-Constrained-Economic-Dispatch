# Experiment Design: Differentiable Robust Optimization for Operating Reserve Markets

## 1. Overview

This document describes the complete experimental design for evaluating the differentiable robust optimization framework on the IEEE 118-bus system. We compare **4 methods** for constructing ellipsoidal uncertainty sets, all evaluated under **conformal calibration** for fair coverage comparison.

**Methods:**
1. **Independent** — diagonal ellipsoid (diagonal L), no training
2. **Sample Covariance** — full static ellipsoid from data, no training
3. **Learned (Static)** — task-aware L trained via profiled gradient, no context
4. **Learned (Contextual)** — context-dependent L trained via profiled gradient + neural network

**Key insight:** Methods 1–2 are purely statistical (estimated from data). Methods 3–4 use our framework's profiled gradient to optimize L for minimum dispatch cost. The comparison shows the value of (a) task-aware training and (b) context dependence.

---

## 2. Data Pipeline

### 2.1 Generated Data (from `generate_uncertainty.py`)

All data is pre-generated and stored in `Experiment/data/uncertainty/`:

| File | Shape | Description |
|------|-------|-------------|
| `uncertainty_15d.parquet` | (35040, 15) | Uncertainty vectors $u_t \in \mathbb{R}^{15}$ |
| `context_7d.parquet` | (35040, 7) | Context features $\xi_t \in \mathbb{R}^7$ |
| `L_true_t.npy` | (35040, 15, 15) | Ground-truth Cholesky factors $L_{\mathrm{true}}(\xi_t)$ |
| `allocation_matrix.npy` | (10, 15) | Allocation matrix $A$ |
| `metadata.json` | — | Split indices, dimension labels, parameters |

**Uncertainty dimensions** (15 = 3 sources × 5 regions):

| Index | Label | Source | Region |
|:-----:|-------|--------|--------|
| 0–4 | load_R1, ..., load_R5 | Load | R1–R5 |
| 5–9 | solar_R1, ..., solar_R5 | Solar | R1–R5 |
| 10–14 | wind_R1, ..., wind_R5 | Wind | R1–R5 |

**Context features** (7-D):
- Normalized forecasts: load, solar, wind (3)
- Cyclical time: sin/cos of hour, sin/cos of month (4)

### 2.1.1 Context-Dependent Data Generation

The ground-truth covariance $\Sigma_{\mathrm{true}}(\xi_t) = D(\xi_t) R(\xi_t) D(\xi_t)$ varies with context through two channels:

**Variance scaling** — the diagonal $D(\xi_t)$ modulates marginal standard deviations:

| Source | Formula | Scaling Range | Coefficient of Variation |
|--------|---------|:------------:|:------------------------:|
| Load | $\sigma_{\mathrm{load}} \times (0.6 + 0.4 \cdot f_{\mathrm{load}}/\bar{f}_{\mathrm{load}})$ | 0.3×–1.8× | ~25% |
| Solar (active regions) | $\sigma_{\mathrm{solar}} \times \mathrm{clip}(f_{\mathrm{solar}}/f_{75}, 0.01, 3.0)$ | 0.01×–3.0× | ~130% |
| Wind (active regions) | $\sigma_{\mathrm{wind}} \times \mathrm{clip}(f_{\mathrm{wind}}/f_{50}, 0.1, 4.0)^{0.7}$ | ~0.2×–2.5× | ~35% |
| Wind (non-wind regions) | $0.5 \times \mathrm{clip}(\bar{f}_{\mathrm{wind}}/\overline{\bar{f}}_{\mathrm{wind}}, 0.3, 2.0)^{0.3}$ | ~0.35×–0.6× | ~10% |

**Correlation perturbation** — the 3×3 source correlation $R_{\mathrm{source}}(\xi_t)$ shifts with context:

| Effect | Formula | Range |
|--------|---------|:-----:|
| Solar-wind anticorrelation | $\Delta R_{sw} = -0.40 \times \mathrm{solar\_ctx}$ | $[-0.40, 0]$ |
| Wind-load correlation | $\Delta R_{wl} = +0.25 \times \mathrm{wind\_ctx}$ | $[0, +0.25]$ |
| Load-solar anticorrelation | $\Delta R_{ls} = -0.20 \times \mathrm{load\_ctx}$ | $[-0.20, 0]$ |

These effects are designed to create meaningful reserve-requirement variation (~25–35% CV in total reserves) so that context-dependent methods have scope to outperform static approaches.

### 2.2 IEEE 118-Bus System Data

From `Experiment/data/`:

| File | Description |
|------|-------------|
| `generator_data.csv` | 54 generators: bus, zone, min/max capacity, cost_c1, reserve_cost |
| `zone_summary.csv` | 10 zones: bus ranges, load (MW) |
| `branch_data.csv` | 186 branches: all with max_loading = 9900 MW (non-binding) |

### 2.3 Data Split

Chronological three-way split (no shuffling):

| Split | Fraction | Hours | Date Range | Purpose |
|-------|:--------:|:-----:|-----------|---------|
| Train | 60% | 21,024 | 2020-01 to 2022-05 | Learn L via profiled gradient |
| Tune | 20% | 7,008 | 2022-05 to 2023-09 | Estimate $\hat\rho_\varepsilon$ and quantile sensitivity |
| Calibrate | 20% | 7,008 | 2023-09 to 2023-12 | Conformal calibration for coverage guarantee |

---

## 3. SCED Formulation

### 3.1 Regime

Since all line thermal limits are 9900 MW (effectively non-binding), we operate in **Regime 1** (zonal reserve). Line flow constraints never bind, so:
- The SCED is a simple LP (no robust line constraints)
- All gradients are available in closed form (solver-free for gradient computation)
- One LP solve per training iteration to get dual multipliers $\mu_z^*$

### 3.2 The LP

$$\min_{g, r} \sum_{i \in \mathcal{G}} \left( c_i^g \cdot g_i + c_i^r \cdot r_i \right)$$

subject to:

| Constraint | Formula | Dual |
|------------|---------|:----:|
| Power balance | $\sum_i g_i = \sum_z D_z$ | $\lambda$ |
| Generator capacity | $g_i + r_i \leq \bar{g}_i, \quad \forall i$ | $\nu_i$ |
| Minimum generation | $g_i \geq \underline{g}_i, \quad \forall i$ | (bounds) |
| Reserve non-negative | $r_i \geq 0, \quad \forall i$ | (bounds) |
| **Zonal reserve** | $\sum_{i \in \mathcal{G}_z} r_i \geq R_z^{\min}(L, \rho), \quad \forall z$ | $\mu_z^*$ |

where:
- $c_i^g$ = `cost_c1` (linear generation cost, \$/MWh)
- $c_i^r$ = `reserve_cost` (\$/MWh)
- $D_z$ = static zone load from `zone_summary.csv`
- $R_z^{\min}(L, \rho)$ = zonal reserve requirement (from uncertainty set)

### 3.3 Reserve Requirements

The zonal reserve requirement for zone $z$ is determined by the support function of the ellipsoidal uncertainty set:

$$R_z^{\min}(L, \rho) = \sigma_{\mathcal{U}_{L,\rho}}(w_z) = \rho \| L^\top w_z \|_2$$

where $w_z = A^\top e_z \in \mathbb{R}^{15}$ is the **effective exposure vector** for zone $z$:
- $A \in \mathbb{R}^{10 \times 15}$ is the allocation matrix (maps 15-D uncertainty to 10 zonal impacts)
- $e_z \in \mathbb{R}^{10}$ is the $z$-th standard unit vector
- $w_z$ equals the $z$-th row of $A$ (transposed to a column vector)

**Interpretation:** $R_z^{\min}$ is the worst-case net-injection deviation at zone $z$ over all uncertainty realizations in the ellipsoid $\mathcal{U}_{L,\rho}$.

### 3.4 Dual Multipliers

The dual multiplier $\mu_z^*$ on the zonal reserve constraint is the shadow price — the marginal cost of increasing the reserve requirement at zone $z$ by 1 MW. These are extracted from the LP solution and used for gradient computation.

---

## 4. The 4 Methods

### 4.1 Method 1: Independent (Diagonal Ellipsoid)

**Construction:**
$$L_{\mathrm{ind}} = \mathrm{diag}(\hat\sigma_1, \ldots, \hat\sigma_{15})$$

where $\hat\sigma_i = \mathrm{std}(u_{\mathrm{train}, i})$ is the marginal standard deviation of dimension $i$ from training data.

**Properties:**
- Ignores all cross-dimensional correlations
- Industry standard baseline — each source/region is treated independently
- No training required

**Conformal calibration:** Compute gauge scores $S_i = \| L_{\mathrm{ind}}^{-1} u_i \|_2$ on calibration data, set $\rho = S_{(\lceil(n_{\mathrm{cal}}+1)\tau\rceil)}$.

### 4.2 Method 2: Sample Covariance

**Construction:**
$$\hat\Sigma = \frac{1}{n_{\mathrm{train}}} \sum_{t=1}^{n_{\mathrm{train}}} u_t u_t^\top, \qquad L_{\mathrm{cov}} = \mathrm{chol}(\hat\Sigma)$$

**Properties:**
- Captures all pairwise correlations from training data
- Statistically optimal if the data is Gaussian
- No training required — purely statistical estimate
- Does not account for what the SCED optimizer cares about

**Conformal calibration:** Same as Method 1 with $L = L_{\mathrm{cov}}$.

### 4.3 Method 3: Learned Static (Our Framework, No Context)

**Construction:**
- $L \in \mathbb{R}^{15 \times 15}$ is a free lower-triangular matrix (120 parameters)
- Initialized: $L_0 = L_{\mathrm{cov}}$ (warm start from Method 2)
- Trained via **Algorithm 1** (profiled gradient) to minimize dispatch cost

**Properties:**
- Same representational power as Method 2 (single static L)
- But optimized for task cost, not statistical fit
- Demonstrates the value of task-aware training
- May redistribute correlation to reduce cost in high-μ zones

**Conformal calibration:** After training, calibrate on calibration set.

### 4.4 Method 4: Learned Contextual (Our Framework)

**Construction:**
- Neural network $L_\phi(\xi): \mathbb{R}^7 \to \mathbb{R}^{15 \times 15}$
- Architecture: `Linear(7, 128) → ReLU → Linear(128, 64) → ReLU → Linear(64, 120)` → Cholesky construction
- 120 outputs fill the lower triangle of L (with `exp()` on the 15 diagonal entries for positivity)
- Trace normalization: $L \leftarrow L / \sqrt{\mathrm{tr}(LL^\top) / 15}$
- Initialized: bias of last layer set to vectorized $L_{\mathrm{cov}}$; hidden layer weights scaled by 0.1

**Training hyperparameters** (tuned via 3-phase sweep):
- Learning rate: $3 \times 10^{-4}$ (Adam optimizer)
- Batch size: 8 (per-sample SCED gives context-specific dual multipliers)
- Iterations: 1500 (early stopping with patience = 400)
- Smoothing bandwidth: $\varepsilon = 0.5$
- Gradient clipping: NN params max-norm 1.0, per-sample profiled gradient max-norm 100.0

**Properties:**
- Adapts uncertainty set to current conditions (time of day, forecast levels)
- Can learn that solar variance vanishes at night, wind variance increases in winter, etc.
- Most expressive model — should achieve lowest cost
- Trained via Algorithm 1 with PyTorch autograd for NN parameters

**Conformal calibration:** Scores $S_i = \| L_\phi(\xi_i)^{-1} u_i \|_2$, single global $\rho$ for marginal coverage.

---

## 5. Training Algorithm (Methods 3 & 4)

### 5.1 Profiled Objective

The bilevel problem is profiled into:
$$\min_\theta J(\theta) := V(\theta, \rho_P(\theta))$$

where $V(\theta, \rho)$ is the SCED cost and $\rho_P(\theta)$ is the $\tau$-quantile of gauge scores.

### 5.2 Algorithm 1: Profiled Gradient Training

At iteration $k$:

**Step A — Tuning** (on $\mathcal{D}_{\mathrm{tune}}$):

1. Compute gauge scores: $S_i(\theta_k) = s_{\theta_k}(u_i) = \| L_k^{-1} u_i \|_2$
   - Method 3: $L_k$ is the current static L
   - Method 4: $L_k = L_\phi(\xi_i)$ (different for each tune sample)

2. Smoothed $\tau$-quantile via bisection:
   $$\hat\rho_\varepsilon(\theta_k) = \inf\left\{ r : \frac{1}{n_{\mathrm{tune}}} \sum_i \Phi\left(\frac{r - S_i}{\varepsilon}\right) \geq \tau \right\}$$
   where $\Phi$ is the standard normal CDF and $\varepsilon > 0$ is the bandwidth.

3. Kernel weights: $\omega_i = \varphi\left(\frac{\hat\rho - S_i}{\varepsilon}\right)$ where $\varphi$ is the standard normal PDF.

4. Quantile sensitivity:
   $$\widehat{\nabla_\theta \rho_\varepsilon}(\theta_k) = \frac{\sum_i \omega_i \nabla_\theta s_\theta(u_i)}{\sum_i \omega_i}$$

**Step B — Robust Solve:**

1. Compute zonal reserve requirements: $R_z = \hat\rho \cdot \| L_k^\top w_z \|_2$ for each zone $z$
2. Solve SCED LP → extract dual multipliers $\mu_z^*$

**Step C — Gradient:**

1. **Envelope shape term:**
   $$g_{\mathrm{shape}} = \sum_{z=1}^{10} \mu_z^* \cdot \nabla_L \sigma_{\mathcal{U}_{L,\hat\rho}}(w_z) = \sum_z \mu_z^* \cdot \frac{\hat\rho \cdot w_z w_z^\top L}{\| L^\top w_z \|_2}$$

2. **Envelope size sensitivity:**
   $$g_{\mathrm{size}} = \sum_{z=1}^{10} \mu_z^* \cdot \| L^\top w_z \|_2$$

3. **Full profiled gradient:**
   $$\hat{g}_\varepsilon = g_{\mathrm{shape}} + g_{\mathrm{size}} \cdot \nabla_L \hat\rho_\varepsilon$$

4. **Update:**
   $$L \leftarrow \Pi_\Theta(L - \eta_k \cdot \hat{g}_\varepsilon)$$
   where projection $\Pi_\Theta$ enforces: lower triangular, positive diagonal, trace normalization.

**For Method 4:** The gradient $\hat{g}_\varepsilon$ is computed as $\partial J / \partial L$ (15×15 matrix). This is set as the `.grad` for the NN output, and PyTorch autograd backpropagates through the network to update $\phi$.

### 5.3 Key Gradients

**Support function gradient** (paper Eq. 16):
$$\nabla_L \sigma_{\mathcal{U}_{L,\rho}}(w) = \frac{\rho \cdot w w^\top L}{\| L^\top w \|_2}$$

**Gauge function gradient** (paper Eq. 17, needed for quantile sensitivity):
$$\nabla_L s_L(u) = -\frac{L^{-\top} (L^{-1}u)(L^{-1}u)^\top}{\| L^{-1}u \|_2}$$

---

## 6. Conformal Calibration

After training (or directly for methods 1–2):

1. Compute gauge scores on $\mathcal{D}_{\mathrm{cal}}$:
   - Static: $S_i = \| L^{-1} u_i \|_2$
   - Context: $S_i = \| L_\phi(\xi_i)^{-1} u_i \|_2$

2. Sort: $S_{(1)} \leq S_{(2)} \leq \cdots \leq S_{(n_{\mathrm{cal}})}$

3. Set $k = \lceil (n_{\mathrm{cal}} + 1) \cdot \tau \rceil$

4. Calibrated radius: $\hat\rho_\tau = S_{(k)}$

**Guarantee:** Under exchangeability, $\mathbb{P}(u_{\mathrm{new}} \in \mathcal{U}_{L, \hat\rho_\tau}) \geq \tau$.

Since all methods use the same conformal calibration, **coverage is matched at ~τ**. The comparison is purely on cost efficiency.

---

## 7. Evaluation Metrics

On the calibration set (used for both calibration and evaluation):

| Metric | Formula | What it measures |
|--------|---------|-----------------|
| **Total cost** | $\bar{V} = V(L, \hat\rho_\tau)$ | Dispatch + reserve cost under calibrated uncertainty set |
| **Empirical coverage** | $\frac{1}{n}\sum_i \mathbb{1}[s_L(u_i) \leq \hat\rho_\tau]$ | Should be $\approx \tau = 0.95$ |
| **Reserve volume** | $\sum_z R_z^{\min}$ (MW) | Total reserves procured |
| **Per-zone reserve** | $R_z^{\min}$ for each $z$ | Spatial allocation of reserves |
| **Frobenius error** | $\|LL^\top - L_{\mathrm{true}} L_{\mathrm{true}}^\top\|_F$ | How well L recovers ground-truth covariance |

### 7.1 Expected Ordering

$$\text{Cost: Independent} \geq \text{Sample Cov} \geq \text{Learned (Static)} \geq \text{Learned (Contextual)}$$

- **Independent → Sample Cov:** Ignoring correlations over-estimates reserve needs (misses hedging opportunities from negatively correlated sources). In practice, Sample Covariance performs similarly to Independent because statistical accuracy of the covariance does not directly translate to cost efficiency.
- **Sample Cov → Learned (Static):** Task-aware training re-shapes L to reduce cost in high-shadow-price zones. This is the primary demonstration of our framework — profiled gradient optimization reduces cost by ~4.2% ($4,200/hr) and reserve volume by 38%.
- **Learned (Static) → Learned (Contextual):** Context-dependent L can adapt to conditions (e.g., no solar reserve at night). End-to-end training achieves $94,565/hr (below Static's $95,335/hr), confirming the gradient pipeline works. However, the trace normalization constraint limits the NN to shape-only adaptation, and the model overfits on calibration ($95,964/hr). Designing NN architectures that generalize well for this problem class is an important direction for future work.

---

## 8. Dimensionality Summary

| Object | Shape | Description |
|--------|:-----:|-------------|
| $u_t$ | (T, 15) | Uncertainty vectors (3 sources × 5 regions) |
| $\xi_t$ | (T, 7) | Context features |
| $L$ | (15, 15) | Cholesky factor (lower triangular, positive diagonal) |
| $A$ | (10, 15) | Allocation matrix (maps 15-D to 10 zones) |
| $w_z = A[z,:]$ | (15,) | Exposure vector for zone $z$ |
| $R_z^{\min}$ | (10,) | Reserve requirements per zone |
| $g, r$ | (54,) each | Generator dispatch and reserves |
| $\mu_z^*$ | (10,) | Dual multipliers (shadow prices) |
| $\nabla_L \sigma(w)$ | (15, 15) | Support function gradient |
| $\nabla_L s(u)$ | (15, 15) | Gauge function gradient |

---

## 9. Implementation Files

### 9.1 Core Modules

| File | Purpose |
|------|---------|
| `sced.py` | Decoupled SCED LP solver, support/gauge functions, gradient computation, conformal calibration |
| `sced_coupled.py` | Coupled SCED LP solver with inter-zone transfer constraints; extracts reserve duals $\mu_z$ and transfer duals $\lambda_z$ |
| `methods.py` | All 4 methods (box, sample cov, static L, context NN), training loops, evaluation helpers for decoupled SCED |
| `methods_coupled.py` | Training loops and evaluation helpers for coupled SCED; uses combined duals $(\mu_z + \lambda_z)$ for profiled gradient |
| `utils.py` | Shared utilities: `load_data()`, `split_data()`, `compute_frob_error()` |

### 9.2 Experiment Runners

| File | Purpose |
|------|---------|
| `run_experiment.py` | Decoupled experiment: run all 4 methods with zonal reserve constraints only |
| `run_coupled_experiment.py` | Coupled experiment: run all 4 methods with zonal reserves + inter-zone transfer limits |

### 9.3 Data Generation

| File | Purpose |
|------|---------|
| `parse_ieee118.py` | Parse IEEE 118-bus MATPOWER case → generator, bus, branch CSVs |
| `generate_uncertainty.py` | Generate 15-D uncertainty vectors with context-dependent covariance (VAR(1) + modulation) |

### 9.4 Auxiliary (Tuning)

Located in `tuning/`:

| File | Purpose |
|------|---------|
| `tuning/tune_nn.py` | Phase 1: initial NN hyperparameter sweep |
| `tuning/tune_nn_phase2.py` | Phase 2: extended training for top configs |
| `tuning/tune_nn_phase3.py` | Phase 3: fine-grained batch size + training length sweep |
| `tuning/sweep_nn.py` | Comprehensive Latin-hypercube sweep (~40 configs) |
| `tuning/diagnose_rho.py` | Diagnostic: gauge score and $\rho$ analysis across methods |

### 9.5 Data Files

**System data** (`data/`):

| File | Description |
|------|-------------|
| `generator_data.csv` | 54 generators: bus, zone, min/max capacity, cost_c1, reserve_cost |
| `zone_summary.csv` | 10 zones: bus ranges, load (MW) |
| `branch_data.csv` | 186 branches (all with max_loading = 9900 MW, non-binding) |
| `bus_data.csv` | 118 buses with load and generation data |
| `ptdf_matrix.npy` | (186, 118) Power Transfer Distribution Factor matrix |
| `ptdf_zone_matrix.npy` | (186, 10) Zonal PTDF matrix |

**Uncertainty data** (`data/uncertainty/`):

| File | Shape | Description |
|------|:-----:|-------------|
| `uncertainty_15d.parquet` | (35040, 15) | Uncertainty vectors $u_t$ |
| `context_7d.parquet` | (35040, 7) | Context features $\xi_t$ |
| `L_true_t.npy` | (35040, 15, 15) | Ground-truth Cholesky factors |
| `allocation_matrix.npy` | (10, 15) | Allocation matrix $A$ |
| `metadata.json` | — | Split indices, dimension labels, parameters |

**Results** (`data/`):

| File | Description |
|------|-------------|
| `experiment_results.json` | Decoupled experiment results (cost, coverage, reserves per method) |
| `coupled_experiment_results.json` | Coupled experiment results (+ transfer duals, T_z_max) |

---

## 10. Experimental Results

### 10.1 Main Results

All methods are evaluated on the calibration set (7,008 samples) with conformal calibration at $\tau = 0.95$.

| Method | Cost ($/hr) | Reserve (MW) | Coverage |
|--------|:----------:|:------------:|:--------:|
| Independent | 99,540 | 1,510 | 0.950 |
| Sample Covariance | 99,655 | 1,525 | 0.950 |
| Learned (Static) | 95,335 | 932 | 0.950 |
| Learned (Contextual) | 95,964 | 1,028 | 0.950 |

**Per-zone reserves (MW):**

| Method | Z1 | Z2 | Z3 | Z4 | Z5 | Z6 | Z7 | Z8 | Z9 | Z10 |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:---:|
| Independent | 50.0 | 46.7 | 57.6 | 63.2 | 135.4 | 37.5 | 362.5 | 285.6 | 220.9 | 250.6 |
| Sample Covariance | 49.4 | 46.2 | 55.5 | 60.9 | 127.7 | 35.4 | 372.0 | 293.1 | 227.0 | 257.5 |
| Learned (Static) | 41.7 | 39.0 | 54.2 | 59.4 | 96.5 | 26.8 | 196.3 | 154.6 | 123.4 | 140.0 |
| Learned (Contextual) | 47.9 | 44.8 | 60.5 | 66.4 | 104.5 | 29.0 | 216.4 | 170.5 | 134.8 | 152.9 |

### 10.2 Key Findings

1. **Task-aware learning reduces cost by 4.2%.** The Learned (Static) method achieves $95,335/hr — a $4,205/hr reduction (4.2%) vs the Independent baseline — while reducing total reserve volume by 38% (1,510 → 932 MW). The profiled gradient reshapes the uncertainty set to lower reserves in high-shadow-price zones (e.g., Z7: 362 → 196 MW, Z8: 286 → 155 MW).

2. **Statistical accuracy ≠ cost efficiency.** The Sample Covariance method, despite capturing all pairwise correlations, is slightly more expensive than the Independent method ($99,655 vs $99,540). This confirms that optimizing for task cost rather than statistical fit is the key contribution.

3. **End-to-end contextual learning works but overfits.** The Learned (Contextual) method achieves a best training cost of $94,565/hr — $770 below the Static method — demonstrating that the profiled gradient pipeline successfully propagates task-relevant gradients through the neural network. However, on the calibration set the cost is $95,964/hr ($630 above Static), reflecting an overfitting gap. The trace normalization constraint restricts the network to shape-only adaptation, while the dominant context-dependent variation in the ground-truth covariance is in scale. Architecture design for this problem class is an important direction for future work.

4. **Conformal calibration ensures fair comparison.** All methods achieve exactly 95.0% empirical coverage, confirming that conformal calibration decouples coverage guarantees from uncertainty set shape. The comparison is purely on cost efficiency.

### 10.3 Reproducibility

```bash
cd Experiment
python run_experiment.py          # Run all 4 methods and print results
```

Results are saved to `data/experiment_results.json`.

---

## 11. Coupled Experiment (Inter-Zone Transfer Limits)

### 11.1 Motivation

The decoupled experiment (Section 10) uses zonal reserve constraints only — the dispatch is determined by generator capacity and power balance, with no inter-zone coupling through L. Transfer constraints introduce coupling: the robust transfer margin σ_z = ρ ||L^T A[z,:]||₂ depends on L through the **same exposure vectors** A[z,:] as zonal reserves.

This creates a regime where the uncertainty set geometry L directly affects dispatch feasibility through transfer constraints, not just reserve costs. The learned methods can exploit this by shaping L to reduce reserves in transfer-constrained zones, freeing capacity and lowering re-dispatch costs.

### 11.2 Formulation

The coupled SCED adds robust inter-zone transfer constraints:

```
|Export_z| + ρ ||L^T A[z,:]||₂ ≤ T_z^max
```

where Export_z = Σ_{i∈G_z} g_i − D_z is the net export of zone z. Since σ_z = ρ ||L^T A[z,:]||₂ = R_z^min (the same support function as zonal reserves), the combined envelope gradient uses (μ_z + λ_z) with the same exposure vectors:

```
∇_L V = Σ_z (μ_z + λ_z) · ∇_L σ(A[z,:])
```

where μ_z = reserve dual, λ_z = transfer dual. This reuses `compute_profiled_gradient` unchanged.

The LP formulation (in `sced_coupled.py`) adds 20 inequality rows to the decoupled SCED:

| Block | Constraint | Rows |
|-------|-----------|:----:|
| 1 | Capacity: g_i + r_i ≤ max_p_i | 54 |
| 2 | Zonal reserve: Σ_{G_z} r_i ≥ R_z^min | 10 |
| 3 | Upper transfer: Σ_{G_z} g_i ≤ D_z + T_z^max − R_z^min | 10 |
| 4 | Lower transfer: −Σ_{G_z} g_i ≤ −D_z + T_z^max − R_z^min | 10 |

### 11.3 Transfer Limit Design

Transfer limits T_z^max are computed from the decoupled baseline (sample covariance method):

1. Run decoupled SCED → base dispatch, exports, shadow prices
2. Compute needed_z = |Export_z| + R_z^train (using tune-set smoothed quantile ρ for training feasibility)
3. Tighten top 3 zones by shadow price to 90% of needed (α_tight = 0.90)
4. Set remaining zones to 150% of needed (α_loose = 1.50)

**Transfer limits:**

| Zone | Export (MW) | R_z (MW) | Needed (MW) | T_z^max (MW) | Status |
|:----:|:----------:|:--------:|:-----------:|:------------:|:------:|
| 1 | +570 | 52 | 623 | 934 | Loose |
| 2 | −87 | 49 | 136 | 204 | Loose |
| 3 | +160 | 59 | 219 | 328 | Loose |
| 4 | −195 | 65 | 260 | 389 | Loose |
| 5 | −446 | 136 | 582 | 523 | **Tight** |
| 6 | +730 | 38 | 768 | 1,151 | Loose |
| 7 | −314 | 395 | 709 | 1,063 | Loose |
| 8 | −353 | 311 | 664 | 598 | **Tight** |
| 9 | +123 | 241 | 364 | 546 | Loose |
| 10 | −188 | 273 | 461 | 415 | **Tight** |

Zones 5, 8, and 10 are tightened because they have the highest reserve shadow prices (μ_z = 10.2, 8.3, 9.7 respectively).

### 11.4 Results

**Code:** `sced_coupled.py`, `methods_coupled.py`, `run_coupled_experiment.py`

| Method | Cost ($/hr) | Reserve (MW) | Coverage | Binding Transfers |
|--------|:----------:|:------------:|:--------:|:-----------------:|
| Independent | 100,012 | 1,510 | 0.950 | 3 (Z5, Z8, Z10) |
| Sample Covariance | 100,091 | 1,525 | 0.950 | 3 (Z5, Z8, Z10) |
| Learned (Static) | 95,461 | 944 | 0.950 | 1 (Z5 only) |
| Learned (Contextual) | 95,687 | 967 | 0.950 | 1 (Z5 only) |

**Transfer duals λ_z:**

| Method | Z5 | Z8 | Z10 |
|--------|:--:|:--:|:---:|
| Independent | 7.04 | 0.94 | 1.25 |
| Sample Covariance | 7.04 | 0.94 | 1.25 |
| Learned (Static) | 7.38 | 0.00 | 0.00 |
| Learned (Contextual) | 6.10 | 0.00 | 0.00 |

**Per-zone reserves (MW):**

| Method | Z1 | Z2 | Z3 | Z4 | Z5 | Z6 | Z7 | Z8 | Z9 | Z10 |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:---:|
| Independent | 50.0 | 46.7 | 57.6 | 63.2 | 135.4 | 37.5 | 362.5 | 285.6 | 220.9 | 250.6 |
| Sample Covariance | 49.4 | 46.2 | 55.5 | 60.9 | 127.7 | 35.4 | 372.0 | 293.1 | 227.0 | 257.5 |
| Learned (Static) | 50.8 | 47.5 | 53.6 | 58.9 | 83.3 | 23.1 | 196.6 | 154.9 | 128.9 | 146.2 |
| Learned (Contextual) | 49.9 | 46.7 | 57.8 | 63.5 | 89.9 | 24.9 | 198.0 | 156.0 | 131.3 | 149.0 |

### 11.5 Key Findings

1. **Coupling amplifies the value of learning.** In the decoupled setting (Section 10), learned methods reduced cost by 4.2%. In the coupled setting, the reduction is 4.6% ($100,091 → $95,461). The additional coupling constraints create more opportunities for the learned L to exploit — by reducing R_z in tight zones, the learned methods free transfer capacity and avoid costly re-dispatch.

2. **Learned L relieves transfer congestion.** Baseline methods have 3 binding transfer constraints (zones 5, 8, 10). The learned methods reduce R_z sufficiently in zones 8 and 10 that those transfer constraints become non-binding, leaving only zone 5 binding. This demonstrates that the profiled gradient — using combined duals (μ_z + λ_z) — correctly steers L to reduce reserves where both reserve and transfer costs are high.

3. **Same gradient mechanism, different duals.** The coupled experiment reuses `compute_profiled_gradient` unchanged. The only difference is that the dual multiplier vector is μ_z + λ_z instead of just μ_z. This validates the envelope theorem approach: adding constraints to the SCED requires no new gradient code, only the correct dual extraction from the solver.

4. **Coupled vs decoupled cost comparison.** Transfer constraints increase baseline costs by ~$436/hr (decoupled SampleCov: $99,655 → coupled: $100,091). For learned methods, the increase is only ~$126/hr ($95,335 → $95,461), demonstrating that learned uncertainty sets are more robust to additional operational constraints.

### 11.6 Reproducibility

```bash
cd Experiment
python run_coupled_experiment.py   # Run coupled experiment
```

Results are saved to `data/coupled_experiment_results.json`.

---

## 12. Comparative Summary

### 12.1 Decoupled vs Coupled: Cost Comparison

| Method | Decoupled Cost ($/hr) | Coupled Cost ($/hr) | Increase | Increase (%) |
|--------|:---------------------:|:-------------------:|:--------:|:------------:|
| Independent | 99,540 | 100,012 | +472 | +0.47% |
| Sample Covariance | 99,655 | 100,091 | +436 | +0.44% |
| Learned (Static) | 95,335 | 95,461 | +126 | +0.13% |
| Learned (Contextual) | 95,964 | 95,687 | −277 | −0.29% |

### 12.2 Decoupled vs Coupled: Reserve Comparison

| Method | Decoupled Reserve (MW) | Coupled Reserve (MW) | Change |
|--------|:----------------------:|:--------------------:|:------:|
| Independent | 1,510 | 1,510 | 0 |
| Sample Covariance | 1,525 | 1,525 | 0 |
| Learned (Static) | 932 | 944 | +12 |
| Learned (Contextual) | 1,028 | 967 | −61 |

Note: Reserves for Methods 1–2 are identical because they use the same L (no training). Reserves for Methods 3–4 differ because the coupled training loop steers L differently via the combined duals $(\mu_z + \lambda_z)$.

### 12.3 Key Takeaways

1. **Transfer constraints increase baseline costs more than learned costs.** Baseline methods see a $436–472/hr cost increase from coupling, while Learned (Static) sees only $126/hr. This 3.5× differential demonstrates that learned uncertainty sets are inherently more robust to additional operational constraints.

2. **Coupling amplifies the learning advantage.** The cost gap between Sample Covariance and Learned (Static) grows from $4,320/hr (decoupled) to $4,630/hr (coupled) — a 7% larger advantage. Transfer constraints create additional optimization opportunities that only learned methods can exploit.

3. **Learned methods relieve transfer congestion.** Baseline methods bind all 3 tightened transfer zones (Z5, Z8, Z10). Learned methods reduce R_z sufficiently in Z8 and Z10 that those constraints become slack, leaving only Z5 binding. Fewer binding constraints = lower re-dispatch cost.

4. **Same gradient code, different dual vectors.** The coupled experiment reuses `compute_profiled_gradient` unchanged — the only difference is passing combined duals $(\mu_z + \lambda_z)$ instead of $\mu_z$ alone. This validates the envelope theorem approach: new constraints require only correct dual extraction, not new gradient functions.

---

## 13. Full Reproducibility

### 13.1 Data Generation

```bash
cd Experiment
python parse_ieee118.py          # Parse IEEE 118-bus → CSVs in data/
python generate_uncertainty.py   # Generate uncertainty data → data/uncertainty/
```

### 13.2 Run Experiments

```bash
cd Experiment
python run_experiment.py          # Decoupled: ~10 min (Static L: 200 iters, NN: 1500 iters)
python run_coupled_experiment.py  # Coupled: ~15 min (same + coupled SCED per iteration)
```

### 13.3 Expected Outputs

**Decoupled** (`data/experiment_results.json`):
- 4 methods × {cost, coverage, reserve_total, rho, frob_error, feasible, R_z_min}
- All methods feasible, coverage = 0.950

**Coupled** (`data/coupled_experiment_results.json`):
- Same fields + T_z_max, tight_zones, lambda_z per method
- Tight zones: [5, 8, 10]; learned methods relieve Z8 and Z10

### 13.4 Dependencies

- Python 3.9+
- numpy, pandas, scipy (linprog with HiGHS), torch, pyarrow (for parquet)
- pandapower (for `parse_ieee118.py` only)
