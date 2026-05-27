# Nginx Deployment

This deployment serves the React/Vite admin app from `/var/www/us-stock-scorer/admin` through Nginx and keeps the FastAPI backend running through systemd on `127.0.0.1:8000`. The admin SPA uses same-origin API calls in production, so Nginx proxies `/v1/`, `/health`, `/openapi.json`, `/docs`, and `/redoc` to the backend.

## One-Time Setup

Install Nginx with the package manager for your server:

```bash
sudo apt-get update
sudo apt-get install -y nginx
```

On CentOS/RHEL-style hosts:

```bash
sudo dnf install -y nginx
```

Then deploy this project:

```bash
cd /home/admin/us-stock-scorer
sudo env SERVER_NAME=SERVER_IP bash deploy/install-production.sh
```

The current installed host uses:

```bash
sudo -n env SERVER_NAME=us-stock-scorer.local bash deploy/install-production.sh
```

Before starting the service, create `/home/admin/us-stock-scorer/apps/api/.env` with authentication settings:

```bash
STOCK_SCORER_READ_TOKEN=replace-with-long-random-read-token
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-long-random-password
ADMIN_SESSION_TTL_SECONDS=43200
```

`ADMIN_AUTH_TOKEN` is optional for scripts that need administrator-level Bearer access without using the browser login form.
For local debugging only, the backend falls back to `local-read-token` when `STOCK_SCORER_READ_TOKEN` is unset. Production should set an explicit long random read token or replace this path with dynamic client login.

Use a real domain when you have one:

```bash
sudo env SERVER_NAME=stocks.example.com bash deploy/install-production.sh
```

## Runtime Commands

```bash
sudo systemctl status us-stock-scorer-api.service
sudo systemctl status us-stock-scorer-backtest.timer
sudo systemctl restart us-stock-scorer-api.service
sudo systemctl start us-stock-scorer-backtest.service
sudo systemctl reload nginx
```

`us-stock-scorer-backtest.timer` runs the CLI after the US market close window. It first syncs historical EOD bars for `BACKTEST_TICKERS`, then runs backtesting and strategy evolution. Results are written to `STOCK_SCORER_DB_PATH` or `apps/api/data/stock_scorer.sqlite3`.

If `BACKTEST_TICKERS` is not set in `apps/api/.env`, the deployed service falls back to:

```text
NVDA,AAPL,MSFT,AMZN,GOOGL,META,TSLA,AMD,INTC
```

Use this to inspect the deployed systemd source of truth:

```bash
systemctl cat us-stock-scorer-backtest.service
```

## URLs

- Admin app: `http://SERVER_IP/`
- API docs: `http://SERVER_IP/docs` (requires an admin Bearer token)
- API health: `http://SERVER_IP/health`

Make sure the server firewall or cloud security group allows inbound TCP port `80`.

## Verification

After each deploy, verify the Nginx config, backend service, direct backend health and proxied health:

```bash
sudo -n nginx -t
systemctl is-active us-stock-scorer-api.service
curl -fsS http://127.0.0.1:8000/health
curl -fsS -H "Host: us-stock-scorer.local" http://127.0.0.1/health
curl -fsSI -H "Host: us-stock-scorer.local" http://127.0.0.1/
```

The admin app is an SPA with deep links such as `/score`, `/strategy`, `/backtests`, and `/operations`; the Nginx template keeps those links working through `try_files $uri $uri/ /index.html`.
