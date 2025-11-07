#!/usr/bin/env python3
"""
Launch script for Parameter Tuning Dashboard.

Usage:
    python3 scripts/run_param_tuner.py
    python3 scripts/run_param_tuner.py --port 8051
    python3 scripts/run_param_tuner.py --host 0.0.0.0 --port 8051
"""

import sys
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dashboard.param_tuner import run_param_tuner


def main():
    parser = argparse.ArgumentParser(
        description='Launch Parameter Tuning Dashboard for Open InsiderTrader'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8051,
        help='Port to bind to (default: 8051)'
    )
    parser.add_argument(
        '--no-debug',
        action='store_true',
        help='Disable debug mode'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🎛️  PARAMETER TUNING DASHBOARD - Open InsiderTrader")
    print("=" * 80)
    print(f"\n🌐 Starting server at http://{args.host}:{args.port}")
    print("\nFeatures:")
    print("  • Adjust filtering parameters with sliders")
    print("  • Toggle executive level filters")
    print("  • Live signal count preview")
    print("  • Visual funnel showing filtering stages")
    print("  • Export results to CSV")
    print("  • One-click backtest launch")
    print("\n" + "=" * 80)
    print("Press Ctrl+C to stop the server\n")

    run_param_tuner(
        host=args.host,
        port=args.port,
        debug=not args.no_debug
    )


if __name__ == '__main__':
    main()
