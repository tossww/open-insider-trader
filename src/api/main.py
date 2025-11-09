"""
FastAPI application for Open Insider Trader.

Provides REST API endpoints for:
- Company deep dive data
- Transaction feed
- Insider performance history
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta

from .routers import companies, transactions, signals
from ..database.connection import get_session

# Create FastAPI app
app = FastAPI(
    title="Open Insider Trader API",
    description="Insider trading intelligence platform API",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Open Insider Trader API",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    try:
        session = get_session()
        # Test database connection
        from ..database.schema import Company
        count = session.query(Company).count()
        session.close()

        return {
            "status": "healthy",
            "database": "connected",
            "companies_count": count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
