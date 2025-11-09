# Open Insider Trader - PRD

## Vision
A web-based insider trading intelligence platform that identifies high-conviction insider buy signals and sends email alerts when opportunities arise. Built on OpenInsider.com data with performance-validated scoring.

---

## Core User Flow

1. **Email Alert** → You receive an email: "High-conviction buy signal detected for $TICKER"
2. **Click to Web App** → Opens company deep-dive view
3. **Review Signal** → See insider's historical performance, trade details, conviction score
4. **Make Decision** → Informed buy/pass decision based on data

---

## Features

### 1. Web Application

#### A. Transaction Feed (Right Column)
- Display all recent **buy transactions only** (no option exercises)
- Sorted by date (newest first)
- Filterable by:
  - Score threshold (≥3, ≥5, ≥7)
  - Executive level (C-Suite, Director, etc.)
  - Trade value ($100K+, $500K+, $1M+)
- Show per transaction:
  - Ticker, company name
  - Insider name, title
  - Trade value, shares
  - Signal score (0-8)
  - Date

#### B. Company Deep Dive (Main View)
**Accessed by:** Clicking a ticker or entering ticker in search box

**Display:**
1. **Company Header**
   - Ticker, company name
   - Current stock price, 52w high/low
   - Market cap

2. **Insider Activity Table** (grouped by person)
   - Columns:
     - Insider Name
     - Title
     - # Buys (last 12 months)
     - # Sells (last 12 months)
     - Win Rate (% of buys that went up over 1w, 1m, 3m, 6m)
     - Avg Return (across all holding periods)
     - Alpha vs SPY
     - Latest Trade (date, value, type)
   - Sort by: Win Rate (default), Alpha, Latest Trade
   - Color coding:
     - Green: Win rate >70%, Alpha >10%
     - Yellow: Win rate 60-70%, Alpha 5-10%
     - Gray: Win rate <60% or Alpha <5%

3. **Trade History Timeline**
   - Chronological list of all buys/sells for selected insider
   - Show: Date, Type (Buy/Sell), Value, Shares, Price
   - Overlay stock price chart with trade markers

### 2. Signal Scoring System

**Score = Conviction (0-3) + Track Record (0-5)**

#### Conviction Score (0-3 points)
- Trade value >$1M: +1 point
- Multiple buys within 30 days: +1 point
- C-Suite executive: +1 point

#### Track Record Score (0-5 points)
Based on insider's historical performance:
- **Win Rate:**
  - >70%: +3 points
  - 60-70%: +2 points
  - 50-60%: +1 point
  - <50%: 0 points
- **Alpha vs SPY:**
  - >10%: +2 points
  - 5-10%: +1 point
  - <5%: 0 points

**If insider has no historical trades:** Use company-wide insider average

#### Thresholds
- **Score ≥7:** Strong Buy (email alert + dashboard highlight)
- **Score 5-6:** Watch (dashboard highlight)
- **Score 3-4:** Weak signal (visible, but no highlight)
- **Score <3:** Ignore (filter out by default)

### 3. Email Alerts

**Trigger:** Any transaction with score ≥7

**Email content:**
```
Subject: [STRONG BUY] $TICKER - High-Conviction Insider Purchase

Insider: [Name] ([Title])
Trade Value: $[Value]
Signal Score: [X]/8

Why this matters:
- [Conviction factors: e.g., "$2.5M purchase, C-Suite exec"]
- [Track record: e.g., "73% win rate, +14% alpha vs SPY"]

[View Details Button] → Links to company deep dive

---
Open Insider Trader
```

**Frequency:** Real-time (as signals are detected)

**Settings:**
- Minimum score threshold (default: 7)
- Max emails per day (default: 5)
- Ticker watchlist (optional: only alert for specific tickers)

---

## Data Pipeline

### Data Source
- **Primary:** OpenInsider.com (HTML scraping)
- **Backup:** SEC EDGAR (existing ingestion if needed)

### Scraping
- **Frequency:** Every 6 hours (or daily after market close)
- **Data to extract:**
  - Ticker, company name
  - Insider name, title
  - Trade date, filing date
  - Transaction type (buy/sell, exclude option exercises)
  - Shares, price, total value

### Storage
- **Database:** SQLite (existing schema)
- **Tables:**
  - `transactions` - Raw trade data
  - `insiders` - Insider profiles with performance metrics
  - `signals` - Scored signals with alert status

### Performance Calculation
- **Use existing backtest engine** (from SEC system)
- **Holding periods:** 1d, 1w, 1m, 3m, 6m
- **Metrics:**
  - Win rate (% trades with positive return)
  - Avg return
  - Alpha vs SPY (benchmark: ^GSPC)
  - Sharpe ratio (optional)
- **Recalculation:** Weekly (to update insider performance scores)

---

## Tech Stack

### Backend
- Python 3.11+
- Flask or FastAPI (web server)
- SQLite (database)
- BeautifulSoup/Scrapy (OpenInsider scraping)
- Pandas + yfinance (existing backtest engine)
- APScheduler (cron jobs for scraping)

### Frontend
- React or Next.js
- TailwindCSS
- Recharts/Chart.js (stock price overlay charts)

### Email
- SendGrid or AWS SES
- HTML email templates

### Deployment
- Docker
- AWS EC2 or Render
- Cron job for daily scraping

---

## Constraints & Guidelines

### Performance
- Web app must load in <2 seconds
- Email alerts must send within 5 minutes of signal detection

### Data Quality
- Exclude option exercises (not true conviction)
- Filter out transactions <$50K (noise)
- Validate ticker symbols against yfinance

### Privacy
- No user accounts required for web app (public access)
- Email alerts require sign-up (store email only, no PII)

### Scalability
- Support 10K+ transactions in database
- Handle 100+ email subscribers
- Scraping must not overload OpenInsider.com (rate limiting)

---

## Success Metrics

### Signal Quality
- Average win rate of score ≥7 signals: **>65%**
- Average alpha vs SPY: **>10%** over 3-month holding period

### User Engagement
- Email open rate: **>40%**
- Click-through to web app: **>20%**

### System Reliability
- Scraping success rate: **>95%**
- Email delivery rate: **>99%**
- Uptime: **>99.5%**

---

## Out of Scope (for now)

- Sell signals (focus on buys only)
- Portfolio tracking (just signals, not execution)
- Social sharing (private tool for now)
- Mobile app (web-first)
- Real-time scraping (6-hour delay acceptable)

---

## Academic Validation

Based on research:
- High-conviction insider purchases generate **+20.94% average return** over 12 months
- Insider purchases beat SPY by **+17.6%** on average
- Win rate threshold of **60%+** is statistically significant
- First 6 months post-purchase show **52-68 bps/month** abnormal returns

**Target:** Match or exceed academic benchmarks with our scoring system.

---

*Last updated: 2025-11-08*
