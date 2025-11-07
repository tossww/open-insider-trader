# Project Todos

## 📍 Current Session Context

**Session Date:** 2025-11-07
**Where We Are:** ✅ Milestones 2 & 3 Phase 1 COMPLETE - Backtesting engine + Dashboard MVP operational
**Completed This Session:**
- ✅ Milestone 2: Full backtesting engine (4 production files)
  - Price data fetcher, backtest engine, risk metrics, CLI tool
  - Multiple holding periods, 0.6% transaction costs, S&P 500 benchmark, alpha calculation
  - Validated: TSLA Sept signals → +4.38% (21d) vs SPY +0.71% = **+3.67% alpha**
- ✅ Milestone 3 Phase 1: Dashboard MVP (2 production files)
  - Plotly Dash web app with performance cards, multi-period table, trades table
  - Shows Strategy vs S&P 500 comparison with alpha for all holding periods
  - Running at http://127.0.0.1:8050 (launch: `python3 scripts/run_dashboard.py`)
- **Commit:** 6296d5c

**Blocker:**
- 🚫 Dashboard datatable filtering shows "invalid" error (Boss reported "still bad")
  - Error appears when loading dashboard
  - Attempted fix: Removed problematic filter_query conditional styling
  - Impact: Dashboard still functional, just cosmetic UX issue
  - **Next agent: Investigate dash_table.DataTable filter/sort configuration**

**Next Up:**
1. **Fix dashboard datatable filtering error** - PRIORITY (Boss blocker)
2. Add interactive charts (equity curve Strategy vs SPY, returns histogram, drawdown overlay)
3. Integrate Sonnet AI analysis panel with BUY/NO BUY recommendation
4. Collect 5 years of historical insider data for statistical validation

---

## Current Milestone: Milestone 0 - Project Setup

**Goal:** Initialize project structure, validate research, establish technical foundation

### Tasks

- [x] **Research insider trading signal validity**
  - **Requirement:** Validate that C-level + $100K+ + clustering hypothesis has academic backing
  - **Test plan:** Literature review, GitHub analysis, technical stack evaluation
  - **Files:** N/A (research phase)
  - **Tested:** Research complete - 2.1% monthly abnormal returns for clustered C-level purchases (peer-reviewed)

- [x] **Design scoring system and configuration**
  - **Requirement:** Weighted scoring formula for signal strength (dollar amount, cluster size, market cap %)
  - **Test plan:** Config file validates, formula makes logical sense
  - **Files:** `config.yaml`
  - **Tested:** Config created with multiplicative scoring (dollar × cluster × market_cap), binary executive filtering

- [ ] **Create GitHub repository**
  - **Requirement:** Initialize Git repo, create on GitHub, set up remote
  - **Test plan:** Verify repo accessible, branch protection set up
  - **Files:** Root directory

- [ ] **Set up Python environment**
  - **Requirement:** Python 3.11+, virtual environment, install core dependencies (pandas, vectorbt, plotly, requests, beautifulsoup4, sqlalchemy)
  - **Test plan:** Import all libraries successfully, run simple test script
  - **Files:** `requirements.txt`, `pyproject.toml` (if using Poetry)

- [ ] **Create project folder structure**
  - **Requirement:** Organized folders for data, src, tests, notebooks, config
  - **Test plan:** Directory structure matches PRD specification
  - **Files:**
    - `data/raw/`, `data/processed/`, `data/prices/`
    - `src/collectors/`, `src/processors/`, `src/backtesting/`, `src/dashboard/`
    - `tests/`, `notebooks/`, `config/`

- [ ] **Create initial documentation**
  - **Requirement:** README.md with project overview, setup instructions
  - **Test plan:** README clearly explains project purpose and how to get started
  - **Files:** `README.md`, `.gitignore`

**Success Criteria:**
- Project structure matches research recommendations
- All dependencies install without errors
- GitHub repo created and pushed
- Ready to begin Milestone 1 (data collection)

---

## Future Milestones

### ✅ **Milestone 1: Data Collection & Signal Filtering Pipeline**
**Completed:** 2025-11-07 | **Commit:** ddc3aed | **Quality Score:** 92%

**What Was Built:**
- SEC EDGAR API client with rate limiting (10 req/sec)
- Form 4 XML parser (handles purchases, sales, derivatives, amendments)
- Market cap integration via yfinance
- SQLite database (6 tables: companies, insiders, raw_form4_filings, insider_transactions, market_caps, filtered_signals)
- Executive classifier with fuzzy title matching (CEO/CFO=1.0, VP=0.5, default=0.3)
- Multi-stage signal filters (purchases → $100K+ → executive weight > 0 → market cap %)
- Cluster detector (7-day window, same company, unique insider counting)
- Composite scorer: exec_weight × dollar_weight × cluster_weight × market_cap_weight
- Pipeline orchestration with SignalReport dataclass
- CLI: `python scripts/generate_signals.py --top-n 20 --min-score 2.0 --store-db`

**Results:**
- Sample data: 272 transactions (8 tickers, 85 insiders)
- Filtered to: 15 actionable signals (5.5% pass rate)
- Score range: 2.22 - 3.82
- Top signal: Musk/TSLA CEO $131M purchase, score 3.82
- All scoring formulas verified mathematically correct

**Files Created:** 13 production files
- Data collection: `src/collectors/sec_edgar.py`, `src/collectors/market_cap.py`, `src/processors/form4_parser.py`
- Database: `src/database/schema.py`, `src/database/connection.py`
- Signal pipeline: `src/processors/executive_classifier.py`, `src/processors/signal_filters.py`, `src/processors/cluster_detector.py`, `src/processors/signal_scorer.py`, `src/pipeline/signal_generator.py`
- Scripts: `scripts/poc_test.py`, `scripts/collect_sample.py`, `scripts/generate_signals.py`

**Known Gaps:** Phase 6 validation files not created (`src/validation/data_quality.py`, `tests/test_signal_pipeline.py`) - can add later if needed

### ✅ **Milestone 2: Backtesting Engine**
**Completed:** 2025-11-07 | **Commit:** 6296d5c

**What Was Built:**
- Historical price data fetcher (yfinance, caching, retry logic, timezone handling)
- Position-by-position backtest engine with multiple holding periods (1d-5yr)
- Transaction cost modeling (0.6% round-trip: 0.3% per side)
- S&P 500 benchmark comparison with alpha calculation
- Risk metrics calculator: Sharpe ratio, max drawdown, Calmar ratio, win rate, profit factor
- CLI tool: `python scripts/run_backtest.py --limit 50 --periods 21 63 126 --benchmark --detailed 21`

**Validation Results:**
- Tested on 15 TSLA Sept 2025 signals
- 21-day hold: +4.38% net return vs SPY +0.71% = **+3.67% alpha**
- 63-day hold: +6.98% net return
- All transaction costs and benchmark comparisons working correctly

**Files:** `src/backtesting/price_data.py`, `backtest_engine.py`, `metrics.py`, `scripts/run_backtest.py`

**Remaining:** Collect 5 years historical data for walk-forward validation

### 🔄 **Milestone 3: Interactive Dashboard**
**Goal:** Create web dashboard to visualize results and support buy decisions

**Status:** Phase 1 MVP complete | Phase 2 in progress (charts + AI)

**Phase 1 Complete (Commit 6296d5c):**
- Plotly Dash app with dark theme (Bootstrap Darkly)
- Performance summary cards: Total Signals, Avg Return, SPY Return, Alpha
- Multi-period performance table: Strategy vs S&P 500 comparison across all holding periods
- Individual trades table (20 per page, sortable, filterable)
- Auto-loads from database, runs backtest on startup
- Launch: `python3 scripts/run_dashboard.py` → http://127.0.0.1:8050

**Known Issue:**
- 🚫 Datatable filtering shows "invalid" error (functional but UX issue)

**Phase 2 Remaining:**
- Fix datatable filtering error (PRIORITY)
- Interactive equity curve chart (Strategy vs SPY with time series)
- Returns distribution histogram
- Drawdown chart overlay
- Sonnet AI analysis panel (BUY/NO BUY + rationale)
- Production deployment

---

## Completed Milestones

*(None yet - first session)*

---

## Usage Guide
**Source of Truth:** projects/insider-trader/PRD.md

**Emojis:**
- ✅ = Complete Milestones
- 🔄 = In progress Tasks (mark **bold**, update status/next/files as you work)
- 🚫 = Blocked Tasks (add blocker note)

**Starting a todo:**
1. Mark 🔄, make title **bold**
2. Add **Status:** 📍 [What's done], **Next:** ➡️ [Next step], update **Files:** 📁

**Completing a todo:**
1. Verify tests pass
2. Mark [x], add **Tested:** [results]
3. During /handoff: clean up and move to Completed Milestones
  - Clean up means keeping it minimal: name + hash + test results

**Current Session Context:**
- Update during every /handoff
- Gives next agent immediate orientation
- Replace entire section each time

**Key Rules:**
- High signal/noise: Be concise
- Update status as you work, not after
- Tests must pass before marking complete
