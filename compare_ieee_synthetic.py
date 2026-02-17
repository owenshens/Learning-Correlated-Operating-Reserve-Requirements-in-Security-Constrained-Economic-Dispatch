"""
Compare IEEE-Calibrated vs Synthetic Problems
==============================================

Generate statistics comparing IEEE-calibrated problems with synthetic ones.
"""

import sys
import numpy as np
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from core.ieee_problem_generator import (
    generate_ieee_calibrated_qp,
    compare_ieee_vs_synthetic_statistics
)

def main():
    """Generate comparison statistics for all IEEE cases."""
    print("\n" + "="*70)
    print("IEEE vs SYNTHETIC PROBLEM COMPARISON")
    print("="*70)

    results = {}

    for case_name in ['case30', 'case57', 'case118']:
        print(f"\n{'-'*70}")
        print(f"Comparing {case_name}")
        print('-'*70)

        # Generate comparison
        comparison = compare_ieee_vs_synthetic_statistics(
            ieee_case=case_name,
            seed=42
        )

        ieee_stats = comparison['ieee']
        synth_stats = comparison['synthetic']

        print(f"\nProblem dimensions:")
        print(f"  IEEE  : {ieee_stats['n_agents']} agents, {ieee_stats['n_vars_total']} vars, {ieee_stats['n_resources']} constraints")
        print(f"  Synth : {synth_stats['n_agents']} agents, {synth_stats['n_vars_total']} vars, {synth_stats['n_resources']} constraints")

        print(f"\nCost structure:")
        print(f"  IEEE  linear cost: ${ieee_stats['cost_linear_mean']:.2f} ± ${ieee_stats['cost_linear_std']:.2f}")
        print(f"  Synth linear cost: ${synth_stats['cost_linear_mean']:.2f} ± ${synth_stats['cost_linear_std']:.2f}")
        print(f"  IEEE  max quad eigenvalue: {ieee_stats['cost_quadratic_max_eig']:.4f}")
        print(f"  Synth max quad eigenvalue: {synth_stats['cost_quadratic_max_eig']:.4f}")

        print(f"\nConstraint structure:")
        print(f"  IEEE  constraint Frobenius: {ieee_stats['constraint_frobenius_mean']:.4f}")
        print(f"  Synth constraint Frobenius: {synth_stats['constraint_frobenius_mean']:.4f}")
        print(f"  IEEE  RHS norm: {ieee_stats['rhs_norm']:.2f}")
        print(f"  Synth RHS norm: {synth_stats['rhs_norm']:.2f}")

        print(f"\nUncertainty structure:")
        print(f"  IEEE  P mean Frobenius: {ieee_stats['uncertainty_P_mean']:.4f}")
        print(f"  Synth P mean Frobenius: {synth_stats['uncertainty_P_mean']:.4f}")
        print(f"  IEEE  B Frobenius: {ieee_stats['uncertainty_B_norm']:.4f}")
        print(f"  Synth B Frobenius: {synth_stats['uncertainty_B_norm']:.4f}")

        # Store results
        results[case_name] = comparison

    # Save comparison
    output_file = Path(__file__).parent / 'results' / 'ieee_synthetic_comparison.json'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        # Convert numpy arrays to lists for JSON serialization
        serializable_results = {}
        for case_name, comp in results.items():
            serializable_results[case_name] = {
                'ieee': comp['ieee'],
                'synthetic': comp['synthetic']
            }
        json.dump(serializable_results, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✅ Comparison complete!")
    print(f"Results saved to: {output_file}")
    print(f"{'='*70}\n")

    # Generate summary table
    print("\nSUMMARY TABLE:")
    print("="*70)
    print(f"{'Case':<12} {'Type':<8} {'Agents':<8} {'Vars':<8} {'Cost $/MWh':<15} {'Robust?':<8}")
    print("-"*70)

    for case_name in ['case30', 'case57', 'case118']:
        comp = results[case_name]
        ieee_stats = comp['ieee']
        synth_stats = comp['synthetic']

        print(f"{case_name:<12} {'IEEE':<8} {ieee_stats['n_agents']:<8} {ieee_stats['n_vars_total']:<8} " +
              f"${ieee_stats['cost_linear_mean']:.1f} ± {ieee_stats['cost_linear_std']:.1f}    {'Yes':<8}")
        print(f"{'  (matched)':<12} {'Synth':<8} {synth_stats['n_agents']:<8} {synth_stats['n_vars_total']:<8} " +
              f"${synth_stats['cost_linear_mean']:.1f} ± {synth_stats['cost_linear_std']:.1f}    {'Yes':<8}")
        print()

    print("="*70)

if __name__ == '__main__':
    main()
