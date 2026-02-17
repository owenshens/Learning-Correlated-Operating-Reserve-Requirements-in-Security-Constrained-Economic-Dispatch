#!/usr/bin/env python3
"""
Main Experiment Runner
======================

Command-line interface for running experiments.

Usage:
    python run_experiment.py --help
    python run_experiment.py I.1  # Run specific experiment
    python run_experiment.py --category I  # Run all Category I experiments
    python run_experiment.py --all  # Run all experiments
"""

import argparse
import sys
import time
from pathlib import Path

# Add experiment directory to path
sys.path.insert(0, str(Path(__file__).parent))


def run_experiment_I1():
    """Category I.1: Envelope Theorem Verification"""
    print("\n" + "="*70)
    print("EXPERIMENT I.1: ENVELOPE THEOREM VERIFICATION")
    print("="*70)

    try:
        from experiments.category_I_theoretical import exp_I1_envelope_verification
        exp_I1_envelope_verification.main()
        return True
    except ImportError as e:
        print(f"ERROR: Experiment I.1 not yet implemented: {e}")
        return False


def run_experiment_I2():
    """Category I.2: Dual Penalty Equivalence"""
    print("\n" + "="*70)
    print("EXPERIMENT I.2: DUAL PENALTY EQUIVALENCE")
    print("="*70)

    try:
        from experiments.category_I_theoretical import exp_I2_dual_equivalence
        exp_I2_dual_equivalence.main()
        return True
    except ImportError as e:
        print(f"ERROR: Experiment I.2 not yet implemented: {e}")
        return False


def run_experiment_II1():
    """Category II.1: DRPG Convergence Rates"""
    print("\n" + "="*70)
    print("EXPERIMENT II.1: DRPG CONVERGENCE RATES")
    print("="*70)

    try:
        from experiments.category_II_convergence import exp_II1_drpg_convergence
        exp_II1_drpg_convergence.main()
        return True
    except ImportError as e:
        print(f"ERROR: Experiment II.1 not yet implemented: {e}")
        return False


def run_experiment_II2():
    """Category II.2: PRDA Convergence Rates"""
    print("\n" + "="*70)
    print("EXPERIMENT II.2: PRDA CONVERGENCE RATES")
    print("="*70)

    try:
        from experiments.category_II_convergence import exp_II2_prda_convergence
        exp_II2_prda_convergence.main()
        return True
    except ImportError as e:
        print(f"ERROR: Experiment II.2 not yet implemented: {e}")
        return False


def run_category_I():
    """Run all Category I experiments"""
    print("\n" + "#"*70)
    print("CATEGORY I: THEORETICAL VALIDATION")
    print("#"*70)

    results = []
    results.append(("I.1", run_experiment_I1()))
    results.append(("I.2", run_experiment_I2()))

    return results


def run_category_II():
    """Run all Category II experiments"""
    print("\n" + "#"*70)
    print("CATEGORY II: CONVERGENCE RATES")
    print("#"*70)

    results = []
    results.append(("II.1", run_experiment_II1()))
    results.append(("II.2", run_experiment_II2()))

    return results


def run_all_experiments():
    """Run all available experiments"""
    print("\n" + "#"*70)
    print("RUNNING ALL EXPERIMENTS")
    print("#"*70)

    start_time = time.time()
    all_results = []

    # Category I
    all_results.extend(run_category_I())

    # Category II
    all_results.extend(run_category_II())

    # TODO: Add other categories as implemented

    total_time = time.time() - start_time

    # Summary
    print("\n" + "="*70)
    print("EXPERIMENT SUMMARY")
    print("="*70)

    n_success = sum(1 for _, success in all_results if success)
    n_total = len(all_results)

    for exp_name, success in all_results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {exp_name}: {status}")

    print(f"\nTotal: {n_success}/{n_total} passed")
    print(f"Time: {total_time:.1f}s")
    print("="*70)

    return all_results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run robust optimization experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s I.1                 Run experiment I.1
  %(prog)s --category I        Run all Category I experiments
  %(prog)s --all               Run all experiments
  %(prog)s --list              List all available experiments
        """
    )

    parser.add_argument(
        'experiment',
        nargs='?',
        help='Experiment to run (e.g., I.1, II.2)'
    )

    parser.add_argument(
        '--category',
        choices=['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX'],
        help='Run all experiments in category'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all experiments'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available experiments'
    )

    args = parser.parse_args()

    # List experiments
    if args.list:
        print("\nAvailable experiments:")
        print("  Category I (Theoretical Validation):")
        print("    I.1  - Envelope Theorem Verification")
        print("    I.2  - Dual Penalty Equivalence")
        print("  Category II (Convergence Rates):")
        print("    II.1 - DRPG Convergence")
        print("    II.2 - PRDA Convergence")
        print("\n(More experiments will be added as implemented)")
        return 0

    # Run all
    if args.all:
        results = run_all_experiments()
        n_success = sum(1 for _, success in results if success)
        return 0 if n_success == len(results) else 1

    # Run category
    if args.category:
        if args.category == 'I':
            results = run_category_I()
        elif args.category == 'II':
            results = run_category_II()
        else:
            print(f"ERROR: Category {args.category} not yet implemented")
            return 1

        n_success = sum(1 for _, success in results if success)
        return 0 if n_success == len(results) else 1

    # Run specific experiment
    if args.experiment:
        exp_map = {
            'I.1': run_experiment_I1,
            'I.2': run_experiment_I2,
            'II.1': run_experiment_II1,
            'II.2': run_experiment_II2,
        }

        if args.experiment in exp_map:
            success = exp_map[args.experiment]()
            return 0 if success else 1
        else:
            print(f"ERROR: Unknown experiment '{args.experiment}'")
            print("Run with --list to see available experiments")
            return 1

    # No arguments - show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
