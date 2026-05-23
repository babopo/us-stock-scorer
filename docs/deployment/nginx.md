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

Use a real domain when you have one:

```bash
sudo env SERVER_NAME=stocks.example.com bash deploy/install-production.sh
```

## Runtime Commands

```bash
sudo systemctl status us-stock-scorer-api.service
sudo systemctl restart us-stock-scorer-api.service
sudo systemctl reload nginx
```

## URLs

- Admin app: `http://SERVER_IP/`
- API docs: `http://SERVER_IP/docs`
- API health: `http://SERVER_IP/health`

Make sure the server firewall or cloud security group allows inbound TCP port `80`.
