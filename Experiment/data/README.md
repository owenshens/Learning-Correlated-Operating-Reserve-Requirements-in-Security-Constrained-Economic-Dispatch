# Data Bundle

This directory contains the processed data and saved outputs required to reproduce the results reported in the preprint.

## Layout

- `uncertainty/`
  - generated uncertainty samples, context features, metadata, and ground-truth covariance/Cholesky artifacts
- `models/`
  - saved trained static and contextual models used by the paper-facing scripts
- top-level `*.json`
  - saved summary outputs for the main experiments, sweeps, and confidence intervals
- top-level benchmark files
  - IEEE 118-bus derived system inputs such as generator, zone, bus, and branch data

## Key Files

- `experiment_results.json`
  - main decoupled comparison reported in the preprint
- `coupled_experiment_results.json`
  - coupled transfer-constrained comparison
- `tau_sweep_results.json`
  - cost--coverage tradeoff sweep
- `block_bootstrap_ci.json`
  - decoupled confidence intervals
- `block_bootstrap_coupled_ci.json`
  - coupled confidence intervals
- `uncertainty/metadata.json`
  - dimension labels, split indices, and generation settings

## Size Note

The largest artifact in this directory is:

- `uncertainty/L_true_t.npy`

It is included as part of the benchmark dataset used to evaluate recovery of the underlying uncertainty geometry.
