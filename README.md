# Learning Correlated Operating Reserve Requirements in Security-Constrained Economic Dispatch

This repository accompanies the preprint *Learning Correlated Operating Reserve Requirements in Security-Constrained Economic Dispatch*. It contains the experiment package used for the reported numerical results together with the LaTeX source of the manuscript.

## Repository Structure

- `Experiment/`
  - reproducibility package for the numerical experiments
- `Paper/preprint.tex`
  - LaTeX source of the preprint
- `Paper/reference.bib`
  - bibliography used by the manuscript
- `CITATION.cff`
  - citation metadata for the repository

## Included Results

The experiment package covers the principal results reported in the paper:

- decoupled zonal reserve experiment
- coupled SCED experiment with transfer constraints
- cost-coverage tradeoff sweep across target levels
- block-bootstrap confidence intervals

The processed data artifacts and saved model outputs required to reproduce these results are included in `Experiment/data/`. In particular, the saved outputs in `Experiment/data/experiment_results.json`, `Experiment/data/coupled_experiment_results.json`, and `Experiment/data/tau_sweep_results.json` correspond to the main tables reported in the preprint.

## Quick Start

From `Experiment/`:

```bash
pip install -r requirements.txt
python run_experiment.py
python run_coupled_experiment.py
python run_tau_sweep.py
python run_block_bootstrap.py
python run_block_bootstrap_coupled.py
```

Generated outputs are written to `Experiment/data/`.

## Script Guide

- `Experiment/run_experiment.py`
  - decoupled zonal reserve comparison
- `Experiment/run_coupled_experiment.py`
  - coupled SCED with transfer constraints
- `Experiment/run_tau_sweep.py`
  - cost-coverage tradeoff across target levels
- `Experiment/run_block_bootstrap.py`
  - confidence intervals for the decoupled experiment
- `Experiment/run_block_bootstrap_coupled.py`
  - confidence intervals for the coupled experiment
- `Experiment/generate_uncertainty.py`
  - synthetic uncertainty generation calibrated to real data

## Naming Conventions

Some variable names in the code predate the final manuscript terminology:

- `Box` corresponds to the `Independent` baseline in the paper
- `NN_L` corresponds to `Learned (Contextual)`

The README files and manuscript use the paper terminology throughout.

## Citation

If you use this repository, please cite the paper metadata provided in `CITATION.cff`.
