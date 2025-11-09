# Open Insider Trader

**A web-based insider trading intelligence platform** that identifies high-conviction insider buy signals and sends email alerts when opportunities arise.

## Features

- **📊 Smart Signal Scoring**: Combines conviction (trade size, exec level, clustering) + track record (win rate, alpha)
- **🔔 Email Alerts**: Automatic notifications for score ≥7 signals
- **🌐 Web Dashboard**: Transaction feed with filtering + company deep-dive views
- **🤖 Automated Scraping**: Every 6 hours from OpenInsider.com
- **📈 Performance Tracking**: Win rates and alpha vs SPY for all insiders

## Quick Start

### 1. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### 2. Initialize Database

```bash
# Create database and scrape initial data
python scripts/initialize_db.py
```

### 3. Generate Signals

```bash
# Score all transactions
python scripts/test_signal_scoring.py
```

### 4. Run Application

**Terminal 1 - Backend:**
```bash
python scripts/run_api.py --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Email alerts (optional)
SENDGRID_API_KEY=your_key_here
FROM_EMAIL=alerts@your-domain.com
SUBSCRIBER_EMAILS=user1@email.com,user2@email.com

# App URL (for email links)
BASE_URL=http://localhost:3000
```

## Project Structure

```
open-insider-trader/
├── src/
│   ├── api/              # FastAPI backend
│   ├── collectors/       # Data scrapers
│   ├── database/         # SQLAlchemy models
│   ├── signals/          # Scoring system
│   ├── backtesting/      # Performance calculation
│   ├── email/            # Alert system
│   └── automation/       # Schedulers
├── frontend/             # React + Vite app
├── scripts/              # Utility scripts
├── data/                 # SQLite database
└── tests/                # Test suite
```

## Signal Scoring

**Total Score = Conviction (0-3) + Track Record (0-5)**

### Conviction Score
- Trade value >$1M: +1
- Multiple buys in 30 days: +1
- C-Suite executive: +1

### Track Record Score
- Win rate >70%: +3, 60-70%: +2, 50-60%: +1
- Alpha >10%: +2, 5-10%: +1

### Thresholds
- **≥7**: Strong Buy (email alert)
- **5-6**: Watch
- **3-4**: Weak
- **<3**: Ignore

## API Endpoints

### Transactions
- `GET /api/transactions/feed` - Transaction feed with filters
- `GET /api/transactions/stats` - Overall statistics

### Companies
- `GET /api/companies/{ticker}` - Company deep dive
- `GET /api/companies/{ticker}/insider/{id}/history` - Insider timeline

### Signals
- `GET /api/signals/strong-buys` - Strong buy signals
- `POST /api/signals/{id}/mark-sent` - Mark alert as sent

## Deployment

See [README_DEPLOYMENT.md](README_DEPLOYMENT.md) for full deployment guide.

**Quick deploy to Render:**
1. Connect GitHub repo to Render
2. Set environment variables in dashboard
3. Deploy automatically via `render.yaml`

**Docker:**
```bash
docker-compose up --build
```

## Development

### Run Tests
```bash
pytest tests/
```

### Manual Scraping
```bash
python -c "from src.collectors.openinsider import OpenInsiderCollector; OpenInsiderCollector().collect()"
```

### Process Alerts (Dry Run)
```bash
python -c "from src.automation.alert_processor import process_alerts; process_alerts(dry_run=True)"
```

## Academic Validation

Based on research showing:
- High-conviction insider purchases: **+20.94% avg return** over 12 months
- Insider purchases beat SPY by **+17.6%** on average
- Win rate threshold of **60%+** is statistically significant

## Roadmap

- [ ] Stock price charts with trade markers
- [ ] Sell signal detection
- [ ] Portfolio tracking
- [ ] Mobile app
- [ ] Real-time scraping (WebSocket)
- [ ] Social sharing

## License

MIT

## Disclaimer

**This is not financial advice.** Do your own research before making investment decisions. Past performance does not guarantee future results.
