"""
Generate 15-dimensional uncertainty data with context-dependent covariance
for the IEEE 118-bus robust SCED experiment.

Combines real data from two sources:
  - Germany OPSD: source-type correlations (load/solar/wind), AR(1), variance profiles
  - US Multi-ISO: spatial correlations (5 BAs), AR(1)

Produces:
  - Context vector xi_t (forecasts + cyclical time features) at each hour
  - Uncertainty vector u_t from a VAR(1) process with context-dependent L(xi)
  - Ground-truth L_true(xi_t) for each time step (what the NN must recover)

See uncertainty_generation.md for full methodology.
"""

import numpy as np
import pandas as pd
import os
import json

BASE_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE_DIR, "raw_data")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "uncertainty")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 15-D dimension labels: 3 sources x 5 regions
SOURCES = ["load", "solar", "wind"]
REGIONS = ["R1", "R2", "R3", "R4", "R5"]
DIM_LABELS = [f"{s}_{r}" for s in SOURCES for r in REGIONS]

# Context feature labels
CONTEXT_LABELS = [
    "load_fc", "solar_fc", "wind_fc",
    "hour_sin", "hour_cos", "month_sin", "month_cos",
]

# IEEE 118-bus zone structure
ZONE_LOADS_MW = {1: 365, 2: 341, 3: 360, 4: 395, 5: 801, 6: 222, 7: 575, 8: 453, 9: 342, 10: 388}

# Meta-region grouping: 10 zones -> 5 meta-regions
REGION_ZONES = {
    "R1": [1, 2],
    "R2": [3, 4],
    "R3": [5, 6],
    "R4": [7, 8],
    "R5": [9, 10],
}

# Concentrated renewable capacity assignment (Option 2)
# Solar: zones 3-6 (R2, R3); Wind: zones 7-10 (R4, R5)
SOLAR_ZONES = {3, 4, 5, 6}
WIND_ZONES = {7, 8, 9, 10}

SOLAR_REGIONS = {"R2", "R3"}
WIND_REGIONS = {"R4", "R5"}

# Germany total system load for computing error fraction
GERMANY_TOTAL_LOAD_MW = 80_000


# ===========================================================================
# Data fitting
# ===========================================================================

def fit_source_correlation():
    """Extract source-type correlation, AR(1) coefficients, and variance profiles from Germany OPSD."""
    df = pd.read_parquet(os.path.join(RAW_DIR, "germany_opsd", "germany_processed.parquet"))
    error_cols = ["load_error", "solar_error", "wind_error"]

    R_source = df[error_cols].corr().values
    ar_coeffs = {col: df[col].autocorr(lag=1) for col in error_cols}
    sigma_fracs = {col: df[col].std() / GERMANY_TOTAL_LOAD_MW for col in error_cols}

    # Forecast statistics for generating synthetic forecasts
    forecast_stats = {}
    for source in ["load", "solar", "wind"]:
        fc_col = f"{source}_forecast"
        forecast_stats[source] = {
            "mean": float(df[fc_col].mean()),
            "std": float(df[fc_col].std()),
            "p25": float(df[fc_col].quantile(0.25)),
            "p50": float(df[fc_col].quantile(0.50)),
            "p75": float(df[fc_col].quantile(0.75)),
        }

    return {
        "R_source": R_source,
        "ar_coeffs": {"load": ar_coeffs["load_error"],
                      "solar": ar_coeffs["solar_error"],
                      "wind": ar_coeffs["wind_error"]},
        "sigma_fracs": {"load": sigma_fracs["load_error"],
                        "solar": sigma_fracs["solar_error"],
                        "wind": sigma_fracs["wind_error"]},
        "forecast_stats": forecast_stats,
    }


def fit_region_correlation():
    """Extract spatial correlation and AR(1) coefficients from Multi-ISO data."""
    df = pd.read_parquet(os.path.join(RAW_DIR, "multi_iso", "eia_forecast_errors",
                                      "multi_ba_forecast_errors_clean.parquet"))
    error_cols = ["CISO_error", "ERCO_error", "PJM_error", "MISO_error", "NYIS_error"]

    R_region = df[error_cols].corr().values

    ar_coeffs = {}
    ba_to_region = {"CISO": "R1", "ERCO": "R2", "PJM": "R3", "MISO": "R4", "NYIS": "R5"}
    for col in error_cols:
        ba = col.replace("_error", "")
        ar_coeffs[ba_to_region[ba]] = df[col].autocorr(lag=1)

    return {"R_region": R_region, "ar_coeffs": ar_coeffs}


# ===========================================================================
# Static structure
# ===========================================================================

def compute_region_loads():
    """Compute meta-region total loads from zone loads."""
    return {region: sum(ZONE_LOADS_MW[z] for z in zones)
            for region, zones in REGION_ZONES.items()}


def build_marginal_sigmas(sigma_fracs, region_loads):
    """Compute base marginal standard deviations for all 15 dimensions."""
    sigmas = np.zeros(15)
    for s_idx, source in enumerate(SOURCES):
        frac = sigma_fracs[source]
        for r_idx, region in enumerate(REGIONS):
            sigmas[s_idx * 5 + r_idx] = frac * region_loads[region]
    return sigmas


def build_ar_coefficients(source_ar, region_ar):
    """Build 15-D AR(1) coefficient vector (geometric mean of source and region)."""
    phi = np.zeros(15)
    for s_idx, source in enumerate(SOURCES):
        for r_idx, region in enumerate(REGIONS):
            phi[s_idx * 5 + r_idx] = np.sqrt(source_ar[source] * region_ar[region])
    return phi


def build_allocation_matrix():
    """Build the 10x15 allocation matrix mapping 15-D uncertainty to 10 zonal injections."""
    A = np.zeros((10, 15))
    for r_idx, (region, zones) in enumerate(REGION_ZONES.items()):
        region_load = sum(ZONE_LOADS_MW[z] for z in zones)
        for z in zones:
            z_idx = z - 1
            A[z_idx, 0 * 5 + r_idx] = ZONE_LOADS_MW[z] / region_load  # load

            if z in SOLAR_ZONES:
                solar_zones_in_region = [zz for zz in zones if zz in SOLAR_ZONES]
                if solar_zones_in_region:
                    solar_total = sum(ZONE_LOADS_MW[zz] for zz in solar_zones_in_region)
                    A[z_idx, 1 * 5 + r_idx] = ZONE_LOADS_MW[z] / solar_total

            if z in WIND_ZONES:
                wind_zones_in_region = [zz for zz in zones if zz in WIND_ZONES]
                if wind_zones_in_region:
                    wind_total = sum(ZONE_LOADS_MW[zz] for zz in wind_zones_in_region)
                    A[z_idx, 2 * 5 + r_idx] = ZONE_LOADS_MW[z] / wind_total
    return A


# ===========================================================================
# Forecast generation (context features)
# ===========================================================================

def generate_forecasts(timestamps, region_loads, rng):
    """Generate synthetic forecast time series for each region.

    Returns:
        forecasts: dict with keys 'load', 'solar', 'wind', each (T, 5) array
        context: (T, 7) array of normalized context features
    """
    T = len(timestamps)
    hours = np.array([t.hour for t in timestamps])
    months = np.array([t.month for t in timestamps])
    dow = np.array([t.dayofweek for t in timestamps])

    region_load_arr = np.array([region_loads[r] for r in REGIONS])  # (5,)

    # --- Load forecast ---
    # Diurnal shape: peaks at 9am and 7pm, trough at 3am
    diurnal = (0.4 * np.sin(np.pi * (hours - 3) / 12) +
               0.15 * np.sin(2 * np.pi * (hours - 5) / 24))
    seasonal = 0.10 * np.cos(2 * np.pi * (months - 1) / 12)  # winter peak
    weekend = -0.05 * (dow >= 5).astype(float)
    noise_load = np.zeros(T)
    for t in range(1, T):
        noise_load[t] = 0.95 * noise_load[t - 1] + 0.02 * rng.standard_normal()
    load_factor = 1 + diurnal + seasonal + weekend + noise_load  # ~[0.4, 1.7]
    load_fc = np.outer(load_factor, region_load_arr)  # (T, 5)

    # --- Solar forecast ---
    # Zero at night, peaks midday, seasonal amplitude
    sun_angle = np.clip(np.sin(np.pi * (hours - 6) / 12), 0, None)  # 0 at night
    seasonal_solar = 1 + 0.3 * np.sin(2 * np.pi * (months - 3) / 12)  # summer peak
    # Cloud noise: AR(1) with moderate persistence
    noise_solar = np.zeros(T)
    for t in range(1, T):
        noise_solar[t] = 0.90 * noise_solar[t - 1] + 0.15 * rng.standard_normal()
    solar_raw = sun_angle * seasonal_solar * np.exp(noise_solar)
    # Solar only in R2, R3; capacity proportional to region load
    solar_capacity = np.zeros(5)
    for r_idx, region in enumerate(REGIONS):
        if region in SOLAR_REGIONS:
            solar_capacity[r_idx] = region_load_arr[r_idx] * 0.3  # 30% solar penetration
    solar_fc = np.outer(solar_raw, solar_capacity)  # (T, 5)

    # --- Wind forecast ---
    # Persistent weather-driven process, seasonal
    seasonal_wind = 1 + 0.15 * np.sin(2 * np.pi * (months - 12) / 12)  # winter peak
    noise_wind = np.zeros(T)
    for t in range(1, T):
        noise_wind[t] = 0.98 * noise_wind[t - 1] + 0.10 * rng.standard_normal()
    wind_factor = 0.30 * seasonal_wind * np.exp(noise_wind)  # ~[0.1, 0.8] capacity factor
    # Wind only in R4, R5
    wind_capacity = np.zeros(5)
    for r_idx, region in enumerate(REGIONS):
        if region in WIND_REGIONS:
            wind_capacity[r_idx] = region_load_arr[r_idx] * 0.4  # 40% wind penetration
    wind_fc = np.outer(wind_factor, wind_capacity)  # (T, 5)

    forecasts = {"load": load_fc, "solar": solar_fc, "wind": wind_fc}

    # Build 7-D context vector: (load_fc_norm, solar_fc_norm, wind_fc_norm, sin/cos hour, sin/cos month)
    # Aggregate across regions to get system-level forecast indicators
    load_fc_agg = load_fc.sum(axis=1)
    solar_fc_agg = solar_fc.sum(axis=1)
    wind_fc_agg = wind_fc.sum(axis=1)

    # Normalize to zero mean, unit variance
    def normalize(x):
        return (x - x.mean()) / (x.std() + 1e-8)

    context = np.column_stack([
        normalize(load_fc_agg),
        normalize(solar_fc_agg),
        normalize(wind_fc_agg),
        np.sin(2 * np.pi * hours / 24),
        np.cos(2 * np.pi * hours / 24),
        np.sin(2 * np.pi * months / 12),
        np.cos(2 * np.pi * months / 12),
    ])  # (T, 7)

    return forecasts, context


# ===========================================================================
# Context-dependent covariance
# ===========================================================================

def compute_context_sigmas(sigmas_base, forecasts, region_loads):
    """Compute context-dependent std devs for each time step.

    Args:
        sigmas_base: (15,) base marginal std devs
        forecasts: dict with 'load', 'solar', 'wind' each (T, 5)
        region_loads: dict

    Returns:
        sigmas_t: (T, 15) context-dependent std devs
    """
    T = forecasts["load"].shape[0]
    sigmas_t = np.tile(sigmas_base, (T, 1))  # (T, 15), start with base

    region_load_arr = np.array([region_loads[r] for r in REGIONS])

    # Load scaling: moderate dependence, ±40-70% around base
    # load_fc / mean_load_fc → scale factor
    load_fc_mean = forecasts["load"].mean(axis=0, keepdims=True)  # (1, 5)
    load_scale = 0.6 + 0.4 * (forecasts["load"] / (load_fc_mean + 1e-8))  # (T, 5)
    load_scale = np.clip(load_scale, 0.3, 1.8)
    for r_idx in range(5):
        sigmas_t[:, 0 * 5 + r_idx] *= load_scale[:, r_idx]

    # Solar scaling: very strong dependence (near zero at night, proportional to forecast)
    # Normalize by 75th percentile of non-zero solar
    for r_idx, region in enumerate(REGIONS):
        solar_col = forecasts["solar"][:, r_idx]
        if region in SOLAR_REGIONS:
            nonzero = solar_col[solar_col > 0]
            p75 = np.percentile(nonzero, 75) if len(nonzero) > 0 else 1.0
            solar_scale = np.clip(solar_col / p75, 0.01, 3.0)
        else:
            solar_scale = np.ones(T) * 0.01  # no solar in this region
        sigmas_t[:, 1 * 5 + r_idx] *= solar_scale

    # Wind scaling: moderate dependence (sublinear)
    for r_idx, region in enumerate(REGIONS):
        wind_col = forecasts["wind"][:, r_idx]
        if region in WIND_REGIONS:
            p50 = np.median(wind_col[wind_col > 0]) if np.any(wind_col > 0) else 1.0
            wind_scale = np.clip(wind_col / p50, 0.1, 4.0) ** 0.7
        else:
            # Non-wind regions: mildly context-dependent on system-wide wind
            wind_factor = np.clip(forecasts["wind"].mean(axis=1) / (forecasts["wind"].mean() + 1e-8), 0.3, 2.0) ** 0.3
            wind_scale = 0.5 * wind_factor
        sigmas_t[:, 2 * 5 + r_idx] *= wind_scale

    return sigmas_t


def compute_context_R_source(R_source_base, context):
    """Compute context-perturbed source correlation matrix at each time step.

    Three empirical effects:
      1. High solar → stronger solar-wind anticorrelation
      2. High wind → stronger wind-load positive correlation
      3. High load → stronger load-solar anticorrelation

    Args:
        R_source_base: (3, 3) base correlation
        context: (T, 7) context features (col 1 = solar_fc_norm, col 2 = wind_fc_norm)

    Returns:
        R_source_t: (T, 3, 3) context-dependent source correlation
    """
    T = context.shape[0]
    R_source_t = np.tile(R_source_base, (T, 1, 1))  # (T, 3, 3)

    # Normalized solar context clipped to [0, 1] for perturbation strength
    solar_ctx = np.clip(context[:, 1], 0, 2.0) / 2.0  # maps ~[0, 1]
    wind_ctx = np.clip(context[:, 2], 0, 2.0) / 2.0

    # Effect 1: high solar → solar-wind anticorrelation strengthens
    # solar idx = 1, wind idx = 2
    delta_sw = -0.40 * solar_ctx  # up to -0.40 additional anticorrelation
    R_source_t[:, 1, 2] += delta_sw
    R_source_t[:, 2, 1] += delta_sw

    # Effect 2: high wind → wind-load correlation strengthens
    # load idx = 0, wind idx = 2
    delta_wl = 0.25 * wind_ctx  # up to +0.25 additional correlation
    R_source_t[:, 0, 2] += delta_wl
    R_source_t[:, 2, 0] += delta_wl

    # Effect 3: high load → stronger load-solar anticorrelation
    # load idx = 0, solar idx = 1
    load_ctx = np.clip(context[:, 0], 0, 2.0) / 2.0
    delta_ls = -0.20 * load_ctx  # up to -0.20 additional anticorrelation
    R_source_t[:, 0, 1] += delta_ls
    R_source_t[:, 1, 0] += delta_ls

    # Project to nearest PSD (eigenvalue clipping)
    for t in range(T):
        eigvals, eigvecs = np.linalg.eigh(R_source_t[t])
        eigvals = np.maximum(eigvals, 0.01)
        R_source_t[t] = eigvecs @ np.diag(eigvals) @ eigvecs.T
        # Re-normalize to unit diagonal
        d = np.sqrt(np.diag(R_source_t[t]))
        R_source_t[t] = R_source_t[t] / np.outer(d, d)

    return R_source_t


def compute_ground_truth_L(sigmas_t, R_source_t, R_region):
    """Compute ground-truth L(xi_t) at each time step.

    Args:
        sigmas_t: (T, 15) context-dependent std devs
        R_source_t: (T, 3, 3) context-dependent source correlation
        R_region: (5, 5) fixed regional correlation

    Returns:
        L_true_t: (T, 15, 15) ground-truth Cholesky factors
    """
    T = sigmas_t.shape[0]
    L_true_t = np.zeros((T, 15, 15))

    for t in range(T):
        R_full = np.kron(R_source_t[t], R_region)  # (15, 15)
        D = np.diag(sigmas_t[t])
        Sigma = D @ R_full @ D

        # Ensure PSD
        eigvals = np.linalg.eigvalsh(Sigma)
        if eigvals.min() < 1e-10:
            Sigma += (1e-8 - eigvals.min()) * np.eye(15)

        L_true_t[t] = np.linalg.cholesky(Sigma)

    return L_true_t


# ===========================================================================
# Time series generation
# ===========================================================================

def generate_var1_with_context(phi, sigmas_t, R_source_t, R_region, n_hours, seed=42):
    """Generate VAR(1) time series with context-dependent innovations.

    At each step: u_t = Phi * u_{t-1} + L_innov(xi_t) * z_t
    where L_innov(xi_t) is derived from the context-dependent covariance.
    """
    rng = np.random.default_rng(seed)
    d = 15
    u = np.zeros((n_hours, d))

    # Precompute innovation Cholesky for each time step
    # Sigma_innov(xi_t)(i,j) = Sigma(xi_t)(i,j) * (1 - phi_i * phi_j)
    phi_outer = np.outer(phi, phi)

    burn_in = 500
    u_prev = np.zeros(d)

    for t in range(-burn_in, n_hours):
        idx = max(t, 0)  # use t=0 params during burn-in

        # Context-dependent covariance at this step
        R_full = np.kron(R_source_t[idx], R_region)
        D = np.diag(sigmas_t[idx])
        Sigma = D @ R_full @ D

        # Innovation covariance
        Sigma_innov = Sigma * (1 - phi_outer)
        eigvals = np.linalg.eigvalsh(Sigma_innov)
        if eigvals.min() < 1e-10:
            Sigma_innov += (1e-8 - eigvals.min()) * np.eye(d)

        L_innov = np.linalg.cholesky(Sigma_innov)

        z = rng.standard_normal(d)
        epsilon = L_innov @ z
        u_new = phi * u_prev + epsilon

        if t >= 0:
            u[t] = u_new
        u_prev = u_new

    return u


# ===========================================================================
# Main
# ===========================================================================

def generate_uncertainty_data(n_years=4, seed=42, tau=0.95):
    """Generate complete uncertainty dataset with context features.

    Returns:
        dict with all generated data and metadata
    """
    print("=" * 60)
    print("Generating 15-D Context-Dependent Uncertainty Data")
    print("for IEEE 118-Bus Robust SCED Experiment")
    print("=" * 60)

    # Step 1: Fit parameters from real data
    print("\n[1/7] Fitting source-type parameters from Germany OPSD...")
    source_params = fit_source_correlation()
    R_source_base = source_params["R_source"]
    print(f"  R_source condition number: {np.linalg.cond(R_source_base):.2f}")
    print(f"  AR(1): {source_params['ar_coeffs']}")

    print("\n[2/7] Fitting spatial parameters from Multi-ISO...")
    region_params = fit_region_correlation()
    R_region = region_params["R_region"]
    print(f"  R_region condition number: {np.linalg.cond(R_region):.2f}")

    # Step 2: Build base structure
    print("\n[3/7] Building base covariance structure...")
    region_loads = compute_region_loads()
    sigmas_base = build_marginal_sigmas(source_params["sigma_fracs"], region_loads)
    phi = build_ar_coefficients(source_params["ar_coeffs"], region_params["ar_coeffs"])
    print(f"  Base sigma range: [{sigmas_base.min():.1f}, {sigmas_base.max():.1f}] MW")
    print(f"  AR(1) range: [{phi.min():.3f}, {phi.max():.3f}]")

    # Step 3: Generate timestamps and forecast context
    n_hours = n_years * 8760
    timestamps = pd.date_range("2020-01-01", periods=n_hours, freq="h")
    rng = np.random.default_rng(seed)

    print(f"\n[4/7] Generating forecast context features ({n_hours} hours)...")
    forecasts, context = generate_forecasts(timestamps, region_loads, rng)
    print(f"  Context shape: {context.shape}")
    print(f"  Load forecast range: [{forecasts['load'].min():.0f}, {forecasts['load'].max():.0f}] MW")
    print(f"  Solar forecast range: [{forecasts['solar'].min():.0f}, {forecasts['solar'].max():.0f}] MW")
    print(f"  Wind forecast range: [{forecasts['wind'].min():.0f}, {forecasts['wind'].max():.0f}] MW")

    # Step 4: Compute context-dependent sigmas and correlations
    print("\n[5/7] Computing context-dependent covariance L(xi)...")
    sigmas_t = compute_context_sigmas(sigmas_base, forecasts, region_loads)
    R_source_t = compute_context_R_source(R_source_base, context)
    print(f"  Sigma_t range: [{sigmas_t.min():.2f}, {sigmas_t.max():.1f}] MW")
    print(f"  Solar sigma night vs day: {sigmas_t[:24, 5].min():.2f} vs {sigmas_t[12*30:12*30+24, 5].max():.1f} MW")

    # Sample ground-truth L at a few points for verification
    sample_R_corr_sw = R_source_t[:, 1, 2]
    sample_R_corr_wl = R_source_t[:, 0, 2]
    print(f"  Solar-wind corr range: [{sample_R_corr_sw.min():.3f}, {sample_R_corr_sw.max():.3f}]")
    print(f"  Wind-load corr range:  [{sample_R_corr_wl.min():.3f}, {sample_R_corr_wl.max():.3f}]")

    # Step 5: Generate VAR(1) time series
    print(f"\n[6/7] Generating VAR(1) time series with context-dependent innovations...")
    u = generate_var1_with_context(phi, sigmas_t, R_source_t, R_region, n_hours, seed=seed + 1)
    print(f"  u shape: {u.shape}")
    print(f"  Empirical std range: [{u.std(axis=0).min():.1f}, {u.std(axis=0).max():.1f}] MW")

    # Check AR(1)
    emp_ar1 = np.array([pd.Series(u[:, i]).autocorr(lag=1) for i in range(15)])
    print(f"  Empirical AR(1) range: [{emp_ar1.min():.3f}, {emp_ar1.max():.3f}]")

    # Step 6: Compute ground-truth L (subsample for storage)
    print("\n  Computing ground-truth L_true(xi_t) for all time steps...")
    L_true_t = compute_ground_truth_L(sigmas_t, R_source_t, R_region)
    print(f"  L_true_t shape: {L_true_t.shape}")

    # Step 7: Build allocation matrix and splits
    print(f"\n[7/7] Building allocation matrix and train/tune/calibrate split...")
    A = build_allocation_matrix()
    print(f"  A shape: {A.shape}, non-zero: {np.count_nonzero(A)}")

    n_train = int(0.6 * n_hours)
    n_tune = int(0.2 * n_hours)
    n_cal = n_hours - n_train - n_tune
    split_indices = {
        "train": (0, n_train),
        "tune": (n_train, n_train + n_tune),
        "calibrate": (n_train + n_tune, n_hours),
    }
    print(f"  Train:     {n_train:,} hours ({timestamps[0]} to {timestamps[n_train-1]})")
    print(f"  Tune:      {n_tune:,} hours ({timestamps[n_train]} to {timestamps[n_train+n_tune-1]})")
    print(f"  Calibrate: {n_cal:,} hours ({timestamps[n_train+n_tune]} to {timestamps[-1]})")

    # === Save outputs ===
    print("\nSaving outputs...")

    # Context features
    ctx_df = pd.DataFrame(context, columns=CONTEXT_LABELS, index=timestamps)
    ctx_df.index.name = "timestamp"
    ctx_df.to_parquet(os.path.join(OUTPUT_DIR, "context_7d.parquet"))
    print(f"  context_7d.parquet {ctx_df.shape}")

    # Uncertainty time series
    u_df = pd.DataFrame(u, columns=DIM_LABELS, index=timestamps)
    u_df.index.name = "timestamp"
    u_df.to_parquet(os.path.join(OUTPUT_DIR, "uncertainty_15d.parquet"))
    print(f"  uncertainty_15d.parquet {u_df.shape}")

    # Regional forecasts (raw, for detailed context if needed)
    for source in SOURCES:
        fc_df = pd.DataFrame(forecasts[source], columns=REGIONS, index=timestamps)
        fc_df.index.name = "timestamp"
        fc_df.to_parquet(os.path.join(OUTPUT_DIR, f"forecast_{source}.parquet"))
    print(f"  forecast_{{load,solar,wind}}.parquet (T, 5) each")

    # Allocation matrix
    np.save(os.path.join(OUTPUT_DIR, "allocation_matrix.npy"), A)

    # Ground-truth L(xi) for every time step
    np.save(os.path.join(OUTPUT_DIR, "L_true_t.npy"), L_true_t)
    print(f"  L_true_t.npy {L_true_t.shape} ({L_true_t.nbytes / 1e6:.1f} MB)")

    # Base (unconditional) covariance for reference
    R_full_base = np.kron(R_source_base, R_region)
    D_base = np.diag(sigmas_base)
    Sigma_base = D_base @ R_full_base @ D_base
    np.save(os.path.join(OUTPUT_DIR, "sigma_base.npy"), Sigma_base)
    np.save(os.path.join(OUTPUT_DIR, "L_base.npy"), np.linalg.cholesky(Sigma_base + 1e-10 * np.eye(15)))

    # AR(1) and context-dependent sigmas
    np.save(os.path.join(OUTPUT_DIR, "phi_ar1.npy"), phi)
    np.save(os.path.join(OUTPUT_DIR, "sigmas_t.npy"), sigmas_t)

    # Zonal uncertainty for convenience
    delta_p = u @ A.T
    delta_p_df = pd.DataFrame(delta_p, columns=[f"zone_{z}" for z in range(1, 11)], index=timestamps)
    delta_p_df.index.name = "timestamp"
    delta_p_df.to_parquet(os.path.join(OUTPUT_DIR, "zonal_uncertainty_10d.parquet"))
    print(f"  zonal_uncertainty_10d.parquet {delta_p_df.shape}")

    # Metadata
    metadata = {
        "d": 15,
        "d_context": 7,
        "n_sources": 3,
        "n_regions": 5,
        "sources": SOURCES,
        "regions": REGIONS,
        "dim_labels": DIM_LABELS,
        "context_labels": CONTEXT_LABELS,
        "zone_to_region": {str(z): r for r, zones in REGION_ZONES.items() for z in zones},
        "region_loads_mw": region_loads,
        "solar_zones": sorted(SOLAR_ZONES),
        "wind_zones": sorted(WIND_ZONES),
        "solar_regions": sorted(SOLAR_REGIONS),
        "wind_regions": sorted(WIND_REGIONS),
        "n_hours": n_hours,
        "n_years": n_years,
        "seed": seed,
        "tau": tau,
        "split_indices": {k: list(v) for k, v in split_indices.items()},
        "marginal_sigmas_base_mw": sigmas_base.tolist(),
        "ar1_coefficients": phi.tolist(),
        "context_dependent_effects": {
            "solar_variance": "sigma_solar * clip(solar_fc / solar_fc_p75, 0.01, 3.0)",
            "wind_variance": "sigma_wind * clip(wind_fc / wind_fc_p50, 0.1, 4.0)^0.7",
            "load_variance": "sigma_load * (0.6 + 0.4 * load_fc / load_fc_mean)",
            "wind_nonwind_regions": "0.5 * clip(wind_fc_avg / wind_fc_mean, 0.3, 2.0)^0.3",
            "solar_wind_corr_shift": "delta_R(solar,wind) = -0.40 * clip(solar_ctx, 0, 1)",
            "wind_load_corr_shift": "delta_R(wind,load) = +0.25 * clip(wind_ctx, 0, 1)",
            "load_solar_corr_shift": "delta_R(load,solar) = -0.20 * clip(load_ctx, 0, 1)",
        },
    }
    with open(os.path.join(OUTPUT_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  metadata.json")

    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")

    return {
        "u": u,
        "context": context,
        "forecasts": forecasts,
        "timestamps": timestamps,
        "A": A,
        "L_true_t": L_true_t,
        "sigmas_t": sigmas_t,
        "phi": phi,
        "split_indices": split_indices,
        "metadata": metadata,
    }


if __name__ == "__main__":
    generate_uncertainty_data()
