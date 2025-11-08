#!/usr/bin/env python3
"""
Launch the unified dashboard combining parameter tuning with live backtest results.

Usage:
    python3 scripts/run_unified_dashboard.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dashboard.unified_dashboard import run_unified_dashboard


if __name__ == '__main__':
    print("=" * 80)
    print("🎯 UNIFIED DASHBOARD - Open InsiderTrader")
    print("=" * 80)
    print("\n🌐 Starting server at http://127.0.0.1:8052")
    print("\nFeatures:")
    print("  • Adjust filtering parameters with sliders")
    print("  • View ticker-level results with 1d, 1w, 1m, 1y gains vs S&P 500")
    print("  • Compare strategy vs S&P 500 with 4 average performance charts")
    print("  • Real-time backtesting on parameter changes")
    print("\n" + "=" * 80)
    print("Press Ctrl+C to stop the server\n")

    run_unified_dashboard(port=8052, debug=True)
