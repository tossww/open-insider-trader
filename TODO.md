# TODO

## 📍 Current Session Context
**Session Date:** 2025-11-09 06:20
**Status:** ✅ Platform Complete + Data Refreshed + UX Polished

**Where We Are:**
- Full-stack insider trading platform is production-ready (Phases 1-5 complete)
- Fresh data pipeline working (362 transactions, latest: Nov 7 21:00)
- Frontend UX refined (proper timestamps, text selection fix, clean date formatting)

**Working On:**
- Nothing in progress - clean slate

**Next Up:**
1. **Enable Auto-Scheduler** - Scraper configured but never activated in API startup
2. **Deploy to Production** - Render or Docker (all configs ready)
3. **Generate Signals** - Run signal scoring on fresh Nov 4-7 transactions
4. **Phase 6 Enhancements** - Stock price charts, advanced filters
5. **Phase 7** - Email subscription UI (currently uses env var)

**Key Files:**
- API: `src/api/main.py`, `src/api/routers/*.py`
- Frontend: `frontend/src/pages/{Dashboard,CompanyView}.jsx`
- Scraper: `src/collectors/openinsider.py`
- Scheduler: `src/automation/scheduler.py` (exists but not started)
- Database: `data/insider_trades.db` (362 transactions)

**Important Notes:**
- Scheduler issue: `start_scheduler()` not called in `src/api/main.py`
- To enable: Add scheduler startup to FastAPI lifespan or startup event
- Data scraping works when run manually, automation just needs activation

---

## Pending Tasks

### 🔧 Enable Automated Scraping
**Priority:** HIGH
**Status:** ⏸️ Ready to implement

The scheduler exists (`src/automation/scheduler.py`) with 3 jobs configured:
- Scraping: Every 6 hours
- Alerts: Every hour
- Performance calc: Weekly (Sun 2 AM)

**Problem:** `start_scheduler()` is never called when API starts

**Next Steps:**
1. Add FastAPI lifespan event handler to `src/api/main.py`
2. Call `start_scheduler()` on startup
3. Call `stop_scheduler()` on shutdown
4. Test by checking logs after API restart
5. Verify scraper runs automatically after 6 hours

**Files to modify:**
- `src/api/main.py` (add lifespan context manager)

**Example code pattern:**
```python
from contextlib import asynccontextmanager
from .automation import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()

app = FastAPI(..., lifespan=lifespan)
```

---

### 🚀 Deploy to Production
**Priority:** MEDIUM
**Status:** ⏸️ Ready when needed

All deployment configs ready:
- `Dockerfile` - Multi-stage build
- `docker-compose.yml` - Local dev
- `render.yaml` - Render deployment
- `README_DEPLOYMENT.md` - AWS EC2 guide
- `.env.example` - Environment template

**Before deploying:**
1. Set up SendGrid API key (for email alerts)
2. Configure subscriber emails in env
3. Test Docker build locally
4. Choose platform (Render recommended for simplicity)

---

### 🎯 Generate Signals for Fresh Data
**Priority:** MEDIUM
**Status:** ⏸️ Ready to run

Database has 108 new transactions (Nov 4-7) without signal scores.

**Next Steps:**
1. Run signal generation script:
   ```bash
   python -c "from src.signals import SignalGenerator; from src.database.connection import get_session; s = get_session(); sigs = SignalGenerator.generate_signals(s); print(f'{len(sigs)} signals'); s.close()"
   ```
2. Check for strong buy signals (score ≥7)
3. Verify email alerts trigger (if SendGrid configured)

**Expected:** Most signals will be low-scored (no historical track record yet)

---

### 📊 Phase 6: Stock Price Charts (DEFERRED)
**Priority:** LOW
**Status:** ⏸️ Post-MVP

Add interactive price charts to company deep dive view.

**What's needed:**
- Recharts already in `package.json`
- Fetch price data for chart overlay
- Add trade markers on timeline
- Show entry/exit points with returns

**Files:**
- `frontend/src/pages/CompanyView.jsx`
- New component: `frontend/src/components/PriceChart.jsx`

---

### 📧 Phase 7: Email Subscription UI (DEFERRED)
**Priority:** LOW
**Status:** ⏸️ Post-MVP

Currently subscribers are configured via `SUBSCRIBER_EMAILS` env var.

**What's needed:**
- Frontend signup form
- Backend API: POST /api/subscribe
- Database table: `email_subscribers`
- Unsubscribe links in emails
- Confirmation emails

---

## Completed Milestones

### ✅ 2025-11-09 - Data Refresh + UX Polish (Commit: 7c114bb)
**What Was Done:**
- Fixed OpenInsider scraper (bypassed broken daysago filter)
- Manual scrape added 108 transactions (Nov 4-7, 2025)
- Database: 362 total transactions, latest Nov 7 21:00
- Frontend: Changed to `yyyy-MM-dd HH:mm` format (24-hour time)
- API: Added `filing_date` field (actual timestamp vs midnight trade_date)
- Frontend: Fixed text selection navigation issue
- Reverted to standard date-fns (no custom time formatting)

**Key Fix:** Was using `trade_date` (always 00:00) instead of `filing_date` (actual time)

**Files Modified:**
- `src/api/routers/transactions.py`
- `src/api/routers/companies.py`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/pages/CompanyView.jsx`

**Tests:** API ✅ | Frontend build ✅ | Data freshness ✅

---

### ✅ 2025-11-08 - Complete Platform (Phases 1-5)
**Platform Built:**
- Phase 1: OpenInsider scraper, SQLite DB, backtest engine
- Phase 2: Signal scoring (conviction + track record, 0-8 scale)
- Phase 3: FastAPI + React web app
- Phase 4: SendGrid email alerts
- Phase 5: Docker + Render deployment configs

**Files:** 45+ files across 7 modules
**Commits:** 4cb6e43 (PRD), plus implementation commits

---

*Last updated: 2025-11-09 06:20*
