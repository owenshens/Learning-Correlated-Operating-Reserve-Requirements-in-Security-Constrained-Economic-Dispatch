# Experiment Package

This directory contains the code, processed data artifacts, and saved outputs used for the numerical results reported in the preprint.

## Overview

The experiments compare four ellipsoidal uncertainty-set methods under a common SCED model and conformal calibration procedure:

- `Independent`
- `Sample Covariance`
- `Learned (Static)`
- `Learned (Contextual)`

In the codebase, the `Independent` baseline is implemented as `box_method` and may appear as `Box` in saved JSON outputs.

## Data and Saved Artifacts

The `data/` directory includes the inputs and outputs required to reproduce the reported results:

- benchmark system data such as `generator_data.csv`, `zone_summary.csv`, and `branch_data.csv`
- generated uncertainty and context data in `data/uncertainty/`
- saved trained models in `data/models/`
- saved experiment summaries including `experiment_results.json`, `coupled_experiment_results.json`, and `tau_sweep_results.json`

The saved JSON outputs are the sources for the main quantitative tables in the preprint. The largest artifact is `data/uncertainty/L_true_t.npy`, which stores the per-hour benchmark Cholesky factors used in the study.

## Main Scripts

- `generate_uncertainty.py`
  - generates the synthetic uncertainty and context dataset together with supporting metadata
- `run_experiment.py`
  - runs the decoupled zonal reserve comparison
- `run_coupled_experiment.py`
  - runs the coupled experiment with transfer constraints
- `run_tau_sweep.py`
  - evaluates cost and coverage across multiple target levels with the shape fixed at the `tau = 0.95` training point
- `run_block_bootstrap.py`
  - computes block-bootstrap confidence intervals for the decoupled experiment
- `run_block_bootstrap_coupled.py`
  - computes block-bootstrap confidence intervals for the coupled experiment

## Reproducing the Results

From this directory:

```bash
pip install -r requirements.txt
python run_experiment.py
python run_coupled_experiment.py
python run_tau_sweep.py
python run_block_bootstrap.py
python run_block_bootstrap_coupled.py
```

Outputs are written to `data/`.

## Dependencies

The core experiment scripts rely on:

- `numpy`
- `pandas`
- `scipy`
- `pyarrow`
- `torch`

`pandapower` is only needed for `parse_ieee118.py`, which reparses the IEEE test case and is not required to rerun the released experiments.
