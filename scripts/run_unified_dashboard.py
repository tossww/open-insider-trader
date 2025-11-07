#!/usr/bin/env python3
"""
Launch script for Unified Dashboard.

Combines parameter tuning with live backtest results.
"""

import sys
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dashboard.unified_dashboard import run_unified_dashboard


def main():
    parser = argparse.ArgumentParser(
        description='Launch Unified Dashboard for Open InsiderTrader'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8052,
        help='Port to bind to (default: 8052)'
    )
    parser.add_argument(
        '--no-debug',
        action='store_true',
        help='Disable debug mode'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🎯 UNIFIED DASHBOARD - Open InsiderTrader")
    print("=" * 80)
    print(f"\n🌐 Starting server at http://{args.host}:{args.port}")
    print("\nFeatures:")
    print("  • Adjust filtering parameters with sliders")
    print("  • See live backtest results as you tune")
    print("  • Compare performance across holding periods")
    print("  • Visual equity curves and metrics")
    print("  • Find optimal settings for real signal generation")
    print("\n💡 How it works:")
    print("  1. Adjust the parameter sliders")
    print("  2. Click 'Update Results' button")
    print("  3. Dashboard re-filters and re-backtests instantly")
    print("  4. See how performance changes with different settings")
    print("\n" + "=" * 80)
    print("Press Ctrl+C to stop the server\n")

    run_unified_dashboard(
        host=args.host,
        port=args.port,
        debug=not args.no_debug
    )


if __name__ == '__main__':
    main()
