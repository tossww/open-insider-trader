# Deployment Guide

## Quick Start (Docker)

1. **Build and run locally:**
```bash
docker-compose up --build
```

2. **Access the app:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Render Deployment

### Prerequisites
- GitHub repo connected to Render
- SendGrid account with API key

### Steps

1. **Create Render account** at https://render.com

2. **Create new Web Service:**
   - Connect your GitHub repo
   - Render will detect `render.yaml` automatically

3. **Set environment variables** in Render dashboard:
   - `SENDGRID_API_KEY`: Your SendGrid API key
   - `SUBSCRIBER_EMAILS`: Comma-separated email list
   - `FROM_EMAIL`: Sender email (must be verified in SendGrid)
   - `BASE_URL`: Your Render app URL (e.g., `https://your-app.onrender.com`)

4. **Deploy:**
   - Render will build and deploy automatically
   - Check logs for any errors
   - Verify health check: `https://your-app.onrender.com/api/health`

### Post-Deployment

1. **Verify scraping works:**
```bash
curl https://your-app.onrender.com/api/transactions/stats
```

2. **Monitor scheduler:**
- Check logs for scheduled job execution
- Scraping runs every 6 hours
- Alerts process every hour
- Performance recalc weekly (Sunday 2 AM)

3. **Test email alerts:**
- Wait for strong buy signals (score ≥7)
- Or manually trigger via API

## AWS EC2 Deployment (Alternative)

If you prefer AWS:

1. **Launch EC2 instance** (t3.small recommended)

2. **Install Docker:**
```bash
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user
```

3. **Clone repo and deploy:**
```bash
git clone <your-repo>
cd open-insider-trader
cp .env.example .env
# Edit .env with your values
docker-compose up -d
```

4. **Set up reverse proxy (nginx)** for HTTPS

5. **Configure domain and SSL** (Let's Encrypt)

## Monitoring

### Health Checks
- API health: `GET /api/health`
- Transaction stats: `GET /api/transactions/stats`

### Logs
- Render: Check logs in dashboard
- Docker: `docker-compose logs -f`

### Metrics to Monitor
- Scraping success rate (target: >95%)
- Email delivery rate (target: >99%)
- API response time (target: <2s)
- Uptime (target: >99.5%)

## Troubleshooting

### Scraping Fails
- Check OpenInsider.com is accessible
- Verify rate limiting (2s delay)
- Check network connectivity

### Emails Not Sending
- Verify SendGrid API key is correct
- Check sender email is verified in SendGrid
- Review SendGrid activity logs
- Ensure SUBSCRIBER_EMAILS is set

### Database Issues
- SQLite file permissions
- Disk space on server
- Backup database regularly

## Backup Strategy

### Daily Backups
```bash
# Run as cron job
cp data/insider_trades.db backups/insider_trades_$(date +%Y%m%d).db
```

### Restore from Backup
```bash
cp backups/insider_trades_YYYYMMDD.db data/insider_trades.db
```

## Scaling Considerations

For high traffic:
1. **Move to PostgreSQL** (update DB_URL env var)
2. **Use Redis** for caching
3. **Deploy frontend separately** (Vercel/Netlify)
4. **Add load balancer** for multiple API instances
5. **Separate scraping** into dedicated worker service
