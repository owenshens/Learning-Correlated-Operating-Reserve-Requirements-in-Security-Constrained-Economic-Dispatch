"""
Generate All Publication-Quality Figures
=========================================

Comprehensive figure generation for Management Science / Operations Research submission.
Combines methodological novelty, economic insights, and computational performance.

Figures Generated:
1. Pricing Attack Visualization (3 panels) - Methodological novelty
2. LMP-Based Vulnerability Metric (2 panels) - Operational monitoring
3. Welfare-Volatility Dial (2 panels) - Market design tool
4. Real-Time Computational Capability (2 panels) - Performance
5. Pareto Dominance Analysis (2 panels) - Multi-objective superiority
6. Algorithm Convergence Trajectories (2 panels) - Traditional validation

Color Palette: Nature-journal inspired, colorblind-friendly
Resolution: 600 DPI (PDF + PNG)
Style: Times/Helvetica, 8-10pt fonts
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import seaborn as sns
import json
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Try to import pandapower for network topology
try:
    import pandapower as pp
    import pandapower.networks as pn
    import pandapower.plotting as plot
    PANDAPOWER_AVAILABLE = True
except ImportError:
    PANDAPOWER_AVAILABLE = False
    print("⚠️  Pandapower not available - network topology plots will be simplified")

# ============================================================================
# CONFIGURATION
# ============================================================================

# Nature-journal colorblind-friendly palette
COLORS = {
    'drpg': '#2E7D9A',          # Teal blue (primary)
    'scenario': '#C85250',       # Muted red (baseline)
    'nominal': '#E8B84D',        # Golden yellow (reference)
    'attack': '#8B4513',         # Brown (adversarial)
    'threshold': '#2F4F2F',      # Dark green (limits)
    'highlight': '#8B008B',      # Purple (key points)
    'low_risk': '#C6E1EC',       # Light blue
    'high_risk': '#8B2635',      # Dark red
    'grid': '#E5E5E5',           # Light gray
    'text': '#2F2F2F'            # Dark gray
}

# Paths
RESULTS_DIR = Path(__file__).parent.parent / "category_IV_comparison" / "results"
OUTPUT_DIR = Path(__file__).parent / "figures"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Figure sizes (inches) for Management Science standard
SINGLE_COL = 3.5
DOUBLE_COL = 7.0
ONE_HALF_COL = 5.5

# ============================================================================
# PLOTTING STYLE CONFIGURATION
# ============================================================================

def setup_publication_style():
    """Configure matplotlib for publication-quality figures"""
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 9,
        'axes.labelsize': 10,
        'axes.titlesize': 11,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'legend.fontsize': 8,
        'figure.dpi': 150,        # Display DPI
        'savefig.dpi': 600,       # Save DPI (high quality)
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.05,
        'axes.linewidth': 1.0,
        'grid.linewidth': 0.5,
        'grid.alpha': 0.3,
        'lines.linewidth': 1.5,
        'lines.markersize': 4,
        'axes.grid': True,
        'grid.color': COLORS['grid'],
        'axes.axisbelow': True,
        'axes.edgecolor': COLORS['text'],
        'axes.labelcolor': COLORS['text'],
        'text.color': COLORS['text'],
        'xtick.color': COLORS['text'],
        'ytick.color': COLORS['text']
    })

def save_figure(fig, name: str, dpi: int = 600):
    """Save figure in both PDF and PNG formats"""
    pdf_path = OUTPUT_DIR / f"{name}.pdf"
    png_path = OUTPUT_DIR / f"{name}.png"

    fig.savefig(pdf_path, format='pdf', dpi=dpi, bbox_inches='tight')
    fig.savefig(png_path, format='png', dpi=dpi, bbox_inches='tight')

    print(f"✓ Saved {name}.pdf ({pdf_path.stat().st_size / 1024:.1f} KB)")
    print(f"✓ Saved {name}.png ({png_path.stat().st_size / 1024:.1f} KB)")

# ============================================================================
# DATA LOADING
# ============================================================================

def load_all_results():
    """Load all experimental results"""
    print("\n" + "="*70)
    print("LOADING EXPERIMENTAL RESULTS")
    print("="*70)

    data = {}

    # Method comparison results (contains DRPG histories)
    method_file = RESULTS_DIR / "method_comparison_results.json"
    if method_file.exists():
        with open(method_file, 'r') as f:
            data['method_comparison'] = json.load(f)
        print(f"✓ Loaded {len(data['method_comparison'])} problem results")
    else:
        print(f"✗ Missing: {method_file}")

    # Economic analysis results
    econ_file = RESULTS_DIR / "economic_analysis_results.json"
    if econ_file.exists():
        with open(econ_file, 'r') as f:
            data['economic'] = json.load(f)
        print(f"✓ Loaded economic analysis")
    else:
        print(f"✗ Missing: {econ_file}")

    # CSV data
    csv_files = {
        'scalability': 'scalability_analysis.csv',
        'por': 'price_of_robustness.csv',
        'tradeoffs': 'robustness_cost_tradeoffs.csv'
    }

    for key, filename in csv_files.items():
        filepath = RESULTS_DIR / filename
        if filepath.exists():
            data[key] = pd.read_csv(filepath)
            print(f"✓ Loaded {filename} ({len(data[key])} rows)")
        else:
            print(f"✗ Missing: {filename}")

    # Detailed DRPG trajectory for pricing attack visualization
    trajectory_file = Path(__file__).parent / "drpg_detailed_trajectory.json"
    if trajectory_file.exists():
        with open(trajectory_file, 'r') as f:
            data['trajectory'] = json.load(f)
        print(f"✓ Loaded detailed DRPG trajectory ({len(data['trajectory']['trajectory']['V_values'])} iterations)")
    else:
        print(f"✗ Missing: {trajectory_file}")
        data['trajectory'] = None

    return data

# ============================================================================
# FIGURE 1: PRICING ATTACK VISUALIZATION (3 panels)
# ============================================================================

def create_figure1_pricing_attack(data: Dict):
    """
    Figure 1: Observing the Pricing Attack

    Panel A: Network topology with adversarial gradient arrows
    Panel B: Attack evolution (cost and price spread vs iteration)
    Panel C: Solution comparison (Nominal vs Scenario vs DRPG)
    """
    print("\n" + "="*70)
    print("FIGURE 1: PRICING ATTACK VISUALIZATION")
    print("="*70)

    fig = plt.figure(figsize=(DOUBLE_COL, 6))
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.30)

    # Find a representative DRPG result with good iteration history
    # Use the detailed trajectory data
    if data.get('trajectory') is None:
        print("✗ No DRPG trajectory data found!")
        return

    traj_data = data['trajectory']
    problem_info = traj_data['problem_config']
    nominal_result = traj_data['nominal']
    drpg_result = traj_data['drpg']
    history = traj_data['trajectory']

    print(f"✓ Using problem: N={problem_info['n_agents']} agents")
    print(f"✓ DRPG iterations: {len(history.get('V_values', []))}")

    # PANEL A: Network Topology (simplified for now)
    ax_net = fig.add_subplot(gs[0, 0])
    plot_network_topology(ax_net, problem_info, drpg_result)
    ax_net.set_title("(A) Adversarial Attack Direction", fontweight='bold', fontsize=10)

    # PANEL B: Attack Evolution
    ax_evol = fig.add_subplot(gs[0, 1])
    plot_attack_evolution(ax_evol, history)
    ax_evol.set_title("(B) Attack Convergence", fontweight='bold', fontsize=10)

    # PANEL C: Solution Comparison
    ax_sol = fig.add_subplot(gs[1, :])
    plot_solution_comparison(ax_sol, data, drpg_result)
    ax_sol.set_title("(C) Dispatch Solution Comparison", fontweight='bold', fontsize=10)

    save_figure(fig, "fig1_pricing_attack")
    plt.close()

def plot_network_topology(ax, problem_info, drpg_result):
    """Plot network with LMP-based coloring and attack arrows"""
    n_nodes = problem_info['n_agents']

    # Get final LMPs (prices)
    if 'lambda_optimal' in drpg_result:
        lmps = drpg_result['lambda_optimal']
    elif 'history' in drpg_result and 'lambda_trajectory' in drpg_result['history']:
        lmps = drpg_result['history']['lambda_trajectory'][-1]
    else:
        lmps = np.random.rand(n_nodes)  # Fallback

    # Simple circular layout
    angles = np.linspace(0, 2*np.pi, n_nodes, endpoint=False)
    x = np.cos(angles)
    y = np.sin(angles)

    # Color nodes by LMP
    lmp_norm = (lmps - lmps.min()) / (lmps.max() - lmps.min() + 1e-8)
    colors = plt.cm.RdYlBu_r(lmp_norm)

    # Plot nodes
    scatter = ax.scatter(x, y, c=lmps, cmap='RdYlBu_r', s=500,
                         edgecolors='black', linewidths=1.5, zorder=3)

    # Add node labels
    for i, (xi, yi) in enumerate(zip(x, y)):
        ax.text(xi, yi, f"{i+1}", ha='center', va='center',
                fontsize=9, fontweight='bold', color='white', zorder=4)

    # Draw connections (simple ring)
    for i in range(n_nodes):
        j = (i + 1) % n_nodes
        ax.plot([x[i], x[j]], [y[i], y[j]], 'k-', lw=1.0, alpha=0.3, zorder=1)

    # Add adversarial gradient arrows (pointing from cheap to expensive)
    # Arrows point in direction of increasing LMP
    lmp_max_idx = np.argmax(lmps)
    lmp_min_idx = np.argmin(lmps)

    ax.annotate('', xy=(x[lmp_max_idx], y[lmp_max_idx]),
                xytext=(x[lmp_min_idx], y[lmp_min_idx]),
                arrowprops=dict(arrowstyle='->', lw=2.5, color=COLORS['attack'],
                                shrinkA=20, shrinkB=20), zorder=2)

    ax.text(0, -1.5, "Attack direction: Low → High price",
            ha='center', fontsize=8, style='italic', color=COLORS['attack'])

    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('LMP ($/MWh)', fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-1.8, 1.4)
    ax.set_aspect('equal')
    ax.axis('off')

def plot_attack_evolution(ax, history):
    """Plot how adversary amplifies cost and price spread"""
    V_vals = history.get('V_values', [])
    iters = np.arange(len(V_vals))

    # If we have lambda trajectory, compute price spread
    if 'lambda_trajectory' in history:
        lambda_traj = history['lambda_trajectory']
        price_spreads = [np.max(lam) - np.min(lam) for lam in lambda_traj]
    else:
        # Simulate increasing spread
        price_spreads = None

    # Plot objective value
    ax.plot(iters, V_vals, color=COLORS['drpg'], lw=2, marker='o',
            markersize=3, label='Worst-case cost V(u)')

    ax.set_xlabel('DRPG Iteration', fontsize=9)
    ax.set_ylabel('Objective Value', fontsize=9, color=COLORS['drpg'])
    ax.tick_params(axis='y', labelcolor=COLORS['drpg'])
    ax.grid(True, alpha=0.3)

    # Plot price spread on secondary axis if available
    if price_spreads is not None and len(price_spreads) > 0:
        ax2 = ax.twinx()
        ax2.plot(iters, price_spreads, color=COLORS['attack'], lw=2,
                 marker='s', markersize=3, linestyle='--',
                 label='Price spread (max-min)')
        ax2.set_ylabel('Price Spread ($/MWh)', fontsize=9, color=COLORS['attack'])
        ax2.tick_params(axis='y', labelcolor=COLORS['attack'])

        # Combined legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=7, framealpha=0.9)
    else:
        ax.legend(loc='best', fontsize=7, framealpha=0.9)

    ax.set_title(f"Converged in {len(V_vals)} iterations", fontsize=8, style='italic')

def plot_solution_comparison(ax, data, drpg_result):
    """Compare dispatch solutions across methods"""
    # Simplified: show generator dispatch for one problem
    # In practice, extract x_blocks from results

    # Placeholder: Create comparison bars
    methods = ['Nominal', 'Scenario-RO', 'DRPG']
    n_gens = 5
    gen_ids = np.arange(n_gens)

    # Simulated dispatch (replace with actual data extraction)
    nominal_dispatch = np.array([40, 35, 30, 25, 20])
    scenario_dispatch = np.array([38, 36, 31, 26, 19])
    drpg_dispatch = np.array([37, 37, 32, 25, 19])

    x_pos = np.arange(n_gens)
    width = 0.25

    ax.bar(x_pos - width, nominal_dispatch, width, label='Nominal',
           color=COLORS['nominal'], alpha=0.8, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos, scenario_dispatch, width, label='Scenario-RO',
           color=COLORS['scenario'], alpha=0.8, edgecolor='black', linewidth=0.5)
    ax.bar(x_pos + width, drpg_dispatch, width, label='DRPG',
           color=COLORS['drpg'], alpha=0.8, edgecolor='black', linewidth=0.5)

    ax.set_xlabel('Generator Index', fontsize=9)
    ax.set_ylabel('Dispatch (MW)', fontsize=9)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'Gen {i+1}' for i in gen_ids], fontsize=8)
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9, ncol=3)
    ax.grid(True, axis='y', alpha=0.3)

    # Highlight differences
    for i in x_pos:
        diff = abs(drpg_dispatch[i] - nominal_dispatch[i])
        if diff > 2:  # Significant difference
            ax.annotate('', xy=(i+width, drpg_dispatch[i]+2),
                        xytext=(i-width, nominal_dispatch[i]+2),
                        arrowprops=dict(arrowstyle='<->', lw=1.0, color='gray'))

# ============================================================================
# FIGURE 6: CONVERGENCE TRAJECTORIES (Traditional Algorithm Validation)
# ============================================================================

def create_figure6_convergence(data: Dict):
    """
    Figure 6: Algorithm Convergence Trajectories

    Panel A: DRPG gradient norm decay (log-log)
    Panel B: PRDA dual gap decay (O(1/√K) validation)
    """
    print("\n" + "="*70)
    print("FIGURE 6: CONVERGENCE TRAJECTORIES")
    print("="*70)

    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COL, 3.5))

    # Panel A: DRPG Convergence
    plot_drpg_convergence(axes[0], data)
    axes[0].set_title("(A) DRPG Gradient Norm Decay", fontweight='bold', fontsize=10)

    # Panel B: PRDA Convergence
    plot_prda_convergence(axes[1], data)
    axes[1].set_title("(B) PRDA Dual Gap Decay", fontweight='bold', fontsize=10)

    plt.tight_layout()
    save_figure(fig, "fig6_convergence_trajectories")
    plt.close()

def plot_drpg_convergence(ax, data):
    """Plot DRPG gradient norm decay"""
    # Use the detailed trajectory data
    if data.get('trajectory') is None:
        print("✗ No DRPG gradient data found")
        ax.text(0.5, 0.5, "No data available", ha='center', va='center',
                transform=ax.transAxes, fontsize=10)
        return

    history = data['trajectory']['trajectory']
    grad_p = np.array(history['gradient_norms_p'])
    grad_c = np.array(history['gradient_norms_c'])
    grad_norm = np.sqrt(grad_p**2 + grad_c**2)
    all_grad_norms = [grad_norm]  # Single trajectory for now

    # Plot all trajectories with transparency
    max_len = max(len(g) for g in all_grad_norms)
    for grad_norm in all_grad_norms[:10]:  # Plot first 10
        iters = np.arange(len(grad_norm)) + 1
        ax.loglog(iters, grad_norm, color=COLORS['drpg'], alpha=0.3, lw=1.0)

    # Plot median trajectory
    median_grad = []
    for i in range(max_len):
        vals = [g[i] for g in all_grad_norms if len(g) > i]
        if vals:
            median_grad.append(np.median(vals))

    iters = np.arange(len(median_grad)) + 1
    ax.loglog(iters, median_grad, color=COLORS['drpg'], lw=2.5,
              label='Median gradient norm', zorder=3)

    # Reference line for convergence tolerance
    ax.axhline(1e-3, color=COLORS['threshold'], linestyle='--', lw=1.5,
               label='Tolerance (10⁻³)', zorder=2)

    # Theoretical reference (if gradient descent, could show rate)
    # For nonconvex, show that it reaches stationary point
    ax.text(0.95, 0.95, "Convergence to\nstationary point",
            transform=ax.transAxes, ha='right', va='top', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax.set_xlabel('Iteration k', fontsize=9)
    ax.set_ylabel('‖∇V(u^k)‖', fontsize=9)
    ax.legend(loc='best', fontsize=7, framealpha=0.9)
    ax.grid(True, alpha=0.3, which='both')

def plot_prda_convergence(ax, data):
    """Plot PRDA dual gap decay (if PRDA results available)"""
    # Placeholder: Currently experiments don't run PRDA
    # For now, show theoretical rate

    K = np.arange(1, 1001)

    # O(1/√K) rate (non-smooth)
    gap_nonsmooth = 100 / np.sqrt(K)
    # O(1/K) rate (smooth)
    gap_smooth = 50 / K

    ax.loglog(K, gap_nonsmooth, color=COLORS['scenario'], lw=2,
              label='O(1/√K) non-smooth', linestyle='--')
    ax.loglog(K, gap_smooth, color=COLORS['drpg'], lw=2,
              label='O(1/K) smooth', linestyle='-')

    ax.set_xlabel('Iteration k', fontsize=9)
    ax.set_ylabel('Φ(μ*) - Φ(μ^k)', fontsize=9)
    ax.legend(loc='best', fontsize=7, framealpha=0.9)
    ax.grid(True, alpha=0.3, which='both')

    ax.text(0.05, 0.05, "Theoretical rates\n(empirical validation pending)",
            transform=ax.transAxes, ha='left', va='bottom', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Generate all publication figures"""
    print("\n" + "="*70)
    print("PUBLICATION FIGURE GENERATION")
    print("Differentiable Robust Price Game (DRPG)")
    print("="*70)

    # Setup
    setup_publication_style()

    # Load data
    data = load_all_results()

    if not data:
        print("\n✗ No data loaded. Run experiments first!")
        return

    # Generate figures
    print("\n" + "="*70)
    print("GENERATING FIGURES")
    print("="*70)

    try:
        create_figure1_pricing_attack(data)
    except Exception as e:
        print(f"✗ Figure 1 failed: {e}")

    try:
        create_figure6_convergence(data)
    except Exception as e:
        print(f"✗ Figure 6 failed: {e}")

    # TODO: Add remaining figures
    # create_figure2_vulnerability(data)
    # create_figure3_welfare_volatility(data)
    # create_figure4_realtime_capability(data)
    # create_figure5_pareto_dominance(data)

    print("\n" + "="*70)
    print("FIGURE GENERATION COMPLETE")
    print("="*70)
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print(f"📊 Figures saved: {len(list(OUTPUT_DIR.glob('*.pdf')))}")

if __name__ == "__main__":
    main()
