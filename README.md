# Learning Correlated Operating Reserve Requirements

This repository contains the public release for the experiments and preprint accompanying the paper:

*Learning Correlated Operating Reserve Requirements in Security-Constrained Economic Dispatch*

The release is organized around:

- `Experiment/`: code, data, and saved outputs for the experiments reported in the paper.
- `Paper/preprint.tex` and `Paper/reference.bib`: the public paper artifacts.

This release is intentionally narrow. Development notes, presentation assets, and unreleased paper drafts are excluded from the tracked public repository.

## Repository Layout

- `README.md`
  - release overview and reproduction entry point
- `CITATION.cff`
  - citation metadata for GitHub and downstream citation tools
- `Experiment/`
  - reproducibility package for the reported experiments
- `Paper/preprint.tex`
  - GitHub-facing LaTeX source of the current preprint
- `Paper/reference.bib`
  - bibliography used by the preprint

## What Is Included

The `Experiment/` package reproduces the main quantitative results in the preprint:

- decoupled zonal reserve experiment
- coupled experiment with transfer constraints
- cost--coverage tradeoff sweep
- bootstrap confidence intervals

The experiment bundle already includes the generated uncertainty data and saved model artifacts needed to reproduce the reported tables. The large raw-data directory used during development is intentionally excluded from version control.

The saved outputs in `Experiment/data/experiment_results.json`, `Experiment/data/coupled_experiment_results.json`, and `Experiment/data/tau_sweep_results.json` match the main tables reported in the preprint.

## Quick Start

1. Create a Python environment and install the experiment dependencies:

```bash
cd Experiment
pip install -r requirements.txt
```

2. Run the main paper-facing scripts:

```bash
python run_experiment.py
python run_coupled_experiment.py
python run_tau_sweep.py
python run_block_bootstrap.py
python run_block_bootstrap_coupled.py
```

3. Find outputs in `Experiment/data/`.

## Script-to-Paper Mapping

- `Experiment/run_experiment.py`: decoupled zonal reserves comparison
- `Experiment/run_coupled_experiment.py`: coupled SCED with transfer constraints
- `Experiment/run_tau_sweep.py`: cost--coverage tradeoff across target levels
- `Experiment/run_block_bootstrap.py`: confidence intervals for the decoupled experiment
- `Experiment/run_block_bootstrap_coupled.py`: confidence intervals for the coupled experiment
- `Experiment/generate_uncertainty.py`: synthetic uncertainty generation calibrated to real data

## Naming Notes

Some internal code names predate the final paper wording:

- `Box` in code/results corresponds to the `Independent` baseline in the preprint.
- `NN_L` in saved outputs corresponds to `Learned (Contextual)` in the preprint.

The public documentation uses the paper terminology throughout.

## Paper Files

The public paper files included in Git are:

- `Paper/preprint.tex`
- `Paper/reference.bib`

The raw working manuscript file `Paper/Preprint` is intentionally kept out of the Git release.

## Release Notes

- The repository remote is configured for the public GitHub target:
  - `https://github.com/owenshens/Learning-Correlated-Operating-Reserve-Requirements-in-Security-Constrained-Economic-Dispatch.git`
- The current branch is `main`.
- Binary experiment artifacts are marked in `.gitattributes` to keep the Git presentation cleaner.
