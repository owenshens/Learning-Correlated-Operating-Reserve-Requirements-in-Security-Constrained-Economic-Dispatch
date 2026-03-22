# Experiment Package

This directory contains the experiment code and data bundle used for the results reported in the preprint.

## Scope

The paper compares four ellipsoidal uncertainty-set methods under the same SCED model and the same conformal calibration procedure:

- `Independent`
- `Sample Covariance`
- `Learned (Static)`
- `Learned (Contextual)`

In the legacy code, the `Independent` baseline is implemented by `box_method` and often appears as `Box` in saved JSON outputs.

## Data Bundle

The `data/` directory already includes the generated inputs and saved outputs needed to reproduce the paper results:

- benchmark system data (`generator_data.csv`, `zone_summary.csv`, `branch_data.csv`)
- generated uncertainty and context data (`data/uncertainty/`)
- saved trained models (`data/models/`)
- saved experiment outputs (`experiment_results.json`, `coupled_experiment_results.json`, `tau_sweep_results.json`)

The heaviest artifact is `data/uncertainty/L_true_t.npy`, which stores the per-hour ground-truth Cholesky factors used for benchmarking.

The excluded `raw_data/` directory is not needed to rerun the paper-facing scripts.
The saved JSON outputs are the ones used to populate the preprint tables.

## Main Scripts

- `generate_uncertainty.py`
  - Generates the synthetic uncertainty/context dataset and supporting metadata.
- `run_experiment.py`
  - Runs the decoupled zonal reserve comparison for the four methods.
- `run_coupled_experiment.py`
  - Runs the coupled experiment with transfer constraints.
- `run_tau_sweep.py`
  - Evaluates cost and coverage across multiple target levels with shape fixed at the `tau = 0.95` training point.
- `run_block_bootstrap.py`
  - Computes block-bootstrap confidence intervals for the decoupled experiment.
- `run_block_bootstrap_coupled.py`
  - Computes block-bootstrap confidence intervals for the coupled experiment.

## Reproducing the Paper Results

From this directory:

```bash
pip install -r requirements.txt
python run_experiment.py
python run_coupled_experiment.py
python run_tau_sweep.py
python run_block_bootstrap.py
python run_block_bootstrap_coupled.py
```

Saved outputs will appear in `data/`.

## Dependencies

The core experiment scripts rely on:

- `numpy`
- `pandas`
- `scipy`
- `pyarrow` for Parquet I/O through pandas
- `torch`

`pandapower` is only needed for `parse_ieee118.py`, which reparses the IEEE test case and is not required for rerunning the released experiments.

## Release Scope

This directory is intended to be the public reproducibility package for the paper. Development-only notes are kept out of the tracked release; this README is the authoritative guide for the released workflow and file set.
