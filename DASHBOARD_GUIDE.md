# Dashboard Guide - Open InsiderTrader

Three dashboards are available for analyzing insider trading signals:

## 1. Unified Dashboard (NEW) 🎯

**Purpose:** Interactive parameter tuning + live backtest results in one place

**Launch:**
```bash
python3 scripts/run_unified_dashboard.py
```

Then open: http://127.0.0.1:8052

**Features:**

### Interactive Parameter Controls
- **Min Trade Value Slider**: $25K - $500K
- **Min Signal Score Slider**: 0.5 - 5.0
- **Min Market Cap % Slider**: 0 - 0.001%
- **Executive Level Checkboxes**: C-Suite, VP, All

### Live Backtest Results
Click "🔄 Update Results" to see:

1. **Performance Summary Cards**
   - Total signals passing filters
   - Average return (21-day)
   - S&P 500 benchmark
   - Alpha calculation

2. **Multi-Period Summary Table**
   - Periods: 5D, 1M, 3M, 6M, 1Y, 2Y
   - Avg Return, SPY, Alpha for each period
   - Win rate, Sharpe ratio, Max drawdown

3. **Detailed Trade-by-Trade Table** (NEW)
   - Every individual trade listed with ticker, entry date, signal score
   - For EACH period (5D, 1M, 3M, 6M, 1Y, 2Y):
     - Strategy return %
     - S&P 500 return %
     - Alpha (strategy - SPY)
   - Bottom row shows AVERAGE across all trades
   - Sortable, filterable, 50 rows per page
   - Green = positive returns, Red = negative returns

4. **Equity Curve Chart**
   - Strategy vs S&P 500 over time
   - Interactive hover for details

### Workflow
1. Adjust parameter sliders
2. Click "Update Results"
3. Review performance summary
4. Examine trade-by-trade details
5. Iterate to find optimal settings

---

## 2. Parameter Tuning Dashboard 🎛️

**Purpose:** Test different filter settings before running full backtests

**Launch:**
```bash
python3 scripts/run_param_tuner.py
```

Then open: http://127.0.0.1:8051

**Features:**

### Interactive Controls
- **Min Trade Value Slider**: $25K - $500K
  - Filters transactions by dollar amount
  - Default: $100K
  - Try $50K to double signal count

- **Min Signal Score Slider**: 0.5 - 5.0
  - Composite score threshold (exec × dollar × market_cap weights)
  - Default: 1.5
  - Lower = more signals, potentially lower quality

- **Min Market Cap % Slider**: 0 - 0.001%
  - Filter by trade size relative to company market cap
  - Default: 0 (disabled)
  - Enable to focus on smaller companies

### Executive Level Checkboxes
- **C-Suite Only**: CEO, CFO, President, Chairman (weight = 1.0)
- **Include VPs**: EVP, SVP, VP (weight = 0.5)
- **Include All**: All executives (weight ≥ 0.3)

### Real-Time Preview
- **Signal Count Cards**: See how many signals pass each filter
- **Funnel Chart**: Visual representation of filtering stages
- **Top 20 Signals Table**: Preview highest-scoring signals with sorting/filtering

### Actions
- **🔄 Refresh Signals**: Reapply filters with current settings
- **📥 Export CSV**: Download filtered signals with timestamp
- **🚀 Run Backtest**: Save parameters to `config_tuned.yaml` and get instructions

---

## 2. Backtest Results Dashboard 📊

**Purpose:** View performance metrics and AI analysis for backtested signals

**Launch:**
```bash
python3 scripts/run_dashboard.py
```

Then open: http://127.0.0.1:8050

**Features:**
- Performance summary cards (21-day returns, S&P 500 comparison, alpha)
- Multi-period performance table (1d to 5yr holding periods)
- Interactive equity curve chart (Strategy vs S&P 500)
- Returns distribution histogram
- Drawdown analysis chart
- Individual trades table (sortable, filterable, paginated)
- AI Analysis Panel with Claude Sonnet 4.5 recommendations

---

## Recommended Dashboard: Unified Dashboard 🌟

**The Unified Dashboard is now the recommended tool** as it combines parameter tuning with live backtest results. Use it for:
- Finding optimal filter settings
- Seeing immediate performance impact
- Reviewing individual trade returns across all periods
- Understanding alpha generation over different timeframes

The separate Parameter Tuning and Backtest Results dashboards are still available for specialized workflows.

---

## Workflow

### Quick Start (Unified Dashboard)
1. Launch: `python3 scripts/run_unified_dashboard.py`
2. Adjust parameters (try defaults first)
3. Click "Update Results"
4. Review trade-by-trade table for all periods
5. Note average returns at bottom row
6. Iterate to optimize

### Legacy Workflow (Separate Dashboards)

#### Optimize Parameters
1. Launch Parameter Tuning Dashboard
2. Adjust sliders and checkboxes
3. Watch signal count update in real-time
4. Export CSV to review signals
5. Click "Run Backtest" when satisfied

### Run Backtest
1. Copy `config_tuned.yaml` to `config.yaml` (or edit config.yaml directly)
2. Regenerate signals: `python3 scripts/generate_signals.py --store-db`
3. Run backtest: `python3 scripts/run_backtest.py`
4. View results: `python3 scripts/run_dashboard.py`

### Iterate
- Compare performance across different parameter settings
- Use AI analysis recommendations to guide adjustments
- Export top signals for manual review
- Find optimal balance between signal volume and quality

---

## Tips

**Signal Volume vs Quality:**
- More signals = more statistical power for backtesting
- Higher thresholds = potentially higher quality signals
- Aim for at least 30-50 signals for meaningful results

**Current Database:**
- 3,479 total transactions (2 years, 56 tickers)
- Default settings: 130 C-Suite signals (3.74% pass rate)
- Lowering to $50K: 259 signals (7.4% pass rate)

**Executive Levels:**
- C-Suite trades have strongest predictive power (research-backed)
- VPs can provide additional signals if C-Suite volume is low
- Be cautious with "All" - may dilute signal quality

**Parameter Recommendations:**
- Start conservative: C-Suite only, $100K, Score 1.5
- If <50 signals: Lower trade value to $50K OR add VPs
- If >200 signals: Increase score threshold to 2.0
- Avoid market cap % filter unless targeting small/mid-cap companies

---

## Troubleshooting

**Dashboard won't start:**
- Check Python dependencies: `pip3 install -r requirements.txt`
- Ensure database exists: `ls -la data/insider_trades.db`
- Try different port: `python3 scripts/run_param_tuner.py --port 8052`

**No signals showing:**
- Check filter settings - may be too restrictive
- Verify database has data: Should have 3,479+ transactions
- Try resetting to defaults: Min $100K, Score 1.5, C-Suite only

**Export CSV not working:**
- Click "Refresh Signals" first to populate data
- Check browser download settings
- Look for file in Downloads folder: `insider_signals_YYYYMMDD_HHMMSS.csv`

---

Built with Plotly Dash. Questions? Check TODO.md for latest status.
