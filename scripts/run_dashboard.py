#!/usr/bin/env python3
"""
Launch the Open InsiderTrader dashboard.

Usage:
    python scripts/run_dashboard.py [--port 8050] [--host 127.0.0.1]
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from dashboard.app import run_dashboard


def main():
    parser = argparse.ArgumentParser(description='Launch Open InsiderTrader dashboard')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8050, help='Port to bind to')
    parser.add_argument('--no-debug', action='store_true', help='Disable debug mode')

    args = parser.parse_args()

    print(f"🎯 Starting Open InsiderTrader dashboard...")
    print(f"📍 URL: http://{args.host}:{args.port}")
    print(f"⚡ Debug mode: {'OFF' if args.no_debug else 'ON'}")
    print(f"\n🚀 Dashboard loading...\n")

    run_dashboard(
        host=args.host,
        port=args.port,
        debug=not args.no_debug
    )


if __name__ == '__main__':
    main()
