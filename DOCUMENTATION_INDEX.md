# Documentation Index

This index helps navigate the complete documentation for the DRPG experimental validation project.

## Core Documentation (Root Directory)

### Essential Reading
- **[README.md](README.md)** - Main project overview, installation, and usage instructions
- **[FINAL_SESSION_REPORT.md](FINAL_SESSION_REPORT.md)** - Comprehensive 31KB summary of all validation work
- **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)** - Quick high-level overview of results and findings
- **[ARTIFACTS_MANIFEST.md](ARTIFACTS_MANIFEST.md)** - Complete inventory of experimental artifacts

## Experimental Results

### Main Results Directory: `experiments/`
- **`category_IV_comparison/`** - 81-problem comprehensive validation
  - `results/method_comparison_results.json` - Raw results (179KB)
  - `results/method_comparison_summary.csv` - Summary statistics

- **`comprehensive_figures/`** - Publication-ready figures
  - `figure_1_computational_comparison.pdf/png` - Method comparison (2 panels)
  - `figure_2_scalability_analysis.pdf/png` - Scalability study (3 panels)
  - `figure_3_robustness_distribution.pdf/png` - PoR distribution
  - `figure_4_success_rates.pdf/png` - Convergence reliability

### IEEE Validation: `results/ieee_experiments/`
- **`ieee_case118_results.json`** - IEEE case118 benchmark results
- **`figures/`** - IEEE-specific visualizations
  - `ieee_case118_comparison.pdf/png` - Method comparison
  - `ieee_case118_drpg_convergence.pdf/png` - Convergence analysis
  - `ieee_case118_summary_table.pdf/png` - Results summary table

## Source Code

### Core Algorithms: `core/`
- **`solvers.py`** - DRPG implementation (envelope theorem, adversarial search)
- **`baseline_solvers.py`** - Nominal, Scenario, Budgeted methods
- **`ieee_problem_generator.py`** - IEEE test case integration
- **`uncertainty_sets.py`** - L2Ball, LInfBall, Budget uncertainty sets
- **`robust_qp_problem.py`** - Problem data structure

### Experimental Scripts
- **`run_ieee_case118_experiment.py`** - IEEE case118 validation
- **`generate_comprehensive_figures.py`** - Figure generation from results
- **`test_ieee_generator.py`** - IEEE generator validation tests

## Archived Documentation: `archive/session_reports/`

Historical working documents from development process:
- `PHASE5_PLAN.md` - Initial experimental design
- `COMPREHENSIVE_DESIGN_REPORT.md` - Detailed experiment architecture
- `CRITICAL_REVIEW_UNCERTAINTY_SCALING.md` - Bug discovery and analysis
- `EXPERIMENTAL_REDESIGN_ACTION_PLAN.md` - Correction strategy
- `FINAL_VALIDATION_CORRECTED_RESULTS.md` - Post-fix validation
- `PUBLICATION_READY_ANALYSIS.md` - Results interpretation
- And 6 other interim analysis documents

## Key Findings

### Critical Bug Fix
**Uncertainty Scaling**: Fixed from absolute (constant 0.2) to relative (15% of coefficients)
- **Impact**: PoR increased from 0.138% to 1.07% (realistic)
- **Location**: `core/synthetic_problem_generator.py:134-144`

### Main Results
1. **Computational Trade-off**:
   - Simple coupling (1 constraint): DRPG 5.1× faster than Scenario
   - Complex coupling (5 constraints): DRPG 8.9× slower than Scenario

2. **Robustness Performance**:
   - Mean Price of Robustness: 1.07% (synthetic), 2.70% (IEEE)
   - DRPG success rate: 97.5% (79/81 problems)

3. **IEEE Validation**:
   - case118: 53 generators, 3 iterations, 0.048s solve time
   - Confirms DRPG works on real power system benchmarks

## Quick Navigation

**For reviewers**: Start with [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) → [FINAL_SESSION_REPORT.md](FINAL_SESSION_REPORT.md)

**For implementation**: See `core/solvers.py` and [README.md](README.md) installation section

**For experimental details**: See `experiments/` directory and [ARTIFACTS_MANIFEST.md](ARTIFACTS_MANIFEST.md)

**For historical context**: See `archive/session_reports/` for development chronology

---

*Last updated: 2025-11-02*
*Total artifacts: 22 figure pairs, 16 JSON files, 9 CSV files*
*Repository: git@github.com:owenshens/Energy-Project.git*
