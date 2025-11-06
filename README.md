# Open InsiderTrader

Validate and capitalize on insider trading signals by identifying high-conviction C-level executive stock purchases.

## Research Foundation

Academic research shows **2.1% monthly abnormal returns** for clustered C-level insider purchases.

**Signal Criteria:**
- C-level executives (CEO, CFO, President, etc.)
- $100K+ purchase size
- Clustered trades (multiple executives within 7 days)
- Weighted by trade-to-market-cap ratio

## Project Status

**Current Milestone:** Milestone 0 - Project Setup ✅ Complete

**Next Up:** Milestone 1 - Data Collection Pipeline (SEC Form 4 scraping)

## Quick Start

```bash
# Clone repo
git clone https://github.com/tossww/open-insider-trader.git
cd open-insider-trader

# Set up Python environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

## Project Structure

```
├── data/               # Data storage
│   ├── raw/           # Raw SEC Form 4 filings
│   ├── processed/     # Cleaned and filtered signals
│   └── prices/        # Historical price data
├── src/               # Source code
│   ├── collectors/    # SEC EDGAR API integration
│   ├── processors/    # Signal detection and scoring
│   ├── backtesting/   # VectorBT backtesting engine
│   └── dashboard/     # Plotly Dash web interface
├── tests/             # Unit and integration tests
├── notebooks/         # Jupyter notebooks for analysis
└── config.yaml        # Signal scoring parameters
```

## Roadmap

- [x] **Milestone 0:** Project setup and research validation
- [ ] **Milestone 1:** Data collection pipeline (5 years of Form 4 data)
- [ ] **Milestone 2:** Backtesting engine with realistic transaction costs
- [ ] **Milestone 3:** Interactive dashboard with AI analysis

## Tech Stack

- **Data Pipeline:** Python 3.9+, Pandas, SEC EDGAR API
- **Backtesting:** VectorBT (1000x faster than alternatives)
- **Dashboard:** Plotly Dash or Next.js + Plotly.js
- **AI Analysis:** Anthropic Claude API (Sonnet 4.5)
- **Database:** SQLite (dev) → PostgreSQL (prod)

## Configuration

Signal scoring and filtering parameters are in `config.yaml`:

- **Filtering:** Min trade size, cluster detection window, market cap thresholds
- **Scoring:** Dollar amount weighting, cluster weighting, market cap weighting
- **Backtesting:** Holding periods, transaction costs, benchmark comparison

## Documentation

- **PRD.md** - Full project requirements and technical design
- **TODO.md** - Current tasks and session context
- **Logs.md** - Session history

## License

MIT
