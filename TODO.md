# Project Todos

## 📍 Current Session Context

**Session Date:** 2025-11-06
**Where We Are:** Milestone 0 - Research complete, PRD/config created
**Working On:** Setting up GitHub repo and project structure
**Next Up:** Complete Milestone 0 (repo + Python env + folder structure), then begin Milestone 1 data collection

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

### Milestone 1: Data Collection Pipeline
**Goal:** Collect and process 5 years of SEC Form 4 insider trading data
**Key Tasks:**
- SEC EDGAR API integration
- Form 4 parser with amendment handling
- Database schema design and implementation
- Signal filters (C-level, $100K+, clustering detection)

### Milestone 2: Backtesting Engine
**Goal:** Build and validate backtesting system with realistic assumptions
**Key Tasks:**
- Historical price data integration
- VectorBT backtesting implementation
- Multiple holding period analysis
- Transaction cost modeling
- Walk-forward validation

### Milestone 3: Interactive Dashboard
**Goal:** Create web dashboard to visualize results and support buy decisions
**Key Tasks:**
- Plotly Dash dashboard implementation
- Interactive charts and performance tables
- AI analysis integration (Sonnet API)
- Deployment to production

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
