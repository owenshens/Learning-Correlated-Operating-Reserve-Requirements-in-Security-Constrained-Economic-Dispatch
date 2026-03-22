#!/usr/bin/env python3
"""
Generate all data assets for the algorithm-first GradientDemo.

The demo is now driven by:
- truthful Static-L training traces (decoupled and coupled)
- a deterministic toy trace with the same loop contract
- curated contextual cases derived from the saved NN model
- a lightweight sandbox catalog for browser-side interpolation

The script still exports the zone/network metadata used by the canvas app,
but the main story assets now live under GradientDemo/data/precomputed/.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DATA_DIR = SCRIPT_DIR
PRECOMPUTED_DIR = os.path.join(DEMO_DATA_DIR, "precomputed")
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "Experiment")
EXPERIMENT_DATA_DIR = os.path.join(EXPERIMENT_DIR, "data")
MODELS_DIR = os.path.join(EXPERIMENT_DATA_DIR, "models")

os.makedirs(PRECOMPUTED_DIR, exist_ok=True)

sys.path.insert(0, EXPERIMENT_DIR)

from methods import ContextNN, box_method, sample_cov_method  # noqa: E402
from sced import (  # noqa: E402
    compute_profiled_gradient,
    compute_reserve_requirements,
    conformal_calibrate,
    gauge_gradient,
    gauge_scores_batch,
    project_cholesky,
    quantile_sensitivity,
    smoothed_quantile,
    solve_sced,
    support_gradient,
)
from sced_coupled import solve_coupled_sced  # noqa: E402
from utils import load_data, split_data  # noqa: E402


SEED = 42
TAU = 0.95
EPS = 0.5
STATIC_ITERS = 200
PROJECTION_ZONE_IDS = (5, 7)
VISUAL_SAMPLE_COUNT = 220
TOY_VISUAL_SAMPLE_COUNT = 240


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return super().default(obj)


@dataclass
class ProjectionSpec:
    zone_ids: Tuple[int, int]
    labels: Tuple[str, str]
    rows: np.ndarray


def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, cls=NumpyEncoder, indent=2)
    print(f"  -> wrote {path}")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def safe_cholesky(matrix: np.ndarray) -> np.ndarray:
    jitter = 1e-9
    eye = np.eye(matrix.shape[0])
    for _ in range(8):
        try:
            return np.linalg.cholesky(matrix + jitter * eye)
        except np.linalg.LinAlgError:
            jitter *= 10
    eigvals, eigvecs = np.linalg.eigh(matrix)
    eigvals = np.maximum(eigvals, 1e-8)
    repaired = eigvecs @ np.diag(eigvals) @ eigvecs.T
    return np.linalg.cholesky(repaired)


def project_L_to_plane(L_full: np.ndarray, projection_rows: np.ndarray) -> np.ndarray:
    sigma = L_full @ L_full.T
    sigma_2d = projection_rows @ sigma @ projection_rows.T
    return safe_cholesky(sigma_2d)


def ellipse_axes(L_2d: np.ndarray, rho: float) -> Tuple[float, float, float]:
    scaled = rho * L_2d
    sigma = scaled @ scaled.T
    eigvals, eigvecs = np.linalg.eigh(sigma)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    semi_a = float(math.sqrt(max(eigvals[0], 1e-9)))
    semi_b = float(math.sqrt(max(eigvals[1], 1e-9)))
    angle = float(math.atan2(eigvecs[1, 0], eigvecs[0, 0]))
    return semi_a, semi_b, angle


def project_samples(U: np.ndarray, projection_rows: np.ndarray) -> np.ndarray:
    return U @ projection_rows.T


def classify_inside(U: np.ndarray, L: np.ndarray, rho: float) -> List[bool]:
    L_inv = np.linalg.inv(L)
    mahal = np.linalg.norm((L_inv @ U.T).T, axis=1)
    return (mahal <= rho + 1e-12).tolist()


def build_histogram(scores: np.ndarray, bins: int = 24):
    counts, edges = np.histogram(scores, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers.tolist(), counts.tolist()


def build_cdf(scores: np.ndarray):
    xs = np.sort(scores)
    ys = np.linspace(1.0 / len(xs), 1.0, len(xs))
    return xs.tolist(), ys.tolist()


def format_zone_label(zone_index: int) -> str:
    return f"Zone {zone_index + 1}"


def compute_support_points(
    L: np.ndarray,
    rho_hat: float,
    A: np.ndarray,
    projection_rows: np.ndarray,
) -> List[Dict[str, float]]:
    sigma = L @ L.T
    points = []
    for z in range(A.shape[0]):
        w_z = A[z]
        denom = np.linalg.norm(L.T @ w_z)
        if denom < 1e-12:
            u_star = np.zeros(L.shape[0])
            support = 0.0
        else:
            u_star = rho_hat * (sigma @ w_z) / denom
            support = float(rho_hat * denom)
        p2 = projection_rows @ u_star
        points.append(
            {
                "zone": z + 1,
                "x": float(p2[0]),
                "y": float(p2[1]),
                "support": support,
            }
        )
    return points


def compute_zone_contributions(
    L: np.ndarray,
    rho_hat: float,
    A: np.ndarray,
    mu_z: np.ndarray,
    lambda_z: np.ndarray,
) -> Tuple[List[Dict[str, float]], List[int], np.ndarray, float]:
    contributions = []
    g_shape = np.zeros_like(L)
    g_size = 0.0
    combined = mu_z + lambda_z
    for z in range(A.shape[0]):
        w_z = A[z]
        norm_ltw = np.linalg.norm(L.T @ w_z)
        shape_grad = np.zeros_like(L)
        size_grad = 0.0
        if norm_ltw >= 1e-12 and combined[z] > 1e-12:
            shape_grad = combined[z] * support_gradient(L, rho_hat, w_z)
            size_grad = combined[z] * norm_ltw
            g_shape += shape_grad
            g_size += size_grad
        shape_norm = float(np.linalg.norm(shape_grad))
        total_score = shape_norm + abs(size_grad)
        contributions.append(
            {
                "zone": z + 1,
                "label": format_zone_label(z),
                "mu": float(mu_z[z]),
                "lambda": float(lambda_z[z]),
                "combined_dual": float(combined[z]),
                "support": float(rho_hat * norm_ltw),
                "shape_contribution_norm": shape_norm,
                "size_contribution": float(size_grad),
                "total_contribution": total_score,
            }
        )
    dominant = [
        row["zone"]
        for row in sorted(contributions, key=lambda item: item["total_contribution"], reverse=True)[:3]
    ]
    return contributions, dominant, combined, g_size


def compute_shape_drift(L_prev: np.ndarray, L_next: np.ndarray) -> float:
    denom = max(np.linalg.norm(L_prev), 1e-12)
    return float(np.linalg.norm(L_next - L_prev) / denom)


def project_gradient_2d(grad: np.ndarray, projection_rows: np.ndarray) -> List[List[float]]:
    projected = projection_rows @ grad @ projection_rows.T
    return projected.tolist()


def decode_context(row: np.ndarray) -> Dict[str, float]:
    hour_angle = math.atan2(row[3], row[4])
    if hour_angle < 0:
        hour_angle += 2 * math.pi
    hour = int(round((hour_angle / (2 * math.pi)) * 24)) % 24

    month_angle = math.atan2(row[5], row[6])
    if month_angle < 0:
        month_angle += 2 * math.pi
    month = int(round((month_angle / (2 * math.pi)) * 12)) + 1
    month = min(max(month, 1), 12)

    return {
        "load": float(row[0]),
        "solar": float(row[1]),
        "wind": float(row[2]),
        "hour": hour,
        "month": month,
    }


def encode_context(load_v: float, solar_v: float, wind_v: float, hour: int, month: int) -> np.ndarray:
    hour_angle = (hour % 24) / 24.0 * 2 * math.pi
    month_angle = ((month - 1) % 12) / 12.0 * 2 * math.pi
    return np.array(
        [
            load_v,
            solar_v,
            wind_v,
            math.sin(hour_angle),
            math.cos(hour_angle),
            math.sin(month_angle),
            math.cos(month_angle),
        ],
        dtype=float,
    )


def nearest_context_indices(xi: np.ndarray, target: np.ndarray, k: int) -> np.ndarray:
    weights = np.array([1.0, 1.0, 1.0, 0.35, 0.35, 0.25, 0.25])
    distances = np.sum(((xi - target) * weights) ** 2, axis=1)
    return np.argsort(distances)[:k]


def load_context_model(path: str) -> ContextNN:
    state = torch.load(path, map_location="cpu")
    hidden_dims = [state["net.0.weight"].shape[0], state["net.2.weight"].shape[0]]
    d_ctx = state["net.0.weight"].shape[1]
    d_unc = int((-1 + math.sqrt(1 + 8 * state["net.4.bias"].shape[0])) / 2)
    model = ContextNN(d_context=d_ctx, d_uncertainty=d_unc, hidden_dims=hidden_dims)
    model.load_state_dict(state)
    model.eval()
    return model


def build_projection_spec(A: np.ndarray) -> ProjectionSpec:
    zone_a = PROJECTION_ZONE_IDS[0] - 1
    zone_b = PROJECTION_ZONE_IDS[1] - 1
    rows = np.vstack([A[zone_a], A[zone_b]])
    labels = (
        f"Exposure along Zone {PROJECTION_ZONE_IDS[0]}",
        f"Exposure along Zone {PROJECTION_ZONE_IDS[1]}",
    )
    return ProjectionSpec(PROJECTION_ZONE_IDS, labels, rows)


def choose_visual_subset(U: np.ndarray, count: int, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(U), size=min(count, len(U)), replace=False)
    idx.sort()
    return U[idx]


def make_iteration_record(
    *,
    iter_index: int,
    L_curr: np.ndarray,
    L_next: np.ndarray,
    rho_hat: float,
    tau_target: float,
    scores_tune: np.ndarray,
    coverage_cal: float,
    coverage_test: float,
    reserves_per_zone: np.ndarray,
    sced_result: Dict[str, np.ndarray],
    mu_z: np.ndarray,
    lambda_z: np.ndarray,
    grad_lower: np.ndarray,
    grad_rho: np.ndarray,
    zone_contributions: List[Dict[str, float]],
    dominant_zones: List[int],
    combined_duals: np.ndarray,
    projection: ProjectionSpec,
    A: np.ndarray,
    U_visual: np.ndarray,
) -> Dict[str, object]:
    L_2d = project_L_to_plane(L_curr, projection.rows)
    L_next_2d = project_L_to_plane(L_next, projection.rows)
    semi_a, semi_b, angle = ellipse_axes(L_2d, rho_hat)
    hist_x, hist_counts = build_histogram(scores_tune)
    cdf_x, cdf_y = build_cdf(scores_tune)
    support_points = compute_support_points(L_curr, rho_hat, A, projection.rows)
    g_shape_only = sum(
        (
            contribution["combined_dual"] * support_gradient(L_curr, rho_hat, A[contribution["zone"] - 1])
            if contribution["combined_dual"] > 1e-12
            else np.zeros_like(L_curr)
        )
        for contribution in zone_contributions
    )
    grad_rho_norm = float(np.linalg.norm(grad_rho))
    grad_shape_norm = float(np.linalg.norm(g_shape_only))
    grad_norm = float(np.linalg.norm(grad_lower))
    return {
        "iter": iter_index,
        "L_full": L_curr.tolist(),
        "L_2d": L_2d.tolist(),
        "L_next_2d": L_next_2d.tolist(),
        "rho_hat": float(rho_hat),
        "tau_target": float(tau_target),
        "coverage_cal": float(coverage_cal),
        "coverage_test": float(coverage_test),
        "score_hist_bins": hist_x,
        "score_hist_counts": hist_counts,
        "score_cdf_x": cdf_x,
        "score_cdf_y": cdf_y,
        "reserves_per_zone": reserves_per_zone.tolist(),
        "reserve_total": float(reserves_per_zone.sum()),
        "support_by_zone": reserves_per_zone.tolist(),
        "support_points_2d": support_points,
        "cost": float(sced_result["cost"]),
        "energy_cost": float(sced_result.get("energy_cost", 0.0)),
        "reserve_cost": float(sced_result.get("reserve_cost", 0.0)),
        "mu_z": mu_z.tolist(),
        "lambda_z": lambda_z.tolist(),
        "combined_duals": combined_duals.tolist(),
        "grad_norm": grad_norm,
        "grad_shape_norm": grad_shape_norm,
        "grad_rho_norm": grad_rho_norm,
        "grad_2d": project_gradient_2d(grad_lower, projection.rows),
        "zone_contributions": zone_contributions,
        "shape_drift": compute_shape_drift(L_curr, L_next),
        "dominant_zones": dominant_zones,
        "semi_a": semi_a,
        "semi_b": semi_b,
        "angle": angle,
        "inside_mask": classify_inside(U_visual, L_curr, rho_hat),
    }


def build_static_story_trace(
    *,
    title: str,
    story_key: str,
    L_init: np.ndarray,
    u_tune: np.ndarray,
    u_cal: np.ndarray,
    u_test: np.ndarray,
    A: np.ndarray,
    gen_data,
    zone_loads,
    zone_gens,
    projection: ProjectionSpec,
    U_visual: np.ndarray,
    n_iters: int,
    lr: float,
    coupled: bool = False,
    T_z_max: np.ndarray | None = None,
) -> Dict[str, object]:
    L = L_init.copy()
    iterations = []
    best_cost = float("inf")
    best_index = 0
    max_grad_norm = 10.0

    for k in range(n_iters):
        scores_tune = gauge_scores_batch(L, u_tune)
        rho_hat = smoothed_quantile(scores_tune, TAU, EPS)
        grad_rho = quantile_sensitivity(L, scores_tune, u_tune, rho_hat, EPS)
        reserves = compute_reserve_requirements(L, rho_hat, A)

        if coupled:
            sced_result = solve_coupled_sced(reserves, T_z_max, gen_data, zone_loads, zone_gens)
            mu_z = sced_result["mu_z"]
            lambda_z = sced_result["lambda_z"]
        else:
            sced_result = solve_sced(reserves, gen_data, zone_loads, zone_gens)
            mu_z = sced_result["mu_z"]
            lambda_z = np.zeros_like(mu_z)

        if not sced_result["feasible"]:
            continue

        zone_contributions, dominant_zones, combined_duals, _ = compute_zone_contributions(
            L, rho_hat, A, mu_z, lambda_z
        )
        grad = compute_profiled_gradient(L, rho_hat, A, combined_duals, grad_rho)
        grad_lower = np.tril(grad)
        grad_norm = np.linalg.norm(grad_lower)
        if grad_norm > max_grad_norm:
            grad_lower = grad_lower * (max_grad_norm / grad_norm)

        L_next = project_cholesky(L - lr * grad_lower)
        coverage_cal = float(np.mean(gauge_scores_batch(L, u_cal) <= rho_hat))
        coverage_test = float(np.mean(gauge_scores_batch(L, u_test) <= rho_hat))
        record = make_iteration_record(
            iter_index=k,
            L_curr=L,
            L_next=L_next,
            rho_hat=rho_hat,
            tau_target=TAU,
            scores_tune=scores_tune,
            coverage_cal=coverage_cal,
            coverage_test=coverage_test,
            reserves_per_zone=reserves,
            sced_result=sced_result,
            mu_z=mu_z,
            lambda_z=lambda_z,
            grad_lower=grad_lower,
            grad_rho=grad_rho,
            zone_contributions=zone_contributions,
            dominant_zones=dominant_zones,
            combined_duals=combined_duals,
            projection=projection,
            A=A,
            U_visual=U_visual,
        )
        iterations.append(record)

        if record["cost"] < best_cost:
            best_cost = record["cost"]
            best_index = len(iterations) - 1

        L = L_next

    checkpoint_candidates = [0, len(iterations) // 4, len(iterations) // 2, (3 * len(iterations)) // 4, best_index, len(iterations) - 1]
    checkpoints = sorted({idx for idx in checkpoint_candidates if 0 <= idx < len(iterations)})
    visual_points = project_samples(U_visual, projection.rows)
    sample_points = [{"x": float(x), "y": float(y)} for x, y in visual_points]
    return {
        "title": title,
        "story_key": story_key,
        "tau_target": TAU,
        "projection": {
            "zones": list(projection.zone_ids),
            "labels": list(projection.labels),
        },
        "checkpoints": checkpoints,
        "samples": sample_points,
        "iterations": iterations,
    }


def build_toy_story() -> Dict[str, object]:
    rng = np.random.default_rng(SEED)
    toy_A = np.array(
        [
            [1.0, 0.0],
            [0.62, 0.78],
            [-0.78, 0.62],
        ]
    )
    samples = rng.multivariate_normal(
        mean=np.zeros(2),
        cov=np.array([[2.4, 1.1], [1.1, 1.8]]),
        size=TOY_VISUAL_SAMPLE_COUNT,
    )
    u_tune = samples[:160]
    u_cal = samples[160:200]
    u_test = samples[200:]
    projection = ProjectionSpec((1, 2), ("Toy axis x", "Toy axis y"), np.eye(2))
    L = np.array([[1.85, 0.0], [0.72, 1.35]])
    iterations = []

    for k in range(8):
        scores_tune = gauge_scores_batch(L, u_tune)
        rho_hat = smoothed_quantile(scores_tune, TAU, 0.35)
        grad_rho = quantile_sensitivity(L, scores_tune, u_tune, rho_hat, 0.35)
        reserves = compute_reserve_requirements(L, rho_hat, toy_A)
        mu_z = np.clip((reserves / max(reserves.max(), 1e-9)) * np.array([1.4, 3.0, 2.1]), 0.0, None)
        lambda_z = np.zeros_like(mu_z)
        cost = float(25 + np.dot(np.array([0.9, 1.8, 1.2]), reserves))
        energy_cost = float(18.0 + 0.15 * k)
        reserve_cost = float(cost - energy_cost)
        zone_contributions, dominant_zones, combined_duals, _ = compute_zone_contributions(
            L, rho_hat, toy_A, mu_z, lambda_z
        )
        grad = compute_profiled_gradient(L, rho_hat, toy_A, combined_duals, grad_rho)
        grad_lower = np.tril(grad)
        grad_norm = np.linalg.norm(grad_lower)
        if grad_norm > 4.0:
            grad_lower = grad_lower * (4.0 / grad_norm)
        L_next = project_cholesky(L - 0.06 * grad_lower)
        coverage_cal = float(np.mean(gauge_scores_batch(L, u_cal) <= rho_hat))
        coverage_test = float(np.mean(gauge_scores_batch(L, u_test) <= rho_hat))
        record = make_iteration_record(
            iter_index=k,
            L_curr=L,
            L_next=L_next,
            rho_hat=rho_hat,
            tau_target=TAU,
            scores_tune=scores_tune,
            coverage_cal=coverage_cal,
            coverage_test=coverage_test,
            reserves_per_zone=reserves,
            sced_result={
                "cost": cost,
                "energy_cost": energy_cost,
                "reserve_cost": reserve_cost,
            },
            mu_z=mu_z,
            lambda_z=lambda_z,
            grad_lower=grad_lower,
            grad_rho=grad_rho,
            zone_contributions=zone_contributions,
            dominant_zones=dominant_zones,
            combined_duals=combined_duals,
            projection=projection,
            A=toy_A,
            U_visual=samples,
        )
        iterations.append(record)
        L = L_next

    sample_points = [{"x": float(x), "y": float(y)} for x, y in samples]
    return {
        "title": "Toy Gradient Loop",
        "story_key": "toy",
        "tau_target": TAU,
        "projection": {
            "zones": [1, 2],
            "labels": ["Toy x", "Toy y"],
        },
        "checkpoints": [0, 2, 4, 6, 7],
        "samples": sample_points,
        "iterations": iterations,
        "zone_labels": ["Alpha", "Beta", "Gamma"],
    }


def evaluate_static_record(
    *,
    L: np.ndarray,
    rho: float,
    A: np.ndarray,
    gen_data,
    zone_loads,
    zone_gens,
    projection: ProjectionSpec,
    U_local: np.ndarray,
    coupled: bool = False,
    T_z_max: np.ndarray | None = None,
) -> Dict[str, object]:
    reserves = compute_reserve_requirements(L, rho, A)
    if coupled:
        sced_result = solve_coupled_sced(reserves, T_z_max, gen_data, zone_loads, zone_gens)
        lambda_z = sced_result["lambda_z"]
    else:
        sced_result = solve_sced(reserves, gen_data, zone_loads, zone_gens)
        lambda_z = np.zeros(A.shape[0])
    mu_z = sced_result["mu_z"]
    L_2d = project_L_to_plane(L, projection.rows)
    semi_a, semi_b, angle = ellipse_axes(L_2d, rho)
    zone_contributions, dominant_zones, combined_duals, _ = compute_zone_contributions(L, rho, A, mu_z, lambda_z)
    coverage = float(np.mean(gauge_scores_batch(L, U_local) <= rho))
    dominant_zone = dominant_zones[0] if dominant_zones else 1
    support_points = compute_support_points(L, rho, A, projection.rows)
    return {
        "cost": float(sced_result["cost"]),
        "energy_cost": float(sced_result.get("energy_cost", 0.0)),
        "reserve_cost": float(sced_result.get("reserve_cost", 0.0)),
        "reserves_per_zone": reserves.tolist(),
        "reserve_total": float(reserves.sum()),
        "coverage": coverage,
        "rho": float(rho),
        "tau_target": TAU,
        "L_2d": L_2d.tolist(),
        "semi_a": semi_a,
        "semi_b": semi_b,
        "angle": angle,
        "mu_z": mu_z.tolist(),
        "lambda_z": lambda_z.tolist(),
        "combined_duals": combined_duals.tolist(),
        "dominant_zone": dominant_zone,
        "dominant_zones": dominant_zones,
        "zone_contributions": zone_contributions,
        "support_points_2d": support_points,
    }


def build_context_cases(
    *,
    model: ContextNN,
    xi_tune: np.ndarray,
    u_tune: np.ndarray,
    xi_test: np.ndarray,
    u_test: np.ndarray,
    A: np.ndarray,
    gen_data,
    zone_loads,
    zone_gens,
    projection: ProjectionSpec,
) -> Dict[str, object]:
    scores_tune = np.zeros(len(u_tune))
    xi_tune_t = torch.tensor(xi_tune, dtype=torch.float32)
    with torch.no_grad():
        L_tune = model(xi_tune_t).numpy()
    for i in range(len(u_tune)):
        scores_tune[i] = np.linalg.norm(np.linalg.solve(L_tune[i], u_tune[i]))
    rho_hat = smoothed_quantile(scores_tune, TAU, EPS)

    targets = {
        "low": np.array([-1.2, -0.7, -0.6]),
        "nominal": np.array([0.0, -0.2, 0.0]),
        "storm": np.array([1.1, 1.8, 2.0]),
    }
    cases = []
    for label, target_xyz in targets.items():
        distances = np.sum((xi_test[:, :3] - target_xyz) ** 2, axis=1)
        idx = int(np.argmin(distances))
        xi_case = xi_test[idx]
        local_idx = nearest_context_indices(xi_test, xi_case, min(192, len(xi_test)))
        U_local = u_test[local_idx]
        with torch.no_grad():
            L_case = model(torch.tensor(xi_case[None, :], dtype=torch.float32)).numpy()[0]
        record = evaluate_static_record(
            L=L_case,
            rho=rho_hat,
            A=A,
            gen_data=gen_data,
            zone_loads=zone_loads,
            zone_gens=zone_gens,
            projection=projection,
            U_local=U_local,
        )
        batch_idx = nearest_context_indices(xi_tune, xi_case, min(8, len(xi_tune)))
        mu_batch = []
        sample_summaries = []
        grad_norms = []
        with torch.no_grad():
            L_batch = model(torch.tensor(xi_tune[batch_idx], dtype=torch.float32)).numpy()
        grad_rho = np.zeros_like(L_batch[0])
        weights = np.exp(-0.5 * ((rho_hat - scores_tune) / EPS) ** 2) / math.sqrt(2 * math.pi)
        if weights.sum() > 1e-12:
            for i, weight in enumerate(weights):
                if weight > 1e-15:
                    grad_rho += weight * gauge_gradient(L_tune[i], u_tune[i])
            grad_rho /= weights.sum()
        for batch_pos, tune_idx in enumerate(batch_idx):
            L_b = L_batch[batch_pos]
            reserves = compute_reserve_requirements(L_b, rho_hat, A)
            sced = solve_sced(reserves, gen_data, zone_loads, zone_gens)
            mu_z = sced["mu_z"]
            zone_contribs, dominant, _, _ = compute_zone_contributions(
                L_b, rho_hat, A, mu_z, np.zeros_like(mu_z)
            )
            grad = compute_profiled_gradient(L_b, rho_hat, A, mu_z, grad_rho)
            grad_norms.append(float(np.linalg.norm(grad)))
            mu_batch.append(mu_z)
            sample_summaries.append(
                {
                    "sample_index": int(tune_idx),
                    "cost": float(sced["cost"]),
                    "dominant_zones": dominant,
                    "top_zone": dominant[0] if dominant else 1,
                    "reserve_total": float(reserves.sum()),
                }
            )
        aggregate_zone_pressure = np.mean(mu_batch, axis=0)
        cases.append(
            {
                "label": label,
                "context": decode_context(xi_case),
                "L_2d": record["L_2d"],
                "rho": record["rho"],
                "coverage": record["coverage"],
                "cost": record["cost"],
                "energy_cost": record["energy_cost"],
                "reserve_cost": record["reserve_cost"],
                "reserves_per_zone": record["reserves_per_zone"],
                "mu_z": record["mu_z"],
                "lambda_z": record["lambda_z"],
                "combined_duals": record["combined_duals"],
                "support_points_2d": record["support_points_2d"],
                "zone_contributions": record["zone_contributions"],
                "dominant_zone": record["dominant_zone"],
                "dominant_zones": record["dominant_zones"],
                "semi_a": record["semi_a"],
                "semi_b": record["semi_b"],
                "angle": record["angle"],
                "nn_backprop_summary": {
                    "batch_size": len(batch_idx),
                    "rho_hat": float(rho_hat),
                    "avg_grad_norm": float(np.mean(grad_norms)),
                    "dominant_zones": (np.argsort(aggregate_zone_pressure)[::-1][:3] + 1).tolist(),
                    "sample_summaries": sample_summaries,
                },
            }
        )
    return {
        "tau_target": TAU,
        "cases": cases,
    }


def build_sandbox_catalog(
    *,
    A: np.ndarray,
    gen_data,
    zone_loads,
    zone_gens,
    projection: ProjectionSpec,
    u_test: np.ndarray,
    xi_test: np.ndarray,
    methods_summary: Dict[str, object],
    T_z_max: np.ndarray,
) -> Dict[str, object]:
    L_base = np.load(os.path.join(EXPERIMENT_DATA_DIR, "uncertainty", "L_base.npy"))
    method_defs = {
        "box": {"type": "static", "L": np.diag(np.diag(L_base))},
        "samplecov": {"type": "static", "L": L_base.copy()},
        "staticl": {"type": "static", "L": np.load(os.path.join(MODELS_DIR, "L_static_decoupled.npy"))},
        "contextual": {"type": "nn", "model": load_context_model(os.path.join(MODELS_DIR, "nn_model_decoupled.pt"))},
    }
    coupled_defs = {
        "box": {"type": "static", "L": np.diag(np.diag(L_base))},
        "samplecov": {"type": "static", "L": L_base.copy()},
        "staticl": {"type": "static", "L": np.load(os.path.join(MODELS_DIR, "L_static_coupled.npy"))},
        "contextual": {"type": "nn", "model": load_context_model(os.path.join(MODELS_DIR, "nn_model_coupled.pt"))},
    }

    load_levels = [-1.25, 0.0, 1.25]
    solar_levels = [-0.7, 0.4, 1.9]
    wind_levels = [-0.8, 0.2, 1.6]
    hours = [0, 6, 12, 18]

    records = []
    record_id = 0
    for load_v in load_levels:
        for solar_v in solar_levels:
            for wind_v in wind_levels:
                for hour in hours:
                    ctx = encode_context(load_v, solar_v, wind_v, hour, 6)
                    local_idx = nearest_context_indices(xi_test, ctx, min(160, len(xi_test)))
                    U_local = u_test[local_idx]
                    for coupled_flag, defs, result_source in [
                        (False, method_defs, methods_summary),
                        (True, coupled_defs, methods_summary),
                    ]:
                        for method_key, cfg in defs.items():
                            if coupled_flag:
                                rho = float(result_source["methods"][method_key]["coupled_rho"])
                            else:
                                rho = float(result_source["methods"][method_key]["rho"])
                            if cfg["type"] == "static":
                                L = cfg["L"]
                            else:
                                with torch.no_grad():
                                    L = cfg["model"](torch.tensor(ctx[None, :], dtype=torch.float32)).numpy()[0]
                            record = evaluate_static_record(
                                L=L,
                                rho=rho,
                                A=A,
                                gen_data=gen_data,
                                zone_loads=zone_loads,
                                zone_gens=zone_gens,
                                projection=projection,
                                U_local=U_local,
                                coupled=coupled_flag,
                                T_z_max=T_z_max,
                            )
                            record.update(
                                {
                                    "id": record_id,
                                    "method": method_key,
                                    "coupled": coupled_flag,
                                    "context": decode_context(ctx),
                                }
                            )
                            records.append(record)
                            record_id += 1
    return {
        "tau_target": TAU,
        "projection": {
            "zones": list(projection.zone_ids),
            "labels": list(projection.labels),
        },
        "records": records,
        "default_context": {"load": 0.0, "solar": 0.4, "wind": 0.2, "hour": 12, "month": 6},
    }


def build_methods_summary(
    decoupled_results: Dict[str, object],
    coupled_results: Dict[str, object],
) -> Dict[str, object]:
    key_map = {"box": "Box", "samplecov": "SampleCov", "staticl": "StaticL", "contextual": "NN_L"}
    methods = {}
    for demo_key, exp_key in key_map.items():
        d = decoupled_results[exp_key]
        c = coupled_results[exp_key]
        methods[demo_key] = {
            "cost": d["cost"],
            "energy_cost": d.get("energy_cost", 0),
            "reserve_cost": d.get("reserve_cost", 0),
            "coverage": d.get("test_coverage", d.get("coverage", 0)),
            "rho": d["rho"],
            "reserve_total": d["reserve_total"],
            "reserves_per_zone": d["R_z_min"],
            "coupled_cost": c["cost"],
            "coupled_energy_cost": c.get("energy_cost", 0),
            "coupled_reserve_cost": c.get("reserve_cost", 0),
            "coupled_coverage": c.get("test_coverage", c.get("coverage", 0)),
            "coupled_rho": c["rho"],
            "coupled_reserve_total": c["reserve_total"],
            "coupled_reserves_per_zone": c["R_z_min"],
            "lambda_z": c.get("lambda_z", [0.0] * 10),
        }
    return {"methods": methods, "tau_target": TAU}


def build_zones():
    zone_rows = load_csv(os.path.join(EXPERIMENT_DATA_DIR, "zone_summary.csv"))
    gen_rows = load_csv(os.path.join(EXPERIMENT_DATA_DIR, "generator_data.csv"))
    metadata = load_json(os.path.join(EXPERIMENT_DATA_DIR, "uncertainty", "metadata.json"))

    gen_count = {}
    for row in gen_rows:
        zone_id = int(row["zone"])
        gen_count[zone_id] = gen_count.get(zone_id, 0) + 1

    positions = {
        1: {"x": 0.15, "y": 0.75},
        2: {"x": 0.35, "y": 0.80},
        3: {"x": 0.55, "y": 0.78},
        4: {"x": 0.75, "y": 0.72},
        5: {"x": 0.90, "y": 0.60},
        6: {"x": 0.10, "y": 0.35},
        7: {"x": 0.30, "y": 0.25},
        8: {"x": 0.50, "y": 0.22},
        9: {"x": 0.70, "y": 0.28},
        10: {"x": 0.88, "y": 0.38},
    }

    solar_zones = set(metadata.get("solar_zones", []))
    wind_zones = set(metadata.get("wind_zones", []))
    zones = []
    for row in zone_rows:
        zone_id = int(row["zone"])
        sources = ["load"]
        if zone_id in solar_zones:
            sources.append("solar")
        if zone_id in wind_zones:
            sources.append("wind")
        zones.append(
            {
                "id": zone_id,
                "name": f"Zone {zone_id}",
                "buses": row["buses"],
                "num_buses": int(row["num_buses"]),
                "load_mw": float(row["load_mw"]),
                "num_generators": gen_count.get(zone_id, 0),
                "region": metadata["zone_to_region"].get(str(zone_id), ""),
                "uncertainty_sources": sources,
                "x": positions[zone_id]["x"],
                "y": positions[zone_id]["y"],
            }
        )
    save_json(zones, os.path.join(DEMO_DATA_DIR, "zones.json"))


def build_generators():
    rows = load_csv(os.path.join(EXPERIMENT_DATA_DIR, "generator_data.csv"))
    generators = []
    for row in rows:
        generators.append(
            {
                "id": int(row["gen_id"]),
                "bus": int(row["bus"]),
                "zone": int(row["zone"]),
                "type": row["type"],
                "min_p_mw": float(row["min_p_mw"]),
                "max_p_mw": float(row["max_p_mw"]),
                "energy_cost_c2": float(row["cost_c2"]),
                "energy_cost_c1": float(row["cost_c1"]),
                "energy_cost_c0": float(row["cost_c0"]),
                "reserve_cost": float(row["reserve_cost"]),
            }
        )
    save_json(generators, os.path.join(DEMO_DATA_DIR, "generators.json"))


def build_network(A: np.ndarray, coupled_results: Dict[str, object]):
    metadata = load_json(os.path.join(EXPERIMENT_DATA_DIR, "uncertainty", "metadata.json"))
    ptdf_zone = np.load(os.path.join(EXPERIMENT_DATA_DIR, "ptdf_zone_matrix.npy"))
    network = {
        "allocation_matrix": A.tolist(),
        "allocation_shape": list(A.shape),
        "ptdf_zone_shape": list(ptdf_zone.shape),
        "n_zones": int(A.shape[0]),
        "n_uncertainty_dims": int(A.shape[1]),
        "dim_labels": metadata["dim_labels"],
        "zone_to_region": metadata["zone_to_region"],
        "regions": metadata["regions"],
        "sources": metadata["sources"],
        "context_labels": metadata["context_labels"],
        "T_z_max": coupled_results["T_z_max"],
        "tight_zones": coupled_results["tight_zones"],
    }
    save_json(network, os.path.join(DEMO_DATA_DIR, "network.json"))


def validate_story_bundle(bundle: Dict[str, object]):
    required_iter_keys = {
        "iter",
        "L_full",
        "L_2d",
        "L_next_2d",
        "rho_hat",
        "tau_target",
        "coverage_cal",
        "coverage_test",
        "score_hist_bins",
        "score_hist_counts",
        "score_cdf_x",
        "score_cdf_y",
        "reserves_per_zone",
        "reserve_total",
        "support_by_zone",
        "support_points_2d",
        "cost",
        "energy_cost",
        "reserve_cost",
        "mu_z",
        "lambda_z",
        "combined_duals",
        "grad_norm",
        "grad_shape_norm",
        "grad_rho_norm",
        "grad_2d",
        "zone_contributions",
        "shape_drift",
        "dominant_zones",
        "semi_a",
        "semi_b",
        "angle",
        "inside_mask",
    }
    for iteration in bundle["iterations"]:
        missing = required_iter_keys - set(iteration.keys())
        if missing:
            raise ValueError(f"Missing keys in {bundle['story_key']} iteration {iteration['iter']}: {sorted(missing)}")


def main():
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    print("=" * 60)
    print("GradientDemo data extraction")
    print("=" * 60)

    data = load_data()
    splits = split_data(data)
    decoupled_results = load_json(os.path.join(EXPERIMENT_DATA_DIR, "experiment_results.json"))
    coupled_results = load_json(os.path.join(EXPERIMENT_DATA_DIR, "coupled_experiment_results.json"))
    projection = build_projection_spec(data["A"])
    U_visual = choose_visual_subset(np.vstack([splits["u_cal"], splits["u_test"]]), VISUAL_SAMPLE_COUNT)

    L_cov = sample_cov_method(splits["u_train"])
    story_static = build_static_story_trace(
        title="Static L Training",
        story_key="real-static",
        L_init=L_cov,
        u_tune=splits["u_tune"],
        u_cal=splits["u_cal"],
        u_test=splits["u_test"],
        A=data["A"],
        gen_data=data["gen_data"],
        zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        projection=projection,
        U_visual=U_visual,
        n_iters=STATIC_ITERS,
        lr=1e-2,
    )
    validate_story_bundle(story_static)
    save_json(story_static, os.path.join(PRECOMPUTED_DIR, "story_static_decoupled.json"))

    story_coupled = build_static_story_trace(
        title="Static L Training (Coupled Transfers)",
        story_key="advanced-coupled",
        L_init=L_cov,
        u_tune=splits["u_tune"],
        u_cal=splits["u_cal"],
        u_test=splits["u_test"],
        A=data["A"],
        gen_data=data["gen_data"],
        zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        projection=projection,
        U_visual=U_visual,
        n_iters=STATIC_ITERS,
        lr=1e-2,
        coupled=True,
        T_z_max=np.array(coupled_results["T_z_max"], dtype=float),
    )
    validate_story_bundle(story_coupled)
    save_json(story_coupled, os.path.join(PRECOMPUTED_DIR, "story_static_coupled.json"))

    story_toy = build_toy_story()
    validate_story_bundle(story_toy)
    save_json(story_toy, os.path.join(PRECOMPUTED_DIR, "story_toy.json"))

    methods_summary = build_methods_summary(decoupled_results, coupled_results)

    nn_model = load_context_model(os.path.join(MODELS_DIR, "nn_model_decoupled.pt"))
    context_cases = build_context_cases(
        model=nn_model,
        xi_tune=splits["xi_tune"],
        u_tune=splits["u_tune"],
        xi_test=splits["xi_test"],
        u_test=splits["u_test"],
        A=data["A"],
        gen_data=data["gen_data"],
        zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        projection=projection,
    )
    save_json(context_cases, os.path.join(PRECOMPUTED_DIR, "context_cases.json"))

    sandbox_catalog = build_sandbox_catalog(
        A=data["A"],
        gen_data=data["gen_data"],
        zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        projection=projection,
        u_test=splits["u_test"],
        xi_test=splits["xi_test"],
        methods_summary=methods_summary,
        T_z_max=np.array(coupled_results["T_z_max"], dtype=float),
    )
    save_json(sandbox_catalog, os.path.join(PRECOMPUTED_DIR, "sandbox_catalog.json"))

    save_json(methods_summary, os.path.join(PRECOMPUTED_DIR, "methods.json"))

    build_zones()
    build_generators()
    build_network(data["A"], coupled_results)

    print("=" * 60)
    print("GradientDemo assets generated.")
    print("=" * 60)


if __name__ == "__main__":
    main()
