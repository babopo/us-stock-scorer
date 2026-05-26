# Nginx Deployment

This deployment serves the React admin app from `/var/www/us-stock-scorer/admin` through Nginx and keeps the FastAPI backend running through systemd on `127.0.0.1:8000`.

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

`us-stock-scorer-backtest.timer` runs the CLI after the US market close window and writes results to `STOCK_SCORER_DB_PATH` or `apps/api/data/stock_scorer.sqlite3`.

## URLs

- Admin app: `http://SERVER_IP/`
- API docs: `http://SERVER_IP/docs` (requires an admin Bearer token)
- API health: `http://SERVER_IP/health`

Make sure the server firewall or cloud security group allows inbound TCP port `80`.
