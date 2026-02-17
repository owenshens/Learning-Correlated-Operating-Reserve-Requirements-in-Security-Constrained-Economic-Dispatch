"""
Diagnostic: Compare gauge scores and ρ between StaticL and NN.

Key question: If NN learns a good L(ξ), its gauge scores s_{L(ξ)}(u) = ||L(ξ)^{-1} u||
should be well-calibrated (low variance, roughly iid), producing a LOWER ρ than StaticL.

If NN's ρ is higher → L(ξ) isn't properly adapting to context.
If NN's ρ is similar but costs are higher → issue is in reserve allocation, not calibration.
"""

import sys, os, json
import numpy as np
import torch

EXPERIMENT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, EXPERIMENT_DIR)

from sced import (
    gauge_scores_batch, compute_reserve_requirements, solve_sced,
    smoothed_quantile, conformal_calibrate, build_zone_gen_map
)
from methods import (
    sample_cov_method, train_static_L, ContextNN,
    train_context_nn, compute_scores_static, compute_scores_context,
    evaluate_method_static, evaluate_method_context
)
from tune_nn import FlexContextNN, train_nn_config, load_data, compute_scores_flex

def main():
    data = load_data()
    tau = 0.95
    d = 15

    # ── Train StaticL ──
    print("=" * 60)
    print("Training StaticL...")
    L_cov = sample_cov_method(data["u_train"])
    L_static, _ = train_static_L(
        L_init=L_cov.copy(),
        u_tune=data["u_tune"], A=data["A"],
        gen_data=data["gen_data"], zone_loads=data["zone_loads"],
        zone_gens=data["zone_gens"],
        tau=tau, eps=0.5, n_iters=200, lr=1e-2, verbose=False,
    )

    # ── Train NN initialized from L_cov (natural data scale, no trace norm) ──
    print("Training NN (initialized from L_cov, no trace normalization)...")
    model = FlexContextNN(d_context=7, d_uncertainty=d, hidden_dims=[128, 64])
    model.initialize_from_L(L_cov)
    model, hist, _ = train_nn_config(
        model=model,
        xi_tune=data["xi_tune"], u_tune=data["u_tune"],
        A=data["A"], gen_data=data["gen_data"],
        zone_loads=data["zone_loads"], zone_gens=data["zone_gens"],
        tau=tau, eps=0.5, n_iters=2000, lr=3e-4,
        batch_size=8, patience=500, verbose=False,
    )

    # ── Also train the "oracle" static L using true average covariance ──
    L_true_t = np.load(os.path.join(EXPERIMENT_DIR, "data", "uncertainty", "L_true_t.npy"))
    with open(os.path.join(EXPERIMENT_DIR, "data", "uncertainty", "metadata.json")) as f:
        meta = json.load(f)
    split = meta["split_indices"]
    L_true_cal = L_true_t[split["calibrate"][0]:split["calibrate"][1]]
    L_true_tune = L_true_t[split["tune"][0]:split["tune"][1]]

    # ── Gauge scores on calibration set ──
    print("\n" + "=" * 60)
    print("GAUGE SCORE ANALYSIS (Calibration Set)")
    print("=" * 60)

    # StaticL scores
    scores_static = compute_scores_static(L_static, data["u_cal"])
    rho_static = conformal_calibrate(scores_static, tau)

    # NN scores
    scores_nn = compute_scores_flex(model, data["xi_cal"], data["u_cal"])
    rho_nn = conformal_calibrate(scores_nn, tau)

    # SampleCov scores
    scores_cov = compute_scores_static(L_cov, data["u_cal"])
    rho_cov = conformal_calibrate(scores_cov, tau)

    # Oracle scores: use true L_t for each sample
    n_cal = len(data["u_cal"])
    scores_oracle = np.zeros(n_cal)
    for i in range(n_cal):
        v = np.linalg.solve(L_true_cal[i], data["u_cal"][i])
        scores_oracle[i] = np.linalg.norm(v)
    rho_oracle = conformal_calibrate(scores_oracle, tau)

    print(f"\n{'Method':<15} {'ρ':>8} {'Mean':>8} {'Std':>8} {'CV':>8} {'Min':>8} {'Max':>8} {'p5':>8} {'p95':>8}")
    print("-" * 85)
    for name, scores, rho in [
        ("SampleCov", scores_cov, rho_cov),
        ("StaticL", scores_static, rho_static),
        ("NN", scores_nn, rho_nn),
        ("Oracle", scores_oracle, rho_oracle),
    ]:
        print(f"{name:<15} {rho:>8.4f} {scores.mean():>8.4f} {scores.std():>8.4f} "
              f"{scores.std()/scores.mean():>8.4f} {scores.min():>8.4f} {scores.max():>8.4f} "
              f"{np.percentile(scores, 5):>8.4f} {np.percentile(scores, 95):>8.4f}")

    # ── Key insight: well-calibrated context-dependent L should reduce score variance ──
    print(f"\nKey insight: If NN properly adapts L(ξ) to context, gauge scores")
    print(f"should have LOWER variance (more uniform → iid chi-like distribution).")
    print(f"This should yield a LOWER ρ than StaticL.")
    print(f"\n  StaticL ρ = {rho_static:.4f}")
    print(f"  NN     ρ = {rho_nn:.4f}")
    print(f"  Oracle ρ = {rho_oracle:.4f}  (using true L_t per sample)")
    print(f"\n  NN ρ - StaticL ρ = {rho_nn - rho_static:+.4f}")
    print(f"  Oracle ρ - StaticL ρ = {rho_oracle - rho_static:+.4f}")

    if rho_nn > rho_static:
        print(f"\n  → NN ρ > StaticL ρ: L(ξ) is NOT well-calibrated.")
        print(f"    The NN is producing some contexts with very high gauge scores,")
        print(f"    pulling up the conformal quantile.")
    else:
        print(f"\n  → NN ρ < StaticL ρ: L(ξ) IS adapting to context.")
        print(f"    But per-context SCED costs may still be higher (Jensen's inequality).")

    # ── Gauge score distribution by quantile of context ──
    print(f"\n{'='*60}")
    print("GAUGE SCORES BY CONTEXT REGIME (Cal Set)")
    print(f"{'='*60}")

    xi_cal = data["xi_cal"]
    # Context features: col 0 = load, col 1 = solar, col 2 = wind (from generate_uncertainty.py)
    load_ctx = xi_cal[:, 0]

    # Split into low/medium/high load contexts
    load_terciles = np.percentile(load_ctx, [33, 67])
    low_mask = load_ctx <= load_terciles[0]
    mid_mask = (load_ctx > load_terciles[0]) & (load_ctx <= load_terciles[1])
    high_mask = load_ctx > load_terciles[1]

    print(f"\nLoad context terciles: ≤{load_terciles[0]:.2f}, ≤{load_terciles[1]:.2f}, >{load_terciles[1]:.2f}")
    print(f"\n{'Regime':<12} {'N':>5} {'StaticL':>10} {'NN':>10} {'Oracle':>10} {'NN-Static':>12}")
    print("-" * 60)
    for label, mask in [("Low load", low_mask), ("Mid load", mid_mask), ("High load", high_mask)]:
        n = mask.sum()
        s_stat = scores_static[mask].mean()
        s_nn = scores_nn[mask].mean()
        s_oracle = scores_oracle[mask].mean()
        print(f"{label:<12} {n:>5} {s_stat:>10.4f} {s_nn:>10.4f} {s_oracle:>10.4f} {s_nn - s_stat:>+12.4f}")

    # ── Per-context reserve cost comparison ──
    print(f"\n{'='*60}")
    print("PER-CONTEXT COST ANALYSIS (Cal Set)")
    print(f"{'='*60}")

    n_cal = len(data["u_cal"])
    costs_static_arr = np.zeros(n_cal)
    costs_nn_arr = np.zeros(n_cal)
    reserves_static_arr = np.zeros(n_cal)
    reserves_nn_arr = np.zeros(n_cal)

    model.eval()
    xi_t = torch.tensor(data["xi_cal"], dtype=torch.float32)
    with torch.no_grad():
        L_nn_all = model(xi_t).numpy()

    for i in range(n_cal):
        # StaticL
        R_z_static = compute_reserve_requirements(L_static, rho_static, data["A"])
        res_s = solve_sced(R_z_static, data["gen_data"], data["zone_loads"], data["zone_gens"])
        costs_static_arr[i] = res_s['cost'] if res_s['feasible'] else np.inf
        reserves_static_arr[i] = R_z_static.sum()

        # NN
        R_z_nn = compute_reserve_requirements(L_nn_all[i], rho_nn, data["A"])
        res_n = solve_sced(R_z_nn, data["gen_data"], data["zone_loads"], data["zone_gens"])
        costs_nn_arr[i] = res_n['cost'] if res_n['feasible'] else np.inf
        reserves_nn_arr[i] = R_z_nn.sum()

    # Note: StaticL cost is the same for all contexts (constant L, constant R_z)
    print(f"\n  StaticL: constant reserves → one SCED cost = ${costs_static_arr[0]:.2f}")
    print(f"  StaticL total reserve: {reserves_static_arr[0]:.1f} MW")
    print(f"\n  NN: per-context reserves")
    print(f"    Mean cost:    ${costs_nn_arr.mean():.2f}")
    print(f"    Min cost:     ${costs_nn_arr.min():.2f}")
    print(f"    Max cost:     ${costs_nn_arr.max():.2f}")
    print(f"    Std cost:     ${costs_nn_arr.std():.2f}")
    print(f"    Mean reserve: {reserves_nn_arr.mean():.1f} MW")
    print(f"    Min reserve:  {reserves_nn_arr.min():.1f} MW")
    print(f"    Max reserve:  {reserves_nn_arr.max():.1f} MW")
    print(f"    Std reserve:  {reserves_nn_arr.std():.1f} MW")
    print(f"    Reserve CV:   {reserves_nn_arr.std()/reserves_nn_arr.mean():.4f}")

    nn_cheaper = (costs_nn_arr < costs_static_arr[0]).sum()
    print(f"\n  Contexts where NN is cheaper: {nn_cheaper}/{n_cal} ({100*nn_cheaper/n_cal:.1f}%)")
    print(f"  Mean savings when cheaper: ${(costs_static_arr[0] - costs_nn_arr[costs_nn_arr < costs_static_arr[0]]).mean():.2f}" if nn_cheaper > 0 else "")
    nn_costlier_mask = costs_nn_arr > costs_static_arr[0]
    nn_costlier = nn_costlier_mask.sum()
    print(f"  Contexts where NN is costlier: {nn_costlier}/{n_cal} ({100*nn_costlier/n_cal:.1f}%)")
    if nn_costlier > 0:
        print(f"  Mean excess when costlier: ${(costs_nn_arr[nn_costlier_mask] - costs_static_arr[0]).mean():.2f}")

    # ── How much does NN vary L(ξ)? ──
    print(f"\n{'='*60}")
    print("NN L(ξ) VARIATION ANALYSIS")
    print(f"{'='*60}")

    L_frob_norms = np.array([np.linalg.norm(L_nn_all[i], 'fro') for i in range(n_cal)])
    L_diag_sums = np.array([np.diag(L_nn_all[i]).sum() for i in range(n_cal)])

    # How much does L(ξ) actually change across contexts?
    L_mean = L_nn_all.mean(axis=0)
    L_diffs = np.array([np.linalg.norm(L_nn_all[i] - L_mean, 'fro') for i in range(n_cal)])

    print(f"  Frobenius norm of L(ξ): mean={L_frob_norms.mean():.4f}, std={L_frob_norms.std():.4f}, CV={L_frob_norms.std()/L_frob_norms.mean():.4f}")
    print(f"  Diag sum of L(ξ): mean={L_diag_sums.mean():.4f}, std={L_diag_sums.std():.4f}, CV={L_diag_sums.std()/L_diag_sums.mean():.4f}")
    print(f"  ||L(ξ) - E[L(ξ)]||_F: mean={L_diffs.mean():.4f}, max={L_diffs.max():.4f}")
    print(f"  Relative variation: {L_diffs.mean() / np.linalg.norm(L_mean, 'fro'):.4f}")

    # Compare with true L_t variation
    L_true_mean = L_true_cal.mean(axis=0)
    L_true_diffs = np.array([np.linalg.norm(L_true_cal[i] - L_true_mean, 'fro') for i in range(n_cal)])
    print(f"\n  True L_t variation:")
    print(f"  ||L_true(ξ) - E[L_true(ξ)]||_F: mean={L_true_diffs.mean():.4f}, max={L_true_diffs.max():.4f}")
    print(f"  Relative variation: {L_true_diffs.mean() / np.linalg.norm(L_true_mean, 'fro'):.4f}")

    print(f"\n  NN variation / True variation = {L_diffs.mean() / L_true_diffs.mean():.4f}")
    if L_diffs.mean() / L_true_diffs.mean() < 0.5:
        print(f"  → NN is barely varying L(ξ) — essentially learning a static L!")
        print(f"  → This explains why ρ_{'{NN}'} ≈ ρ_{'{static}'}: NN hasn't found the context signal.")
    elif L_diffs.mean() / L_true_diffs.mean() > 2.0:
        print(f"  → NN is over-varying L(ξ) — noise in the mapping increases ρ.")
    else:
        print(f"  → NN variation is in reasonable range relative to truth.")


if __name__ == "__main__":
    main()
