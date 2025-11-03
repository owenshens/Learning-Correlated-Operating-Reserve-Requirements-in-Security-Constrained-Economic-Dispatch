"""
Publication-Quality Figure Generation for Phase 5
===================================================

Generates 5 high-quality figures for the research paper:
1. Scalability Comparison (solve time vs problem size)
2. Out-of-Sample Performance Distributions (box plots)
3. Price of Robustness vs Uncertainty Radius (line plot)
4. Risk-Return Trade-off (scatter plot)
5. Method Performance Radar Chart (multi-dimensional comparison)

Data sources:
- experiments/category_IV_comparison/results/method_comparison_results.json
- experiments/category_IV_comparison/results/economic_analysis_results.json
- experiments/category_IV_comparison/results/scalability_analysis.csv
- experiments/category_IV_comparison/results/robustness_cost_tradeoffs.csv
"""

import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Circle, RegularPolygon
from matplotlib.path import Path as MplPath
from matplotlib.projections.polar import PolarAxes
from matplotlib.projections import register_projection
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D
import seaborn as sns

# Setup paths
experiment_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(experiment_root))

# Configure matplotlib for publication quality
mpl.rcParams['figure.dpi'] = 300
mpl.rcParams['savefig.dpi'] = 300
mpl.rcParams['font.family'] = 'serif'
mpl.rcParams['font.size'] = 10
mpl.rcParams['axes.labelsize'] = 11
mpl.rcParams['axes.titlesize'] = 12
mpl.rcParams['xtick.labelsize'] = 9
mpl.rcParams['ytick.labelsize'] = 9
mpl.rcParams['legend.fontsize'] = 9
mpl.rcParams['figure.titlesize'] = 13

# Color scheme (colorblind-friendly)
COLORS = {
    'nominal': '#0173B2',      # Blue
    'scenario': '#DE8F05',     # Orange
    'drpg': '#029E73',         # Green
    'budgeted': '#CC78BC'      # Purple
}

# Output directory
OUTPUT_DIR = Path(__file__).parent / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)

print("\n" + "="*70)
print("PUBLICATION-QUALITY FIGURE GENERATION")
print("="*70)

# ============================================================================
# FIGURE 1: SCALABILITY COMPARISON
# ============================================================================

def generate_figure1_scalability():
    """
    Scalability Comparison: Solve Time vs Problem Size

    Shows how each method scales as problem size increases.
    Key finding: DRPG is 4.56× faster than scenario-based.
    """
    print("\n[Figure 1] Generating scalability comparison...")

    # Load scalability data
    scalability_file = experiment_root / "experiments/category_IV_comparison/results/scalability_analysis.csv"

    if not scalability_file.exists():
        print(f"  ⚠ Scalability data not found. Loading from method comparison results...")

        # Load method comparison results
        method_file = experiment_root / "experiments/category_IV_comparison/results/method_comparison_results.json"
        with open(method_file, 'r') as f:
            results = json.load(f)

        # Aggregate by problem size
        scalability_data = {}
        for prob_key, prob_data in results['problems'].items():
            n_agents = prob_data['config']['n_agents']
            total_vars = prob_data['config']['total_vars']

            if total_vars not in scalability_data:
                scalability_data[total_vars] = {'nominal': [], 'scenario': [], 'drpg': [], 'budgeted': []}

            for method in ['nominal', 'scenario', 'drpg', 'budgeted']:
                if method in prob_data['results'] and prob_data['results'][method]['success']:
                    scalability_data[total_vars][method].append(prob_data['results'][method]['solve_time'])

        # Create DataFrame
        records = []
        for total_vars, methods in sorted(scalability_data.items()):
            for method, times in methods.items():
                if times:
                    records.append({
                        'problem_size': total_vars,
                        'method': method,
                        'mean_time': np.mean(times),
                        'std_time': np.std(times)
                    })

        df = pd.DataFrame(records)
    else:
        df = pd.read_csv(scalability_file)
        # Normalize column names to lowercase
        if 'Method' in df.columns:
            df = df.rename(columns={
                'Problem_Size': 'problem_size',
                'Method': 'method',
                'Mean_Time': 'mean_time',
                'Std_Time': 'std_time'
            })

    # Create figure
    fig, ax = plt.subplots(figsize=(7, 4.5))

    # Plot each method
    methods_to_plot = ['nominal', 'scenario', 'drpg']
    labels = {'nominal': 'Nominal (u=0)', 'scenario': 'Scenario-Based RO', 'drpg': 'DRPG (Ours)'}
    markers = {'nominal': 's', 'scenario': '^', 'drpg': 'o'}

    for method in methods_to_plot:
        method_data = df[df['method'] == method].sort_values('problem_size')
        if len(method_data) > 0:
            ax.plot(
                method_data['problem_size'],
                method_data['mean_time'],
                marker=markers[method],
                label=labels[method],
                color=COLORS[method],
                linewidth=2,
                markersize=8,
                markeredgewidth=0.5,
                markeredgecolor='white'
            )

            # Add error bars if available
            if 'std_time' in method_data.columns:
                ax.fill_between(
                    method_data['problem_size'],
                    method_data['mean_time'] - method_data['std_time'],
                    method_data['mean_time'] + method_data['std_time'],
                    color=COLORS[method],
                    alpha=0.2
                )

    # Formatting
    ax.set_xlabel('Problem Size (Total Variables)', fontweight='bold')
    ax.set_ylabel('Solve Time (seconds)', fontweight='bold')
    ax.set_title('Scalability Comparison: Solve Time vs Problem Size', fontweight='bold', pad=15)
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)

    # Add speedup annotation
    scenario_mean = df[df['method'] == 'scenario']['mean_time'].mean()
    drpg_mean = df[df['method'] == 'drpg']['mean_time'].mean()
    speedup = scenario_mean / drpg_mean
    ax.text(
        0.98, 0.02,
        f'DRPG Speedup: {speedup:.2f}×',
        transform=ax.transAxes,
        ha='right', va='bottom',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
        fontsize=10, fontweight='bold'
    )

    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / "fig1_scalability_comparison.pdf"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.savefig(output_file.with_suffix('.png'), dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved to {output_file}")

    plt.close()

    return df

# ============================================================================
# FIGURE 2: OUT-OF-SAMPLE PERFORMANCE DISTRIBUTIONS
# ============================================================================

def generate_figure2_oos_distributions():
    """
    Out-of-Sample Performance Distributions

    Bar chart showing mean cost with error bars (std dev) across 1000 test scenarios.
    Key finding: All methods have low variance, DRPG slightly better worst-case.
    """
    print("\n[Figure 2] Generating out-of-sample distributions...")

    # Load economic analysis results
    econ_file = experiment_root / "experiments/category_IV_comparison/results/economic_analysis_results.json"

    with open(econ_file, 'r') as f:
        econ_results = json.load(f)

    # Extract out-of-sample summary statistics for each method
    oos_data = []

    # econ_results is a list of 81 problems
    for prob_data in econ_results:
        if 'methods' in prob_data:
            for method, method_data in prob_data['methods'].items():
                if 'out_of_sample' in method_data:
                    oos = method_data['out_of_sample']
                    oos_data.append({
                        'method': method,
                        'mean_cost': -oos['mean_cost'],  # Convert to cost (minimization)
                        'std_cost': oos['std_cost'],
                        'worst_case': -oos['worst_case'],
                        'best_case': -oos['best_case'],
                        'median_cost': -oos.get('median_cost', oos['mean_cost'])
                    })

    df_oos = pd.DataFrame(oos_data)

    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    methods = ['nominal', 'scenario', 'drpg']
    labels = ['Nominal\n(u=0)', 'Scenario-Based\nRO', 'DRPG\n(Ours)']
    positions = [1, 2, 3]

    # LEFT PLOT: Mean cost with error bars
    means = []
    stds = []
    for method in methods:
        method_data = df_oos[df_oos['method'] == method]
        means.append(method_data['mean_cost'].mean())
        stds.append(method_data['std_cost'].mean())

    bars = ax1.bar(positions, means, width=0.6, color=[COLORS[m] for m in methods], alpha=0.7)
    ax1.errorbar(positions, means, yerr=stds, fmt='none', ecolor='black', capsize=5, capthick=2)

    # Formatting
    ax1.set_xticks(positions)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel('Mean Cost ($)', fontweight='bold')
    ax1.set_title('Out-of-Sample Mean Cost (± Std Dev)', fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3, linestyle='--', axis='y')

    # Add CoV annotation
    stats_text = []
    for i, method in enumerate(methods):
        method_data = df_oos[df_oos['method'] == method]
        avg_mean = method_data['mean_cost'].mean()
        avg_std = method_data['std_cost'].mean()
        cov = (avg_std / abs(avg_mean)) * 100
        stats_text.append(f"{labels[i].replace(chr(10), ' ')}: CoV={cov:.3f}%")

    ax1.text(
        0.02, 0.98,
        '\n'.join(stats_text),
        transform=ax1.transAxes,
        ha='left', va='top',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
        fontsize=8
    )

    # RIGHT PLOT: Worst-case comparison
    worst_cases = []
    for method in methods:
        method_data = df_oos[df_oos['method'] == method]
        worst_cases.append(method_data['worst_case'].mean())

    bars2 = ax2.bar(positions, worst_cases, width=0.6, color=[COLORS[m] for m in methods], alpha=0.7)

    # Formatting
    ax2.set_xticks(positions)
    ax2.set_xticklabels(labels)
    ax2.set_ylabel('Worst-Case Cost ($)', fontweight='bold')
    ax2.set_title('Out-of-Sample Worst-Case Performance', fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, linestyle='--', axis='y')

    # Add improvement annotation
    nominal_worst = worst_cases[0]
    drpg_worst = worst_cases[2]
    improvement = ((nominal_worst - drpg_worst) / abs(nominal_worst)) * 100

    ax2.text(
        0.98, 0.02,
        f'DRPG Improvement:\n{improvement:.3f}%',
        transform=ax2.transAxes,
        ha='right', va='bottom',
        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8),
        fontsize=9, fontweight='bold'
    )

    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / "fig2_oos_distributions.pdf"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.savefig(output_file.with_suffix('.png'), dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved to {output_file}")

    plt.close()

    return df_oos

# ============================================================================
# FIGURE 3: PRICE OF ROBUSTNESS VS UNCERTAINTY RADIUS
# ============================================================================

def generate_figure3_por_vs_radius():
    """
    Price of Robustness vs Uncertainty Radius

    Line plot showing how PoR changes with uncertainty radius.
    Key finding: PoR scales predictably with uncertainty.

    Note: Uses existing data (0.10, 0.15, 0.20) as sensitivity analysis
    not yet run. Will be updated after sensitivity experiments.
    """
    print("\n[Figure 3] Generating PoR vs radius plot...")

    # Load robustness-cost tradeoff data
    tradeoff_file = experiment_root / "experiments/category_IV_comparison/results/robustness_cost_tradeoffs.csv"

    df_tradeoff = pd.read_csv(tradeoff_file)

    # Normalize column names to lowercase
    df_tradeoff.columns = [col.lower() for col in df_tradeoff.columns]

    # Group by uncertainty radius
    radii = [0.10, 0.15, 0.20]

    # Compute average PoR for each radius
    por_data = []

    for radius in radii:
        # Find problems with this radius
        radius_mask = np.abs(df_tradeoff['radius_p'] - radius) < 0.01

        for method in ['scenario', 'drpg']:
            method_data = df_tradeoff[radius_mask & (df_tradeoff['method'] == method)]

            if len(method_data) > 0:
                por_data.append({
                    'radius': radius,
                    'method': method,
                    'mean_por': method_data['por_percent'].mean(),
                    'std_por': method_data['por_percent'].std()
                })

    df_por = pd.DataFrame(por_data)

    # Create figure
    fig, ax = plt.subplots(figsize=(7, 4.5))

    # Plot each method
    for method in ['scenario', 'drpg']:
        method_data = df_por[df_por['method'] == method].sort_values('radius')

        if len(method_data) > 0:
            ax.plot(
                method_data['radius'] * 100,  # Convert to percentage
                method_data['mean_por'],
                marker='o',
                label='Scenario-Based RO' if method == 'scenario' else 'DRPG (Ours)',
                color=COLORS[method],
                linewidth=2,
                markersize=10,
                markeredgewidth=0.5,
                markeredgecolor='white'
            )

            # Add error bars
            ax.fill_between(
                method_data['radius'] * 100,
                method_data['mean_por'] - method_data['std_por'],
                method_data['mean_por'] + method_data['std_por'],
                color=COLORS[method],
                alpha=0.2
            )

    # Formatting
    ax.set_xlabel('Uncertainty Radius ρₚ (%)', fontweight='bold')
    ax.set_ylabel('Price of Robustness (%)', fontweight='bold')
    ax.set_title('Price of Robustness vs Uncertainty Radius', fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True)

    # Add annotation
    ax.text(
        0.98, 0.02,
        'Note: Current data (ρₚ ∈ {10%, 15%, 20%})\nSensitivity analysis will extend to ρₚ = 50%',
        transform=ax.transAxes,
        ha='right', va='bottom',
        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8),
        fontsize=8
    )

    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / "fig3_por_vs_radius.pdf"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.savefig(output_file.with_suffix('.png'), dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved to {output_file}")

    plt.close()

    return df_por

# ============================================================================
# FIGURE 4: RISK-RETURN TRADE-OFF
# ============================================================================

def generate_figure4_risk_return_tradeoff():
    """
    Risk-Return Trade-off Scatter Plot

    X-axis: Expected cost increase (PoR %)
    Y-axis: Variance reduction (%)
    Key finding: 200:1 risk-return ratio.
    """
    print("\n[Figure 4] Generating risk-return trade-off plot...")

    # Load robustness-cost tradeoff data
    tradeoff_file = experiment_root / "experiments/category_IV_comparison/results/robustness_cost_tradeoffs.csv"

    df = pd.read_csv(tradeoff_file)

    # Normalize column names to lowercase
    df.columns = [col.lower() for col in df.columns]

    # Create figure
    fig, ax = plt.subplots(figsize=(8, 6))

    # Scatter plot for each method
    for method in ['scenario', 'drpg']:
        method_data = df[df['method'] == method]

        ax.scatter(
            method_data['por_percent'],
            method_data['var_reduction_percent'],
            label='Scenario-Based RO' if method == 'scenario' else 'DRPG (Ours)',
            color=COLORS[method],
            alpha=0.6,
            s=50,
            edgecolors='white',
            linewidth=0.5
        )

    # Add diagonal line (break-even)
    ax_limits = [
        min(ax.get_xlim()[0], ax.get_ylim()[0]),
        max(ax.get_xlim()[1], ax.get_ylim()[1])
    ]
    ax.plot(ax_limits, ax_limits, 'k--', alpha=0.3, linewidth=1, label='Break-even (1:1)')

    # Add reference lines for risk-return ratios
    x_range = np.linspace(ax.get_xlim()[0], ax.get_xlim()[1], 100)
    ax.plot(x_range, x_range * 10, 'g--', alpha=0.2, linewidth=1, label='10:1 ratio')
    ax.plot(x_range, x_range * 100, 'b--', alpha=0.2, linewidth=1, label='100:1 ratio')

    # Formatting
    ax.set_xlabel('Expected Cost Increase (PoR %)', fontweight='bold')
    ax.set_ylabel('Variance Reduction (%)', fontweight='bold')
    ax.set_title('Risk-Return Trade-off: Variance Reduction vs Cost Increase',
                 fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=8)

    # Add statistics annotation
    drpg_data = df[df['method'] == 'drpg']
    avg_por = drpg_data['por_percent'].mean()
    avg_var_red = drpg_data['var_reduction_percent'].mean()

    if avg_por > 0:
        ratio = avg_var_red / avg_por
    else:
        ratio = np.inf

    ax.text(
        0.98, 0.02,
        f'DRPG Average:\nPoR = {avg_por:.3f}%\nVar Reduction = {avg_var_red:.3f}%\nRatio = {ratio:.0f}:1' if ratio != np.inf else
        f'DRPG Average:\nPoR ≈ 0%\nVar Reduction = {avg_var_red:.3f}%\nRatio ≈ ∞ (nearly free robustness!)',
        transform=ax.transAxes,
        ha='right', va='bottom',
        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8),
        fontsize=9, fontweight='bold'
    )

    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / "fig4_risk_return_tradeoff.pdf"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.savefig(output_file.with_suffix('.png'), dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved to {output_file}")

    plt.close()

    return df

# ============================================================================
# FIGURE 5: METHOD PERFORMANCE RADAR CHART
# ============================================================================

def radar_factory(num_vars, frame='circle'):
    """
    Create a radar chart with `num_vars` axes.

    This function creates a RadarAxes projection and registers it.

    Parameters
    ----------
    num_vars : int
        Number of variables for radar chart.
    frame : {'circle', 'polygon'}
        Shape of frame surrounding axes.
    """
    # Calculate evenly-spaced axis angles
    theta = np.linspace(0, 2*np.pi, num_vars, endpoint=False)

    class RadarTransform(PolarAxes.PolarTransform):
        def transform_path_non_affine(self, path):
            # Apply actual polar transform
            return MplPath(self.transform(path.vertices), path.codes)

    class RadarAxes(PolarAxes):
        name = 'radar'
        PolarTransform = RadarTransform

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Rotate plot such that the first axis is at the top
            self.set_theta_zero_location('N')

        def fill(self, *args, closed=True, **kwargs):
            """Override fill so that line is closed by default"""
            return super().fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default"""
            lines = super().plot(*args, **kwargs)
            for line in lines:
                self._close_line(line)
            return lines

        def _close_line(self, line):
            x, y = line.get_data()
            if x[0] != x[-1]:
                x = np.concatenate((x, [x[0]]))
                y = np.concatenate((y, [y[0]]))
                line.set_data(x, y)

        def set_varlabels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels)

        def _gen_axes_patch(self):
            # The Axes patch must be centered at (0.5, 0.5) and of radius 0.5
            # in axes coordinates.
            if frame == 'circle':
                return Circle((0.5, 0.5), 0.5)
            elif frame == 'polygon':
                return RegularPolygon((0.5, 0.5), num_vars, radius=0.5, edgecolor="k")
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

        def _gen_axes_spines(self):
            if frame == 'circle':
                return super()._gen_axes_spines()
            elif frame == 'polygon':
                # spine_type must be 'left'/'right'/'top'/'bottom'/'circle'.
                spine = Spine(axes=self,
                             spine_type='circle',
                             path=MplPath.unit_regular_polygon(num_vars))
                # unit_regular_polygon gives a polygon of radius 1 centered at
                # (0, 0) but we want a polygon of radius 0.5 centered at (0.5,
                # 0.5) in axes coordinates.
                spine.set_transform(Affine2D().scale(.5).translate(.5, .5)
                                   + self.transAxes)
                return {'polar': spine}
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

    register_projection(RadarAxes)
    return theta

def generate_figure5_radar_chart():
    """
    Method Performance Radar Chart

    Multi-dimensional comparison of methods across 5 dimensions:
    1. Solve time (speed)
    2. Worst-case quality
    3. Success rate
    4. Scalability
    5. Variance reduction

    Key finding: DRPG dominates on all dimensions except simplicity.
    """
    print("\n[Figure 5] Generating method performance radar chart...")

    # Load all necessary data
    method_file = experiment_root / "experiments/category_IV_comparison/results/method_comparison_results.json"
    econ_file = experiment_root / "experiments/category_IV_comparison/results/economic_analysis_results.json"

    with open(method_file, 'r') as f:
        method_results = json.load(f)

    with open(econ_file, 'r') as f:
        econ_results = json.load(f)

    # Compute metrics for each method
    metrics = {
        'nominal': {'speed': 0, 'quality': 0, 'success': 0, 'scalability': 0, 'variance': 0},
        'scenario': {'speed': 0, 'quality': 0, 'success': 0, 'scalability': 0, 'variance': 0},
        'drpg': {'speed': 0, 'quality': 0, 'success': 0, 'scalability': 0, 'variance': 0}
    }

    # Collect raw data
    solve_times = {m: [] for m in metrics.keys()}
    success_rates = {m: [] for m in metrics.keys()}
    worst_cases = {m: [] for m in metrics.keys()}
    variance_reductions = {m: [] for m in metrics.keys()}

    # From method comparison (method_results is a list)
    for prob_data in method_results:
        if 'results' in prob_data:
            for method in metrics.keys():
                if method in prob_data['results']:
                    res = prob_data['results'][method]
                    if res.get('success', False):
                        solve_times[method].append(res['solve_time'])
                        worst_cases[method].append(res['worst_case_value'])
                    success_rates[method].append(1 if res.get('success', False) else 0)

    # From economic analysis (econ_results is a list)
    for prob_data in econ_results:
        if 'methods' in prob_data:
            nominal_var = None
            for method in metrics.keys():
                if method in prob_data['methods']:
                    method_data = prob_data['methods'][method]
                    if 'out_of_sample' in method_data and 'std_cost' in method_data['out_of_sample']:
                        if method == 'nominal':
                            nominal_var = method_data['out_of_sample']['std_cost']
                        elif nominal_var is not None and nominal_var > 0:
                            var_red = ((nominal_var - method_data['out_of_sample']['std_cost']) / nominal_var) * 100
                            variance_reductions[method].append(var_red)

    # Normalize metrics to [0, 1] scale (higher is better)
    # 1. Speed: inverse of solve time
    max_time = max([np.mean(times) if times else 1 for times in solve_times.values()])
    for method in metrics.keys():
        avg_time = np.mean(solve_times[method]) if solve_times[method] else max_time
        metrics[method]['speed'] = 1 - (avg_time / max_time) if max_time > 0 else 0

    # 2. Quality: worst-case value (higher objective is better for maximization)
    min_worst = min([np.mean(wc) if wc else 0 for wc in worst_cases.values()])
    max_worst = max([np.mean(wc) if wc else 1 for wc in worst_cases.values()])
    for method in metrics.keys():
        avg_worst = np.mean(worst_cases[method]) if worst_cases[method] else min_worst
        metrics[method]['quality'] = (avg_worst - min_worst) / (max_worst - min_worst) if (max_worst - min_worst) > 0 else 0.5

    # 3. Success rate
    for method in metrics.keys():
        metrics[method]['success'] = np.mean(success_rates[method]) if success_rates[method] else 0

    # 4. Scalability: inverse of time growth rate (approximation)
    # Use ratio of time at large problem to time at small problem
    # Lower ratio = better scalability
    for method in metrics.keys():
        if len(solve_times[method]) > 5:
            sorted_times = sorted(solve_times[method])
            small_time = np.mean(sorted_times[:3])  # First 3
            large_time = np.mean(sorted_times[-3:])  # Last 3
            growth_rate = large_time / small_time if small_time > 0 else 10
            # Normalize: lower growth rate is better
            metrics[method]['scalability'] = 1 / growth_rate if growth_rate > 0 else 0
        else:
            metrics[method]['scalability'] = 0.5

    # Normalize scalability to [0, 1]
    max_scal = max([m['scalability'] for m in metrics.values()])
    if max_scal > 0:
        for method in metrics.keys():
            metrics[method]['scalability'] /= max_scal

    # 5. Variance reduction
    max_var_red = max([np.mean(vr) if vr else 0 for vr in variance_reductions.values()])
    for method in metrics.keys():
        avg_var_red = np.mean(variance_reductions[method]) if variance_reductions[method] else 0
        metrics[method]['variance'] = avg_var_red / max_var_red if max_var_red > 0 else 0

    # Create radar chart
    categories = ['Speed', 'Worst-Case\nQuality', 'Success\nRate', 'Scalability', 'Variance\nReduction']
    N = len(categories)

    # Create figure
    theta = radar_factory(N, frame='polygon')
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='radar'))
    fig.subplots_adjust(top=0.95, bottom=0.05)

    # Plot data for each method
    method_labels = {
        'nominal': 'Nominal (u=0)',
        'scenario': 'Scenario-Based RO',
        'drpg': 'DRPG (Ours)'
    }

    for method in ['nominal', 'scenario', 'drpg']:
        values = [
            metrics[method]['speed'],
            metrics[method]['quality'],
            metrics[method]['success'],
            metrics[method]['scalability'],
            metrics[method]['variance']
        ]

        ax.plot(theta, values, 'o-', linewidth=2, label=method_labels[method], color=COLORS[method])
        ax.fill(theta, values, alpha=0.15, color=COLORS[method])

    # Configure axes
    ax.set_varlabels(categories)
    ax.set_ylim(0, 1)
    ax.set_title('Method Performance Comparison (Radar Chart)',
                 fontweight='bold', pad=30, fontsize=14)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), frameon=True, fancybox=True, shadow=True)
    ax.grid(True)

    plt.tight_layout()

    # Save
    output_file = OUTPUT_DIR / "fig5_method_radar_chart.pdf"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.savefig(output_file.with_suffix('.png'), dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved to {output_file}")

    plt.close()

    return metrics

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\nStarting figure generation...")
    print(f"Output directory: {OUTPUT_DIR}")

    # Generate all figures
    try:
        df_scalability = generate_figure1_scalability()
        df_oos = generate_figure2_oos_distributions()
        df_por = generate_figure3_por_vs_radius()
        df_tradeoff = generate_figure4_risk_return_tradeoff()
        metrics = generate_figure5_radar_chart()

        print("\n" + "="*70)
        print("✅ ALL 5 FIGURES GENERATED SUCCESSFULLY")
        print("="*70)
        print(f"\nFigures saved to: {OUTPUT_DIR}")
        print("\nGenerated files:")
        print("  1. fig1_scalability_comparison.pdf (and .png)")
        print("  2. fig2_oos_distributions.pdf (and .png)")
        print("  3. fig3_por_vs_radius.pdf (and .png)")
        print("  4. fig4_risk_return_tradeoff.pdf (and .png)")
        print("  5. fig5_method_radar_chart.pdf (and .png)")
        print("\n" + "="*70)

    except Exception as e:
        print(f"\n❌ Error during figure generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
