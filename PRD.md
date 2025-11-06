# PRD - Open InsiderTrader

**Last Updated:** 2025-11-06
**Status:** Milestone 0 - Project Initialization

---

## Vision

Validate and capitalize on insider trading signals by identifying high-conviction C-level executive stock purchases. Use 5 years of backtesting to prove the hypothesis, then build real-time monitoring for actionable trade alerts.

**Target Users:** Individual retail traders seeking data-driven stock purchase signals

---

## Features

### Phase 1: Validation & Backtesting (Core - Must Build)

- [ ] **Data Collection:** Scrape 5 years of SEC Form 4 insider trading data + market cap data
- [ ] **Signal Detection:** Filter for C-level executives, $100K+ purchases, clustered buys (multiple executives within days), trade-to-market-cap ratio
- [ ] **Backtesting Engine:** Calculate performance across multiple time horizons (1d, 3d, 7d, 1mo, 6mo, 1yr, 3yr)
- [ ] **Benchmark Comparison:** Compare returns vs S&P 500 with transaction costs
- [ ] **Interactive Dashboard:** Web interface with performance tables, interactive charts (Plotly)
- [ ] **AI Analysis:** Sonnet-powered analysis of backtesting results with buy/no-buy recommendations

### Phase 2: Live Monitoring (Future)

- **Real-time Scraping:** Monitor openinsider.com for new trades matching criteria
- **Discord Alerts:** Notify when high-conviction signals appear
- **Historical Context:** Show past performance of similar trades for same company/executives
- **Decision Support:** Interactive charts and AI analysis to support buy decisions
- **Trade Execution:** (Long-term) Automated trading integration

### Not Building (Out of Scope for Phase 1)

- Real-time monitoring (Phase 2)
- Portfolio management features
- Social/community features
- Mobile apps

---

## Tech Stack

**Language:** Python 3.11+

**Data Pipeline:**
- SEC EDGAR API (official Form 4 data source, free)
- Pandas, NumPy for data processing
- SQLite (development) → PostgreSQL (production)

**Backtesting:**
- VectorBT (array-based, 1000x faster than alternatives)
- Backtrader (validation if needed)

**Web Dashboard:**
- Plotly Dash (Python-native, financial charts)
- FastAPI (API backend)
- Option: Next.js + Plotly.js if React preferred

**AI Integration:**
- Anthropic Claude API (Sonnet 4.5) for analysis and recommendations

**Deployment:**
- Vercel/Netlify (frontend) or Render/Railway (full-stack Python)

---

## Milestones

### Milestone 0: Project Setup ✅ IN PROGRESS

**Goal:** Initialize project structure, research validation, technical foundation

**Tasks:**
- [x] Research insider trading signal validity
- [x] Design technical architecture
- [ ] Create GitHub repository
- [ ] Set up Python environment and dependencies
- [ ] Create project folder structure

**Status:** In Progress

---

### Milestone 1: Data Collection Pipeline

**Goal:** Collect and process 5 years of SEC Form 4 insider trading data

**Features:**
- SEC EDGAR API integration
- Form 4 parser (handle amendments, derivative securities)
- Market cap data integration (at time of trade)
- Data cleaning and validation
- SQLite database schema
- C-level executive filter (CEO, CFO, President, Chairman, VP)
- Transaction size filter ($100K+ absolute threshold)
- Trade-to-market-cap ratio calculation and filtering
- Cluster detection (2+ executives buying within 7 days)
- Signal scoring system (weighted by market cap percentage)

**Success Criteria:**
- [ ] Successfully parse 5 years of Form 4 filings
- [ ] Database contains >100K insider trades
- [ ] Filtering logic accurately identifies high-conviction signals
- [ ] Data quality validation tests pass

**Status:** Not Started

---

### Milestone 2: Backtesting Engine

**Goal:** Build and validate backtesting system with realistic assumptions

**Features:**
- Historical stock price integration (Yahoo Finance or similar)
- VectorBT backtesting implementation
- Multiple holding period analysis (1d, 3d, 5d, 2wk, 1mo, 6mo, 1yr, max)
- Transaction cost modeling (0.6% round-trip: 0.2% commission + 0.1% slippage per side)
- S&P 500 benchmark comparison
- Risk metrics (Sharpe ratio, max drawdown, win rate, Calmar ratio)
- Walk-forward validation to prevent overfitting

**Success Criteria:**
- [ ] Backtesting completes on 5 years of data
- [ ] Results show statistically significant alpha vs S&P 500
- [ ] Walk-forward validation confirms robustness
- [ ] Transaction costs properly account for retail trader reality

**Status:** Not Started

---

### Milestone 3: Interactive Dashboard

**Goal:** Create web dashboard to visualize results and support buy decisions

**Features:**
- Performance summary tables (returns by time horizon)
- Interactive Plotly charts (equity curves, returns distribution, drawdown)
- Individual trade drill-down
- S&P 500 overlay comparison
- Risk-adjusted metrics display
- Parameter sensitivity analysis
- AI Analysis Panel: Sonnet reviews all metrics and provides recommendation

**Success Criteria:**
- [ ] Dashboard loads in <2 seconds
- [ ] All charts interactive (zoom, pan, hover tooltips)
- [ ] AI analysis generates actionable buy/no-buy recommendation
- [ ] Responsive design (works on mobile)
- [ ] Deployed and accessible via URL

**Status:** Not Started

---

## Success Criteria

**Phase 1 is complete when:**
- [ ] 5 years of insider trading data successfully collected and processed
- [ ] Backtesting engine validates hypothesis with statistically significant results
- [ ] Interactive dashboard displays performance metrics clearly
- [ ] AI analysis provides consistent, rational buy/no-buy recommendations
- [ ] Results demonstrate positive alpha vs S&P 500 after transaction costs
- [ ] Documentation allows Boss to understand methodology and results

---

## Guidelines

**Important Constraints:**
- Must use filing dates (not trade dates) for realistic signal timing
- Must account for transaction costs (retail trader rates: ~0.6% round-trip)
- Must validate with walk-forward analysis to prevent overfitting
- Must handle filing amendments and derivative securities correctly
- Dashboard must clearly show risk (max drawdown, volatility) alongside returns

**Patterns to Follow:**
- Vectorized Pandas operations (no row-by-row iteration)
- Separate data collection from analysis pipelines
- Type hints and data classes for insider trade objects
- Comprehensive logging for data pipeline steps
- Unit tests for signal generation logic

**Things to Avoid:**
- Don't underestimate transaction costs (common backtesting mistake)
- Don't optimize on entire dataset (use walk-forward validation)
- Don't ignore liquidity constraints (flag low-volume stocks)
- Don't hard-code parameters (make them configurable)
- Don't mix insider sales with purchases (sales are weaker signals)

---

## Research Validation

**Academic Foundation:**
- Insider trading has 50+ years of research validation
- C-level executives (CEO, CFO) show strongest predictive power
- **Clustered purchases**: 2.1% monthly abnormal returns (peer-reviewed research)
- Larger transaction sizes indicate conviction
- Longer holding periods (6+ months) outperform short-term

**Key Risk Factors:**
- Transaction costs erode returns (30-75 bps per trade for retail)
- Overfitting to historical patterns
- Liquidity constraints on low-volume stocks
- Rule 10b5-1 pre-scheduled trades (lack informational content)
- Filing delays vary (legal minimum: 2 business days)
- Mega-cap trades may have weak signal (small % of market cap)

**Trade-to-Market-Cap Insight:**
- Insider purchases more predictive for smaller companies (stronger information advantage)
- $100K in $500M company (0.00002% of market cap) >> $100K in $3T company (0.000000033%)
- Signal strength weighted by percentage of market cap
- Consider excluding/down-weighting mega-caps where insider trades are negligible percentage

---

## AI Analysis Integration

**Sonnet's Role:**
When user views backtesting results, Sonnet analyzes:
- Overall strategy performance vs benchmark
- Risk-adjusted returns (Sharpe, Calmar ratios)
- Win rate and consistency
- Statistical significance
- Current market conditions
- Specific signal quality (if Phase 2)

**Output Format:**
```
🤖 AI Analysis

RECOMMENDATION: [BUY / NO BUY / CAUTIOUS]

RATIONALE:
- [Key finding 1]
- [Key finding 2]
- [Key finding 3]

RISK FACTORS:
- [Risk 1]
- [Risk 2]

CONFIDENCE: [High/Medium/Low]
```

---

*This PRD is the source of truth. Code must match PRD. Update PRD when requirements change.*
