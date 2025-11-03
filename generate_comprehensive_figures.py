"""
Generate Comprehensive Publication Figures with Corrected Scaling
================================================================

Creates all publication-ready visualizations from corrected experimental results.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import seaborn as sns
import json
from pathlib import Path

# Nature-journal colorblind-friendly palette
COLORS = {
    'drpg': '#2E7D9A',          # Teal blue
    'scenario': '#C85250',       # Muted red
    'budgeted': '#E8B84D',       # Golden yellow
    'nominal': '#95A5A6',        # Gray
    'grid': '#E5E5E5',
    'text': '#2F2F2F'
}

# Publication style
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 150,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.color': COLORS['grid'],
})

# Paths
RESULTS_DIR = Path("experiments/category_IV_comparison/results")
OUTPUT_DIR = Path("experiments/comprehensive_figures")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

print("="*80)
print("COMPREHENSIVE FIGURE GENERATION (CORRECTED RESULTS)")
print("="*80)

# Load data
print("\nLoading experimental results...")
with open(RESULTS_DIR / "method_comparison_results.json") as f:
    results = json.load(f)
print(f"✓ Loaded {len(results)} experiments")

scalability = pd.read_csv(RESULTS_DIR / "scalability_analysis.csv")
por_data = pd.read_csv(RESULTS_DIR / "price_of_robustness.csv")

# ============================================================================
# FIGURE 1: Scalability Analysis
# ============================================================================
print("\nGenerating Figure 1: Scalability...")

fig, axes = plt.subplots(1, 2, figsize=(7, 3))

# Panel A: Solve time by problem size
ax = axes[0]
for method in ['nominal', 'scenario', 'budgeted', 'drpg']:
    method_data = scalability[scalability['Method'] == method]
    if len(method_data) > 0:
        color = COLORS[method.lower()]
        ax.plot(method_data['Problem_Size'], method_data['Mean_Time'],
                'o-', label=method.capitalize(), color=color, linewidth=2, markersize=6)
        ax.fill_between(method_data['Problem_Size'],
                        method_data['Mean_Time'] - method_data['Std_Time'],
                        method_data['Mean_Time'] + method_data['Std_Time'],
                        alpha=0.2, color=color)

ax.set_xlabel('Problem Size (N agents)')
ax.set_ylabel('Solve Time (s)')
ax.set_title('(A) Computational Performance')
ax.legend(loc='best', framealpha=0.9)
ax.set_yscale('log')

# Panel B: Success rates
ax = axes[1]
success_rates = []
for method in ['Nominal', 'Scenario', 'Budgeted', 'Drpg']:
    converged = sum(1 for exp in results
                    if method.lower() in exp['results']
                    and exp['results'][method.lower()].get('converged', False))
    total = sum(1 for exp in results if method.lower() in exp['results'])
    rate = 100 * converged / total if total > 0 else 0
    success_rates.append({'Method': method, 'Success Rate': rate})

success_df = pd.DataFrame(success_rates)
bars = ax.bar(success_df['Method'], success_df['Success Rate'],
              color=[COLORS[m.lower()] for m in success_df['Method']])
ax.set_ylabel('Success Rate (%)')
ax.set_title('(B) Convergence Reliability')
ax.set_ylim([0, 105])
ax.axhline(y=95, color='red', linestyle='--', linewidth=1, alpha=0.5, label='95% threshold')
ax.legend()

for bar, rate in zip(bars, success_df['Success Rate']):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{rate:.1f}%', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "fig1_scalability_success.pdf")
plt.savefig(OUTPUT_DIR / "fig1_scalability_success.png")
print(f"✓ Saved Figure 1")
plt.close()

# ============================================================================
# FIGURE 2: Price of Robustness Analysis
# ============================================================================
print("\nGenerating Figure 2: Price of Robustness...")

fig, axes = plt.subplots(1, 2, figsize=(7, 3))

# Panel A: PoR distribution by method
ax = axes[0]
por_by_method = []
for method in ['Scenario', 'Budgeted', 'Drpg']:
    method_por = por_data[por_data['Method'] == method.lower()]['PoR_Percent']
    if len(method_por) > 0:
        por_by_method.append(method_por)

bp = ax.boxplot(por_by_method, tick_labels=['Scenario', 'Budgeted', 'DRPG'],
                patch_artist=True)
for patch, method in zip(bp['boxes'], ['scenario', 'budgeted', 'drpg']):
    patch.set_facecolor(COLORS[method])
    patch.set_alpha(0.7)

ax.set_ylabel('Price of Robustness (%)')
ax.set_title('(A) PoR Distribution by Method')
ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax.axhline(y=1, color='red', linestyle='--', linewidth=1, alpha=0.5, label='1% threshold')
ax.legend()

# Panel B: PoR vs uncertainty radius
ax = axes[1]
por_by_radius = por_data.groupby(['Radius_P', 'Method'])['PoR_Percent'].mean().reset_index()
for method in ['scenario', 'budgeted', 'drpg']:
    method_data = por_by_radius[por_by_radius['Method'] == method]
    if len(method_data) > 0:
        ax.plot(method_data['Radius_P'], method_data['PoR_Percent'],
                'o-', label=method.capitalize(), color=COLORS[method],
                linewidth=2, markersize=6)

ax.set_xlabel('Objective Uncertainty Radius (ρ_p)')
ax.set_ylabel('Mean PoR (%)')
ax.set_title('(B) PoR vs Uncertainty Level')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "fig2_price_of_robustness.pdf")
plt.savefig(OUTPUT_DIR / "fig2_price_of_robustness.png")
print(f"✓ Saved Figure 2")
plt.close()

# ============================================================================
# FIGURE 3: Method Comparison Summary
# ============================================================================
print("\nGenerating Figure 3: Method Comparison...")

fig, axes = plt.subplots(1, 3, figsize=(10, 3))

# Aggregate statistics
stats = []
for method in ['nominal', 'scenario', 'budgeted', 'drpg']:
    times = []
    objectives = []
    for exp in results:
        if method in exp['results'] and exp['results'][method].get('converged', False):
            times.append(exp['results'][method]['solve_time'])
            objectives.append(-exp['results'][method]['objective'])  # Negate for profit

    if len(times) > 0:
        stats.append({
            'Method': method.capitalize(),
            'Mean Time': np.mean(times),
            'Mean Objective': np.mean(objectives),
            'Success': 100 * len(times) / sum(1 for e in results if method in e['results'])
        })

stats_df = pd.DataFrame(stats)

# Panel A: Average solve time
ax = axes[0]
bars = ax.bar(stats_df['Method'], stats_df['Mean Time'],
              color=[COLORS[m.lower()] for m in stats_df['Method']])
ax.set_ylabel('Mean Solve Time (s)')
ax.set_title('(A) Computational Efficiency')
ax.set_yscale('log')
for bar, time in zip(bars, stats_df['Mean Time']):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height * 1.2,
            f'{time:.2f}s', ha='center', va='bottom', fontsize=8, rotation=0)

# Panel B: Average objective value
ax = axes[1]
ax.bar(stats_df['Method'], stats_df['Mean Objective'],
       color=[COLORS[m.lower()] for m in stats_df['Method']])
ax.set_ylabel('Mean Objective ($)')
ax.set_title('(B) Solution Quality')
ax.ticklabel_format(style='plain', axis='y')

# Panel C: Trade-off (time vs objective)
ax = axes[2]
for i, row in stats_df.iterrows():
    ax.scatter(row['Mean Time'], row['Mean Objective'],
               s=200, color=COLORS[row['Method'].lower()],
               label=row['Method'], alpha=0.7, edgecolors='black', linewidth=1)

ax.set_xlabel('Mean Solve Time (s)')
ax.set_ylabel('Mean Objective ($)')
ax.set_title('(C) Efficiency-Quality Trade-off')
ax.set_xscale('log')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "fig3_method_comparison.pdf")
plt.savefig(OUTPUT_DIR / "fig3_method_comparison.png")
print(f"✓ Saved Figure 3")
plt.close()

# ============================================================================
# FIGURE 4: Speedup Analysis
# ============================================================================
print("\nGenerating Figure 4: Speedup Analysis...")

fig, ax = plt.subplots(1, 1, figsize=(6, 4))

# Calculate speedups relative to scenario-based RO
speedups = []
for size in [5, 10, 20]:
    scenario_time = scalability[(scalability['Problem_Size'] == size) &
                                 (scalability['Method'] == 'scenario')]['Mean_Time'].values
    drpg_time = scalability[(scalability['Problem_Size'] == size) &
                            (scalability['Method'] == 'drpg')]['Mean_Time'].values

    if len(scenario_time) > 0 and len(drpg_time) > 0:
        speedup = scenario_time[0] / drpg_time[0]
        speedups.append({'Size': size, 'Speedup': speedup})

speedup_df = pd.DataFrame(speedups)

bars = ax.bar(speedup_df['Size'], speedup_df['Speedup'],
              color=COLORS['drpg'], alpha=0.7, edgecolor='black', linewidth=1.5)
ax.axhline(y=1, color='red', linestyle='--', linewidth=2, label='Breakeven (1×)')
ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

# Add speedup/slowdown labels
for bar, row in zip(bars, speedups):
    height = bar.get_height()
    if height > 1:
        label = f'{height:.1f}× faster'
        va = 'bottom'
        y_pos = height + 0.1
    else:
        label = f'{1/height:.1f}× slower'
        va = 'top'
        y_pos = height - 0.1

    ax.text(bar.get_x() + bar.get_width()/2., y_pos,
            label, ha='center', va=va, fontsize=10, fontweight='bold')

ax.set_xlabel('Problem Size (N agents)')
ax.set_ylabel('Speedup vs Scenario-Based RO')
ax.set_title('DRPG Speedup Analysis (Corrected Results)')
ax.set_xticks(speedup_df['Size'])
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "fig4_speedup_analysis.pdf")
plt.savefig(OUTPUT_DIR / "fig4_speedup_analysis.png")
print(f"✓ Saved Figure 4")
plt.close()

# ============================================================================
# Summary Statistics Table
# ============================================================================
print("\nGenerating summary table...")

summary = pd.DataFrame({
    'Method': stats_df['Method'],
    'Mean Time (s)': stats_df['Mean Time'].round(3),
    'Success Rate (%)': stats_df['Success'].round(1),
    'Mean Objective ($)': stats_df['Mean Objective'].round(2)
})

# Calculate PoR for each method
por_means = []
for method in ['Nominal', 'Scenario', 'Budgeted', 'Drpg']:
    if method == 'Nominal':
        por_means.append(0.00)
    else:
        method_por = por_data[por_data['Method'] == method.lower()]['PoR_Percent']
        por_means.append(method_por.mean() if len(method_por) > 0 else np.nan)

summary['Mean PoR (%)'] = por_means

print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)
print(summary.to_string(index=False))

summary.to_csv(OUTPUT_DIR / "summary_statistics.csv", index=False)

print("\n" + "="*80)
print("✅ COMPREHENSIVE FIGURE GENERATION COMPLETE")
print("="*80)
print(f"\n📁 Output directory: {OUTPUT_DIR.absolute()}")
print(f"📊 Generated 4 figures (PDF + PNG)")
print(f"📋 Generated 1 summary table (CSV)")

print("\n" + "="*80)
print("KEY FINDINGS (CORRECTED)")
print("="*80)
print(f"✓ Mean PoR: {por_data[por_data['Method']=='drpg']['PoR_Percent'].mean():.2f}% (realistic!)")
print(f"✓ DRPG success rate: {stats_df[stats_df['Method']=='Drpg']['Success'].values[0]:.1f}%")
print(f"✓ Speedup (N=5): {speedups[0]['Speedup']:.2f}× faster")
print(f"✓ Speedup (N=10): {1/speedups[1]['Speedup']:.2f}× slower (trade-off)")
print(f"✓ Speedup (N=20): {1/speedups[2]['Speedup']:.2f}× slower (trade-off)")
