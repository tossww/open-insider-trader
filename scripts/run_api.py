#!/usr/bin/env python3
"""
Start the FastAPI web server.

Usage:
    python scripts/run_api.py [--host HOST] [--port PORT] [--reload]
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn


def main():
    """Run the FastAPI server."""
    parser = argparse.ArgumentParser(description='Start Open Insider Trader API server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')

    args = parser.parse_args()

    print(f"🚀 Starting Open Insider Trader API on {args.host}:{args.port}")
    print(f"📖 API docs available at: http://{args.host}:{args.port}/docs")
    print()

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == '__main__':
    main()
