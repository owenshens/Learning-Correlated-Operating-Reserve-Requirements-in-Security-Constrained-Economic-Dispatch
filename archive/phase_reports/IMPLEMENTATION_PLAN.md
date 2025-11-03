# Comprehensive Implementation Plan for Experimental Suite

## Executive Summary

This plan outlines the systematic implementation of 23 experiments across 9 categories for validating the robust energy dispatch methodology. Total estimated time: **100 computational hours** over **12 weeks**.

---

## I. Folder Structure and Organization

```
experiment/
├── IMPLEMENTATION_PLAN.md          # This file
├── README.md                        # Quick start guide
├── requirements.txt                 # Python dependencies
├── config/                          # Configuration files
│   ├── hardware_config.yaml        # Hardware specs, solver settings
│   ├── experiment_config.yaml      # Default parameters for all experiments
│   └── ieee_systems/               # IEEE test system data
│       ├── ieee14.json
│       ├── ieee30.json
│       └── ieee118.json
├── core/                            # Core infrastructure (Phase 1)
│   ├── __init__.py
│   ├── problem_generator.py        # Generate synthetic problems
│   ├── uncertainty_sets.py         # All uncertainty set implementations
│   ├── solvers.py                  # DRPG, PRDA, baseline solvers
│   ├── metrics.py                  # Metric computation utilities
│   └── ieee_loader.py              # Load IEEE test systems
├── utils/                           # Utilities (Phase 1)
│   ├── __init__.py
│   ├── logging_utils.py            # Experiment logging and tracking
│   ├── result_storage.py           # Save/load results (JSON/HDF5)
│   ├── statistical_tests.py        # T-tests, Cohen's d, etc.
│   └── math_utils.py               # Projections, gradients, etc.
├── visualization/                   # Visualization suite (Phase 7)
│   ├── __init__.py
│   ├── convergence_plots.py        # Category II plots
│   ├── network_plots.py            # Power system network diagrams
│   ├── economic_plots.py           # Pareto curves, cost distributions
│   ├── uncertainty_plots.py        # Trajectory plots, set overlays
│   └── style_config.py             # Nature/Science style settings
├── experiments/                     # Experiment implementations
│   ├── category_I_theoretical/     # Theoretical validation
│   │   ├── exp_I1_envelope_verification.py
│   │   ├── exp_I2_dual_equivalence.py
│   │   └── exp_I3_subdifferential.py
│   ├── category_II_convergence/    # Convergence rates
│   │   ├── exp_II1_drpg_convergence.py
│   │   └── exp_II2_prda_convergence.py
│   ├── category_III_scalability/   # Scalability & benchmarks
│   │   ├── exp_III1_problem_scaling.py
│   │   └── exp_III2_benchmark_comparison.py
│   ├── category_IV_case_studies/   # Realistic case studies
│   │   ├── exp_IV1_ieee_systems.py
│   │   ├── exp_IV2_regional_stress.py
│   │   └── exp_IV3_rolling_horizon.py
│   ├── category_V_economic/        # Economic insights
│   │   ├── exp_V1_pareto_frontier.py
│   │   ├── exp_V2_price_volatility.py
│   │   └── exp_V3_investment_signals.py
│   ├── category_VI_uncertainty/    # Uncertainty set geometry
│   │   ├── exp_VI1_uncertainty_comparison.py
│   │   └── exp_VI2_renewable_calibration.py
│   ├── category_VII_sensitivity/   # Sensitivity analysis
│   │   ├── exp_VII1_radius_sensitivity.py
│   │   ├── exp_VII2_pca_reduction.py
│   │   └── exp_VII3_hyperparameter_tuning.py
│   └── category_IX_reproducibility/ # Reproducibility
│       ├── exp_IX1_statistical_tests.py
│       └── exp_IX2_perturbation_robustness.py
├── results/                         # Experiment results
│   ├── category_I/
│   ├── category_II/
│   ├── ...
│   └── summary/                    # Aggregate results
├── figures/                         # Generated figures
│   ├── category_I/
│   ├── category_II/
│   ├── ...
│   └── paper_ready/                # Final publication figures
├── tables/                          # Generated LaTeX tables
│   └── all_tables.tex              # Compiled tables for paper
├── notebooks/                       # Jupyter notebooks for exploration
│   ├── quick_start.ipynb
│   ├── experiment_I1_demo.ipynb
│   └── visualization_gallery.ipynb
├── tests/                           # Unit tests
│   ├── test_solvers.py
│   ├── test_uncertainty_sets.py
│   └── test_metrics.py
└── scripts/                         # High-level orchestration
    ├── run_all_experiments.py      # Master script
    ├── run_category.py             # Run one category
    ├── generate_paper_figures.py   # Generate all figures
    └── compile_results.py          # Aggregate results to tables
```

---

## II. Implementation Phases (12 Weeks)

### **Phase 0: Infrastructure Setup (Week 1, Days 1-2)**

**Priority: CRITICAL** - Everything depends on this.

#### Deliverables:
1. ✅ Folder structure created
2. ✅ Core infrastructure modules
3. ✅ Configuration system
4. ✅ Logging and result storage
5. ✅ Unit tests for core components

#### Tasks:
```
Day 1:
- Create folder structure
- Set up requirements.txt with all dependencies
- Implement core/problem_generator.py (synthetic QP generation)
- Implement core/uncertainty_sets.py (L2Ball, L1Ball, LinfBox, TVBudget, TopK, Ellipsoid)
- Write unit tests for uncertainty sets (projections, linear oracles)

Day 2:
- Implement core/solvers.py:
  * DirectNominalSolver (from double_uncertainty_nominal.py)
  * CompositionalDoubleUncertaintyOptimizer (DRPG)
  * PRDA solver
- Implement utils/logging_utils.py
- Implement utils/result_storage.py (JSON + HDF5)
- Set up config/experiment_config.yaml with default parameters
- Create README.md with quick start guide
```

#### Success Criteria:
- [ ] Can generate synthetic problems programmatically
- [ ] All uncertainty set projections pass unit tests
- [ ] Can run a simple DRPG instance and save results
- [ ] Logging system captures iteration history

---

### **Phase 1: Critical Validation (Week 1 Day 3 - Week 2)**

**Priority: CRITICAL** - Core theoretical claims must be validated first.

#### Category I: Theoretical Validation

**Experiment I.1: Envelope Theorem Verification** (Day 3-4)

```python
# experiments/category_I_theoretical/exp_I1_envelope_verification.py

Objective: Verify ∇_u V(u) = P^T μ*(u) numerically

Steps:
1. Generate 3 problem sizes (small, medium, large)
2. For each problem and 4 uncertainty sets (L2, L1, Linf, TV):
   a. Sample 10 test points (interior, boundary, vertex, random)
   b. Compute analytical gradient: g_env = P^T μ*(u)
   c. Compute finite-difference gradient: g_FD
   d. Compute relative error, cosine similarity
   e. Store results
3. Generate Table I.1 (summary statistics)
4. Generate Figures I.1-I.3 (scatter, histogram, heatmap)

Expected Runtime: 2 hours
Priority: CRITICAL
Dependencies: core.solvers, core.uncertainty_sets
```

**Experiment I.2: Dual Penalty Equivalence** (Day 5-6)

```python
# experiments/category_I_theoretical/exp_I2_dual_equivalence.py

Objective: Verify primal robust counterpart = dual penalty formulation

Steps:
1. Generate 3 problem sizes
2. For each problem and uncertainty set:
   a. Solve primal robust counterpart via CVXPY (SOCP reformulation)
   b. Solve dual penalty via PRDA
   c. Recover primal from dual
   d. Compare objective values, primal decisions, dual prices
3. Generate Table I.2, Figures I.4-I.5

Expected Runtime: 4 hours
Priority: CRITICAL
Dependencies: core.solvers (need PRDA), CVXPY
```

**Experiment I.3: Subdifferential Validation** (Day 7)

```python
# experiments/category_I_theoretical/exp_I3_subdifferential.py

Objective: Verify subdifferential inclusion at non-smooth points

Steps:
1. Generate problem with intentional degeneracy
2. Find multiple optimal dual solutions M*(u)
3. Compute convex hull of {P^T μ : μ ∈ M*(u)}
4. Compute FD subgradients; check inclusion
5. Generate Figure I.6, Table I.3

Expected Runtime: 1 hour
Priority: MEDIUM
Dependencies: core.solvers, convex hull computation
```

#### Category II: Convergence Rate Verification

**Experiment II.1: DRPG Convergence** (Week 2, Day 1-2)

```python
# experiments/category_II_convergence/exp_II1_drpg_convergence.py

Objective: Verify O(1/√K) convergence rate for DRPG

Steps:
1. Run DRPG with K=1000 outer iterations
2. Track: V^(k), gradient mapping norm, distance to stationary set
3. Log-log plots: fit slope (should be ~-0.5)
4. Sensitivity to stepsizes α ∈ {0.5, 0.6, 0.8, 1.0}
5. Generate Figures II.1-II.3, Table II.1

Expected Runtime: 3 hours
Priority: CRITICAL
Dependencies: core.solvers.DRPG with full logging
```

**Experiment II.2: PRDA Convergence** (Week 2, Day 3-4)

```python
# experiments/category_II_convergence/exp_II2_prda_convergence.py

Objective: Verify O(1/√K) for non-smooth, O(1/K) for smooth PRDA

Steps:
1. Implement smooth penalty variant (Moreau envelope)
2. Run both variants with K=2000 iterations
3. Track dual objective gap Φ* - Φ^(k)
4. Log-log plots: compare slopes
5. Generate Figures II.4-II.5, Table II.2

Expected Runtime: 3 hours
Priority: CRITICAL
Dependencies: core.solvers.PRDA with smoothing option
```

**Week 2 Checkpoint:**
- [ ] Envelope theorem validated (relative error < 10^-4)
- [ ] Dual equivalence confirmed (obj gap < 0.1%)
- [ ] DRPG and PRDA convergence rates verified
- [ ] 8 figures and 5 tables generated
- [ ] Results stored in results/category_I/ and results/category_II/

---

### **Phase 2: Scalability & Performance (Week 3-4)**

**Priority: CRITICAL** - Demonstrates practical applicability.

#### Category III: Scalability and Performance

**Experiment III.1: Problem Size Scaling** (Week 3, Day 1-3)

```python
# experiments/category_III_scalability/exp_III1_problem_scaling.py

Objective: Characterize scaling with N, n_i, m

Steps:
1. Experiment A: Vary N ∈ {10, 25, 50, 100, 200, 500, 1000}, fix n_i=20, m=10
   - For each N: run DRPG, measure time, memory, iterations
2. Experiment B: Vary n_i ∈ {10, 20, 30, 50}, fix N=50, m=20
3. Experiment C: Vary m ∈ {5, 10, 20, 30, 50}, fix N=100, n_i=30
4. Log-log plots: fit power-law exponents
5. Generate Figures III.1-III.3, Table III.1

Expected Runtime: 8 hours (some large instances)
Priority: CRITICAL
Dependencies: core.problem_generator, memory profiler
```

**Experiment III.2: Benchmark Comparison** (Week 3 Day 4 - Week 4 Day 2)

```python
# experiments/category_III_scalability/exp_III2_benchmark_comparison.py

Objective: Compare DRPG/PRDA vs. CVXPY, CCG, AARO

Steps:
1. Implement baselines:
   a. Monolithic CVXPY (SOCP reformulation)
   b. Column-and-Constraint Generation (CCG)
   c. Affinely Adjustable RO (AARO) - SDP reformulation
2. For problem sizes (small, medium, large, very large):
   a. Run all methods with 1-hour timeout
   b. Record: solve time, objective, iterations, memory
3. Generate Table III.2, Figures III.4-III.6

Expected Runtime: 6 hours
Priority: CRITICAL
Dependencies: CVXPY, implement CCG and AARO
```

**Week 3-4 Checkpoint:**
- [ ] Scalability up to N=1000 demonstrated (within 1 hour)
- [ ] 10-100x speedup over monolithic methods confirmed
- [ ] Benchmark table completed
- [ ] 6 figures and 2 tables generated

---

### **Phase 3: Realistic Case Studies (Week 5-6)**

**Priority: CRITICAL** - Industry relevance and practical impact.

#### Category IV: Realistic Energy Systems

**Experiment IV.1: IEEE Test Systems** (Week 5, Day 1-3)

```python
# experiments/category_IV_case_studies/exp_IV1_ieee_systems.py

Objective: Demonstrate on IEEE 14/30/118-bus systems

Prerequisites:
- Download IEEE test system data from PandaPower or MATPOWER
- Convert to our problem format (generators, lines, buses)
- Add realistic costs, storage, renewables

Steps:
1. Extend IEEE systems:
   - Add quadratic costs, ramp rates
   - Place batteries (1 per 10 buses)
   - Add renewables (20%, 40%, 60% penetration scenarios)
2. For each system and penetration level:
   a. Solve nominal (ρ=0)
   b. Run DRPG to find worst-case u*
   c. Run PRDA for protective dispatch
   d. Monte Carlo validation (1000 samples)
3. Compute metrics: PoR, price volatility, envelope gradients
4. Generate Figures IV.1-IV.4, Table IV.1

Expected Runtime: 12 hours
Priority: CRITICAL
Dependencies: core.ieee_loader, pandapower or matpower data
```

**Experiment IV.2: Regional Grid Stress Tests** (Week 5 Day 4 - Week 6 Day 2)

```python
# experiments/category_IV_case_studies/exp_IV2_regional_stress.py

Objective: Stylized California, Texas, New England systems

Steps:
1. Create stylized regions:
   - California: 50 buses, 30% solar, duck curve
   - Texas: 70 buses, 30% wind, Top-K uncertainty
   - New England: 40 buses, 20% offshore wind, ellipsoid
2. Define stress scenarios (historical events):
   - CA: heat wave + solar ramp-down
   - TX: winter freeze
   - NE: polar vortex
3. For each region:
   a. Run DRPG: find worst-case
   b. Compare to historical u_hist
   c. Run PRDA: protective dispatch
   d. Measure load shedding reduction
4. Generate Figures IV.5-IV.7, Table IV.2

Expected Runtime: 10 hours
Priority: HIGH
Dependencies: Regional topology data (can be synthetic)
```

**Experiment IV.3: Multi-Day Rolling Horizon** (Week 6, Day 3-4)

```python
# experiments/category_IV_case_studies/exp_IV3_rolling_horizon.py

Objective: 7-day operational simulation with rolling dispatch

Steps:
1. Setup: IEEE 30-bus, 40% renewables, 168 hours
2. Generate realized uncertainty path (AR(1) with seasonal pattern)
3. For each day d ∈ {0, 1, ..., 6}:
   a. Solve robust dispatch for hours 24d to 24(d+1)
   b. Execute dispatch with realized u_real
   c. Update battery SOC, generator states
   d. Update uncertainty set calibration
4. Compare nominal vs. robust rolling dispatch:
   - Cumulative cost
   - Storage cycling
   - Price volatility
5. Generate Figures IV.8-IV.10, Table IV.3

Expected Runtime: 8 hours
Priority: HIGH
Dependencies: Time-series simulation framework
```

**Week 5-6 Checkpoint:**
- [ ] IEEE systems solved (14, 30, 118-bus)
- [ ] Regional stress tests completed
- [ ] 7-day rolling horizon simulation done
- [ ] Price of Robustness ~5-15% confirmed
- [ ] 10 figures and 3 tables generated

---

### **Phase 4: Economic Insights (Week 7-8)**

**Priority: HIGH** - Key value proposition for Management Science audience.

#### Category V: Economic Analysis

**Experiment V.1: Pareto Frontier** (Week 7, Day 1-2)

```python
# experiments/category_V_economic/exp_V1_pareto_frontier.py

Objective: Trace welfare-volatility tradeoff as ρ varies

Steps:
1. Setup: IEEE 30-bus, 24-hour, 40% renewables
2. For ρ ∈ {0, 0.5, 1, 2, 3, 5, 7, 10, 15, 20}:
   a. Solve PRDA to get μ*(ρ)
   b. Recover primal x*(ρ)
   c. Compute: V_nom(ρ), V_worst(ρ), ||P^T μ||
3. Plot Pareto curves:
   - Cost vs. volatility
   - PoR vs. worst-case gap
4. Identify knee point ρ* (L-curve criterion)
5. Repeat for 20%, 40%, 60% penetration
6. Generate Figures V.1-V.3, Table V.1

Expected Runtime: 4 hours
Priority: HIGH
Dependencies: L-curve optimization for knee detection
```

**Experiment V.2: Price Volatility Analysis** (Week 7, Day 3-4)

```python
# experiments/category_V_economic/exp_V2_price_volatility.py

Objective: Quantify LMP volatility reduction

Steps:
1. Setup: IEEE 30-bus, 24 hours, nominal vs. robust (ρ=5)
2. Compute volatility metrics:
   - Temporal: std_t(μ_n,t) for each node n
   - Spatial: std_n(μ_n,t) for each hour t
   - Price range, spike count
3. Economic implications:
   - Generator revenue risk (variance over MC samples)
   - Consumer bill risk
   - Congestion rent
4. Generate Figures V.4-V.7, Table V.2

Expected Runtime: 3 hours
Priority: HIGH
Dependencies: Monte Carlo sampling framework
```

**Experiment V.3: Investment Signals** (Week 8, Day 1-2)

```python
# experiments/category_V_economic/exp_V3_investment_signals.py

Objective: Use envelope gradient for infrastructure siting

Steps:
1. Solve nominal dispatch, compute g = P^T μ
2. Identify nodes with highest |g_n|
3. Test interventions:
   a. Add 50 MW generator at high-|g_n| node
   b. Add 20 MW / 40 MWh battery
   c. Increase line capacity by 20 MW
4. For each intervention:
   - Re-solve robust dispatch
   - Measure ΔV (cost reduction)
   - Measure Δ||g|| (vulnerability reduction)
5. Correlation analysis: |g_n| vs. ΔV
6. Generate Figures V.8-V.10, Table V.3

Expected Runtime: 3 hours
Priority: HIGH
Dependencies: Parametric system modification
```

**Week 7-8 Checkpoint:**
- [ ] Pareto frontier traced for multiple penetration levels
- [ ] Price volatility reduction ~25-40% demonstrated
- [ ] Investment signal correlation validated
- [ ] 10 figures and 3 tables generated

---

### **Phase 5: Uncertainty Geometry & Sensitivity (Week 9-10)**

**Priority: MEDIUM/HIGH** - Methodological depth.

#### Category VI: Uncertainty Set Geometry

**Experiment VI.1: Uncertainty Set Comparison** (Week 9, Day 1-2)

```python
# experiments/category_VI_uncertainty/exp_VI1_uncertainty_comparison.py

Objective: Compare L2, L1, Linf, TV, TopK, Ellipsoid, Hybrid sets

Steps:
1. Calibrate all sets to equivalent "effective radius"
2. For each set:
   a. Run DRPG to find u*
   b. Run PRDA to solve protective dual
   c. Measure: V(u*), σ_U(P^T μ), sparsity, smoothness
   d. Measure: DRPG iters, projection oracle time
3. Analyze realism: does u* look plausible?
4. Generate Table VI.1, Figures VI.1-VI.3

Expected Runtime: 6 hours
Priority: MEDIUM
Dependencies: All uncertainty set classes
```

**Experiment VI.2: Renewable Calibration** (Week 9 Day 3 - Week 10 Day 1)

```python
# experiments/category_VI_uncertainty/exp_VI2_renewable_calibration.py

Objective: Fit uncertainty sets to historical renewable data

Steps:
1. Download NREL wind/solar data (or use synthetic proxy):
   - WIND Toolkit or NSRDB
   - 1 year of hourly data (8760 samples)
2. Compute forecast errors e_t = actual - forecast
3. For each uncertainty set, fit parameters:
   - L2: ρ = 95th percentile of ||u_t||_2
   - TV: Γ = 95th percentile of total variation
   - Ellipsoid: Σ from sample covariance
4. Validation:
   - Coverage on test set (should be ~95%)
   - V(u*) vs. 99th percentile of V(u_t)
5. Generate Figures VI.4-VI.7, Table VI.2

Expected Runtime: 4 hours
Priority: HIGH
Dependencies: NREL data or synthetic AR(1) generator
```

#### Category VII: Sensitivity Analysis

**Experiment VII.1: Radius Sensitivity** (Week 10, Day 2)

```python
# experiments/category_VII_sensitivity/exp_VII1_radius_sensitivity.py

Objective: Systematically vary ρ and analyze effects

Steps:
1. For ρ ∈ {0, 0.5, 1, 2, 3, 5, 7, 10, 15, 20}:
   a. Solve PRDA
   b. Compute: PoR, worst-case gap, ||P^T μ||, storage util
2. Identify phase transitions (where behavior changes)
3. Compute marginal PoR: d(PoR)/dρ
4. Cross-validation: find optimal ρ minimizing realized cost
5. Generate Figures VII.1-VII.3, Table VII.1

Expected Runtime: 3 hours
Priority: MEDIUM
Dependencies: Historical data for cross-validation
```

**Experiment VII.2: PCA Dimension Reduction** (Week 10, Day 3)

```python
# experiments/category_VII_sensitivity/exp_VII2_pca_reduction.py

Objective: Trade-off between d and solution quality

Steps:
1. Full uncertainty: 720 factors (30 buses × 24 hours)
2. PCA: extract top d ∈ {2, 5, 10, 20, 50, 100}
3. For each d:
   a. Reconstruct u = U_d z
   b. Run DRPG in reduced space
   c. Measure: explained variance, V(u*), solve time
4. Find optimal d (captures 80-85% variance, tractable time)
5. Generate Figures VII.4-VII.6, Table VII.2

Expected Runtime: 2 hours
Priority: MEDIUM
Dependencies: sklearn PCA or custom implementation
```

**Experiment VII.3: Hyperparameter Tuning** (Week 10, Day 4)

```python
# experiments/category_VII_sensitivity/exp_VII3_hyperparameter_tuning.py

Objective: Characterize sensitivity to algorithm hyperparameters

Steps:
1. Grid search over:
   - Outer stepsize: η_0 ∈ {0.5, 1.0, 2.0}, α ∈ {0.3, 0.5, 0.7, 1.0}
   - Inner tolerance: ε_inner ∈ {1e-2, 1e-3, 1e-4}
   - Warm-start: on/off
   - Outer tolerance: ε_outer ∈ {1e-3, 1e-4, 1e-5}
2. For each config:
   - Run DRPG, measure total time, iters, V(u*)
3. Identify best configuration
4. Generate Figures VII.7-VII.9, Table VII.3

Expected Runtime: 4 hours
Priority: LOW
Dependencies: Hyperparameter grid search framework
```

**Week 9-10 Checkpoint:**
- [ ] Uncertainty set comparison completed
- [ ] Realistic calibration validated (95% coverage)
- [ ] Sensitivity analysis done
- [ ] 9 figures and 3 tables generated

---

### **Phase 6: Reproducibility & Final Polishing (Week 11-12)**

**Priority: CRITICAL** - Essential for peer review.

#### Category IX: Reproducibility

**Experiment IX.1: Statistical Significance** (Week 11, Day 1)

```python
# experiments/category_IX_reproducibility/exp_IX1_statistical_tests.py

Objective: Ensure reported improvements are statistically significant

Steps:
1. For key comparisons (DRPG vs. CCG, nominal vs. robust):
   - Run with 10 different random seeds
   - Collect metrics: solve time, objective, iterations
2. Perform:
   - Paired t-test (p-value)
   - Wilcoxon signed-rank test
   - Cohen's d (effect size)
3. Generate Table IX.1, Figure IX.1 (box plots)

Expected Runtime: 2 hours
Priority: MEDIUM
Dependencies: scipy.stats
```

**Experiment IX.2: Perturbation Robustness** (Week 11, Day 2)

```python
# experiments/category_IX_reproducibility/exp_IX2_perturbation_robustness.py

Objective: Test robustness to problem perturbations

Steps:
1. Perturbations: cost (10%), capacity (5%), demand (2%), topology (remove lines)
2. For each perturbation type:
   - Generate 10 perturbed instances
   - Run DRPG and PRDA
   - Measure: convergence, PoR, sensitivity index
3. Generate Table IX.2, Figure IX.2

Expected Runtime: 3 hours
Priority: MEDIUM
Dependencies: Problem perturbation utilities
```

**Experiment IX.3: Code & Data Archiving** (Week 11 Day 3 - Day 4)

```
Tasks:
1. Clean up code:
   - Remove debug prints
   - Add docstrings to all functions
   - Type hints for all function signatures
2. Write comprehensive README.md
3. Create requirements.txt (pinned versions)
4. Generate API documentation (Sphinx)
5. Create Jupyter notebook tutorials
6. Prepare Zenodo archive:
   - Precomputed results (JSON)
   - IEEE system data
   - Synthetic historical proxy data
7. Set up GitHub repo (if public)
8. Create Docker container (optional)

Expected Time: 8 hours
Priority: CRITICAL
```

#### Phase 7: Visualization & Paper Preparation (Week 12)

**Experiment VIII: Visualization Suite** (Week 12, Day 1-3)

```python
# All in visualization/ module

Tasks:
1. Generate all ~40 figures:
   - Apply Nature/Science style (visualization/style_config.py)
   - 300 DPI, colorblind-friendly palette
   - Clear labels, legends, grid
2. Compile all ~25 tables (LaTeX format)
3. Create figure_gallery.pdf (all figures in one document)
4. Quality check:
   - Readable at 80mm column width
   - Consistent style across all figures
   - No overlapping labels

Expected Time: 3 days
Priority: CRITICAL for paper submission
```

**Final Compilation** (Week 12, Day 4-5)

```
Tasks:
1. Run scripts/compile_results.py:
   - Aggregate all experiment results
   - Generate summary statistics
   - Create master result spreadsheet
2. Generate paper appendix:
   - All tables in LaTeX
   - Supplementary figures
   - Algorithm pseudocode
3. Final checks:
   - All experiments completed
   - All figures generated
   - All tables compiled
   - GitHub repo ready
   - Zenodo archive prepared
4. Write executive summary report

Expected Time: 2 days
```

**Week 11-12 Checkpoint:**
- [ ] Statistical tests completed (all p < 0.05)
- [ ] Perturbation robustness validated
- [ ] Code cleaned and documented
- [ ] All 40 figures generated
- [ ] All 25 tables compiled
- [ ] GitHub repo ready
- [ ] Ready for journal submission

---

## III. Priority Matrix

### Must-Have (Critical Path)

| Experiment | Priority | Time | Blocking |
|------------|----------|------|----------|
| Infrastructure (Phase 0) | P0 | 2 days | ALL |
| I.1 Envelope Verification | P0 | 2 hours | Paper validity |
| I.2 Dual Equivalence | P0 | 4 hours | Paper validity |
| II.1 DRPG Convergence | P0 | 3 hours | Algorithm claims |
| II.2 PRDA Convergence | P0 | 3 hours | Algorithm claims |
| III.1 Scalability | P0 | 8 hours | Practical applicability |
| III.2 Benchmarks | P0 | 6 hours | Competitive analysis |
| IV.1 IEEE Systems | P0 | 12 hours | Industry relevance |
| IX.3 Code Archiving | P0 | 8 hours | Reproducibility |
| VIII Visualization | P0 | 3 days | Paper submission |

### Should-Have (High Value)

| Experiment | Priority | Time | Value |
|------------|----------|------|-------|
| IV.2 Regional Stress | P1 | 10 hours | Practical impact |
| IV.3 Rolling Horizon | P1 | 8 hours | Operational realism |
| V.1 Pareto Frontier | P1 | 4 hours | Economic insight |
| V.2 Price Volatility | P1 | 3 hours | Market design |
| V.3 Investment Signals | P1 | 3 hours | Policy relevance |
| VI.2 Renewable Calibration | P1 | 4 hours | Data-driven validation |

### Nice-to-Have (Enhancing)

| Experiment | Priority | Time | Benefit |
|------------|----------|------|---------|
| I.3 Subdifferential | P2 | 1 hour | Theoretical depth |
| VI.1 Uncertainty Comparison | P2 | 6 hours | Methodological insight |
| VII.1-3 Sensitivity | P2 | 9 hours | Robustness analysis |
| IX.1-2 Statistical Tests | P2 | 5 hours | Rigor |

---

## IV. Dependencies and Blockers

### Critical Dependencies

```
Phase 0 (Infrastructure) → ALL experiments
    ├── core.solvers → Exp I.1, I.2, II.1, II.2, ALL
    ├── core.uncertainty_sets → Exp I.1, VI.1, VI.2
    ├── core.problem_generator → Exp I, II, III, V, VI, VII
    └── utils.result_storage → ALL

Exp I.1, I.2 (Theoretical Validation) → Paper acceptance
Exp II.1, II.2 (Convergence) → Algorithm credibility
Exp III.2 (Benchmarks) → Need Exp III.1 (baseline timings)
Exp IV.1 (IEEE) → Need core.ieee_loader
Exp VI.2 (Calibration) → Need historical data or synthetic proxy
Exp VIII (Visualization) → Need ALL experiments completed
```

### External Dependencies

```
Software:
- CVXPY ≥ 1.4 (baseline comparisons)
- MOSEK or Gurobi academic license (fast QP/SOCP)
- PandaPower or MATPOWER (IEEE systems)
- NREL data access (or synthetic proxy generator)

Hardware:
- 16-core CPU, 64 GB RAM (for large-scale experiments)
- ~10 GB disk space (results + figures)

Data:
- IEEE test systems (publicly available)
- Historical renewable forecast errors (NREL or synthetic)
```

---

## V. Execution Strategy

### Parallel Execution Opportunities

```
Week 1-2 (Can parallelize):
├── Thread 1: Exp I.1, I.2 (Theoretical) → 6 hours
└── Thread 2: Exp II.1, II.2 (Convergence) → 6 hours
    └── Both can run independently after Phase 0

Week 3-4 (Sequential required):
└── Exp III.1 → Exp III.2 (need baseline for comparison)

Week 5-6 (Can parallelize):
├── Thread 1: IV.1 (IEEE 14, 30) → 8 hours
├── Thread 2: IV.1 (IEEE 118) → 4 hours
└── Thread 3: IV.2 (Regional) → 10 hours
    └── IV.3 sequential after IV.1 or IV.2

Week 7-8 (Can parallelize):
├── Thread 1: V.1 (Pareto)
├── Thread 2: V.2 (Volatility)
└── Thread 3: V.3 (Investment)
    └── All independent

Week 9-10 (Can parallelize):
├── Thread 1: VI.1, VI.2
└── Thread 2: VII.1, VII.2, VII.3

Week 11-12 (Sequential):
└── IX, VIII (need all results first)
```

### Continuous Integration

```python
# scripts/run_all_experiments.py

import logging
from experiments.category_I_theoretical import exp_I1, exp_I2, exp_I3
# ... import all

def main():
    logger = logging.getLogger("experiment_suite")

    # Phase 0: Check infrastructure
    assert_infrastructure_ready()

    # Phase 1: Critical validation
    results = {}
    results['I.1'] = exp_I1.run()
    assert results['I.1']['max_rel_error'] < 1e-4, "Envelope theorem failed!"

    results['I.2'] = exp_I2.run()
    assert results['I.2']['obj_gap'] < 0.001, "Dual equivalence failed!"

    # ... continue for all experiments

    # Generate summary report
    compile_results(results)
    generate_all_figures(results)

    logger.info("All experiments completed successfully!")
```

---

## VI. Quality Assurance Checklist

### For Each Experiment:

- [ ] **Code Quality**
  - [ ] Unit tests written and passing
  - [ ] Type hints on all functions
  - [ ] Docstrings (NumPy style)
  - [ ] No hardcoded paths
  - [ ] Random seed set for reproducibility

- [ ] **Results**
  - [ ] Saved to results/{category}/exp_{ID}.json
  - [ ] Includes metadata (timestamp, config, hardware)
  - [ ] Includes all raw data (not just summaries)
  - [ ] Backup to HDF5 for large arrays

- [ ] **Figures**
  - [ ] Saved to figures/{category}/fig_{ID}.pdf (vector)
  - [ ] Also PNG at 300 DPI (for preview)
  - [ ] Style consistent with style_config.py
  - [ ] Axes labeled with units
  - [ ] Legend present and readable

- [ ] **Tables**
  - [ ] LaTeX source in tables/{category}/table_{ID}.tex
  - [ ] Also CSV for programmatic access
  - [ ] Caption describes content
  - [ ] Numbers formatted with appropriate precision

- [ ] **Documentation**
  - [ ] README section updated
  - [ ] Jupyter notebook example created
  - [ ] Results interpretation written

---

## VII. Risk Mitigation

### Potential Blockers and Solutions

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| CVXPY solver failure on large instances | High | Medium | Use MOSEK/Gurobi; implement timeout; report partial results |
| NREL data unavailable | Medium | Low | Use synthetic AR(1) proxy with same stats |
| Memory overflow (N=1000) | Medium | High | Implement sparse matrices; batch processing; cloud compute |
| DRPG doesn't converge | Low | Critical | Diagnose: check Lipschitz constant, try smaller stepsize, increase K_max |
| Results don't match theory | Low | Critical | Debug thoroughly; check implementation against paper equations; verify on toy problem |
| Time overrun (>100 hours) | Medium | Medium | Prioritize P0 experiments; reduce problem sizes; extend timeline |

### Contingency Plan

If timeline slips:
1. **Week 10:** Re-prioritize
   - Drop P2 experiments (I.3, VII.3)
   - Reduce problem sizes for P1 experiments
   - Focus on P0 critical path
2. **Week 11:** Emergency mode
   - Run P0 experiments only
   - Generate essential figures (10-15 instead of 40)
   - Minimal reproducibility (code + README, skip Docker)
3. **Week 12:** Triage
   - Core results + 1-2 case studies
   - Essential benchmarks only
   - Defer sensitivity analysis to appendix or future work

---

## VIII. Success Metrics

### Quantitative Goals

- [ ] **Theoretical Validation**
  - Envelope theorem: relative error < 10^-4 (99% of test points)
  - Dual equivalence: objective gap < 0.1%
  - Convergence rate slopes: within ±0.1 of theory

- [ ] **Performance**
  - Scalability: solve N=1000 within 1 hour
  - Speedup: 10-100x vs monolithic (confirmed)
  - Memory: < 10 GB for largest instance

- [ ] **Economic Impact**
  - Price of Robustness: 5-15% (reasonable hedging cost)
  - Volatility reduction: 25-40%
  - Load shedding: reduced by 50-100% under stress

- [ ] **Reproducibility**
  - All experiments run with ≥10 seeds
  - Statistical significance: p < 0.05 for all key claims
  - Code runs on fresh install (verified)

### Qualitative Goals

- [ ] **Clarity**
  - Every figure has self-explanatory caption
  - Every table has clear column headers
  - All results interpretable by non-expert

- [ ] **Completeness**
  - All 9 categories addressed
  - All critical experiments (P0) completed
  - No missing figures or tables in paper

- [ ] **Impact**
  - Results compelling for Management Science reviewers
  - Demonstrates clear value to energy system operators
  - Code accessible to practitioners

---

## IX. Post-Implementation Checklist

Before paper submission:

- [ ] **Code Repository**
  - [ ] All code committed to GitHub
  - [ ] README.md complete with installation, usage, examples
  - [ ] requirements.txt / environment.yml with pinned versions
  - [ ] LICENSE file (e.g., Apache 2.0)
  - [ ] .gitignore properly configured
  - [ ] Unit tests pass (pytest)
  - [ ] Continuous integration setup (GitHub Actions, optional)

- [ ] **Data Archive (Zenodo)**
  - [ ] IEEE test system files
  - [ ] Synthetic renewable proxy data
  - [ ] Precomputed experiment results (JSON/HDF5)
  - [ ] DOI obtained

- [ ] **Documentation**
  - [ ] Sphinx API docs generated (HTML)
  - [ ] 3-5 Jupyter tutorial notebooks
  - [ ] Video walkthrough (optional, 10 min)

- [ ] **Paper Materials**
  - [ ] All figures in figures/paper_ready/ (PDF, 300 DPI)
  - [ ] All tables in tables/all_tables.tex
  - [ ] Supplementary material compiled (appendix)
  - [ ] Code availability statement written
  - [ ] Data availability statement written

- [ ] **Validation**
  - [ ] Run scripts/run_all_experiments.py on fresh machine
  - [ ] Verify all results reproducible (within ±1% due to solver differences)
  - [ ] Verify all figures regenerate correctly
  - [ ] Third-party code review (if possible)

---

## X. Contact and Collaboration

**Primary Investigator:** [Your Name]
**Timeline:** 12 weeks (flexible)
**Compute Resources:** 16-core CPU, 64 GB RAM
**Collaboration:** Open to feedback on experiment design before execution

**Questions or suggestions?** Please comment on this plan before implementation begins.

---

**END OF IMPLEMENTATION PLAN**

**Estimated total compute time:** ~100 hours
**Estimated researcher time:** 12 weeks (1 FTE)
**Expected deliverables:** 40+ figures, 25+ tables, open-source codebase, Zenodo archive

**Ready to proceed?** Please review and approve this plan before execution begins.
