# Project Logs

## 2025-11-07 11:56 - Milestone 1 Phases 3-5 Complete

**Context:** Implemented complete signal filtering, clustering, and scoring pipeline (8-file system)

**Files Created:**
1. `src/processors/executive_classifier.py` (123 lines) - Maps officer titles to weights with fuzzy matching
2. `src/processors/signal_filters.py` (197 lines) - Multi-stage filtering (purchases → $100K+ → executive → market cap %)
3. `src/processors/cluster_detector.py` (176 lines) - Groups by company + 7-day window
4. `src/processors/signal_scorer.py` (220 lines) - Composite scoring (exec × dollar × cluster × market_cap)
5. `src/pipeline/signal_generator.py` (170 lines) - Pipeline orchestration with SignalReport
6. `scripts/generate_signals.py` (232 lines) - CLI script with --top-n, --min-score, --store-db
7. `src/database/schema.py` (+38 lines) - Added FilteredSignal table

**Pipeline Results (272 transactions → 15 signals):**
- Stage 1 (Purchases): 44
- Stage 2 (>= $100K): 29
- Stage 3 (Executive weight > 0): 25
- Stage 4 (Market cap %): 15
- Actionable signals (score >= 2.0): 15 (100%)
- Score range: 2.22 - 3.82
- Average score: 3.01

**Top 3 Signals:**
1. TSLA - Musk (CEO) - $131M - Score 3.82 ✓
2. TSLA - Musk (CEO) - $115M - Score 3.70 ✓
3. TSLA - Musk (CEO) - $113M - Score 3.69 ✓

**Sanity Checks:** ✓ All passed
- CEO scores 2x VP (same trade size)
- $10M scores 2x $100K (same exec)
- Clustered scores 2x solo (same trade)
- Small-cap scores 4x mega-cap (same $ trade)

**Database:** FilteredSignal table created, 15 records stored, queries working

**Status:** Milestone 1 Phases 3-5 complete, pipeline operational, ready for verification

---

## 2025-11-07 06:50 - Enhanced Sample Collection (Option 2)

**Context:** After Fury approved Iteration 2 at 95%, Boss selected Option 2: enhance sample with financial sector coverage.

**Changes:**
- Added 3 financial tickers: BAC, GS, C
- Total: 8 tickers (4 tech/retail, 4 finance)
- `scripts/collect_sample.py:156` - Extended ticker list

**Results:**
- Filings: 131 (+51% from 87)
- Transactions: 272 (+49% from 182)
- Insiders: 85 unique
- Database: 268KB
- Financial sector: 39% of dataset (105/272 transactions)

**Per-Ticker:**
- BAC: 23 filings, 46 transactions
- GS: 9 filings, 18 transactions
- C: 13 filings, 32 transactions
- JPM: 9 filings (now has peer comparison)

**Status:** Enhanced sample ready for Phases 3-5 signal filtering

---

## 2025-11-06 18:35 - Iteration 2: Bug Fixes

**Context:** Fury scored Iteration 1 at 87%. Identified 3 issues preventing 90% threshold.

**Root Causes Discovered:**
- JPM failures: SEC API `owner='include'` returned non-Form-4 filings (424B2, 10-Q)
- Low transaction count: 30-day range + 10-filing limit too restrictive
- MSFT ticker already correct (no fix needed)

**Changes:**
- `src/collectors/sec_edgar.py:216` - Changed `owner='include'` to `owner='only'`
- `scripts/collect_sample.py:158` - Extended date range 30d → 90d
- `scripts/collect_sample.py:187` - Increased filing limit 10 → 30

**Testing:**
- JPM extraction unit test: 100% success rate (was 10%)
- Total filings: 80 (was 12, +567%)
- Total transactions: 170 (was 30, +467%)
- All 5 tickers collected successfully
- Database size: 196KB (was 100KB)

**Status:** Iteration 2 complete, awaiting Fury verification

---

## 2025-11-06 18:23 - Milestone 1 Phase 1-2 Complete

**Context:** Implemented data collection pipeline foundation (Phases 1-2 of 5)
**Completed:**
- SEC EDGAR API client with rate limiting, CIK lookup, Form 4 retrieval, XML extraction
- Form 4 XML parser handling non-derivative and derivative transactions
- SQLAlchemy database schema (companies, insiders, filings, transactions, market caps)
- Database connection manager with SQLite support
- Market cap fetcher using yfinance with caching
- POC test script validating end-to-end SEC API → parse → display flow
- Sample collection script gathering 30 transactions across AAPL, MSFT, JPM, WMT

**Testing:**
- POC test: ✅ Successfully fetched and parsed TSLA Form 4 filing
- Sample collection: ✅ 30 transactions stored across 3 companies, 11 insiders, 9 market caps
- Database verification: ✅ All tables created, constraints working, data queryable

**Next:** Phase 3-5 (signal filters, clustering detection, scoring) - Awaiting Fury verification

---

## 2025-11-06 - Project Initialized

**Project:** Open InsiderTrader
**Vision:** Validate and capitalize on clustered C-level insider trading signals

**Initial Setup:**
- Completed comprehensive research (academic validation, tech stack, methodology)
- Created PRD with 3 milestones (Data Collection, Backtesting, Dashboard)
- Research validates hypothesis: 2.1% monthly abnormal returns for clustered C-level purchases
- Tech stack: Python + VectorBT + SEC EDGAR API + Plotly + Sonnet AI analysis

**Next Steps:**
- Create GitHub repository
- Set up Python environment
- Build project folder structure
- Begin Milestone 1: Data Collection Pipeline

---
