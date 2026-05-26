#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/home/admin/us-stock-scorer"
APP_USER="${APP_USER:-admin}"
SERVER_NAME="${SERVER_NAME:-us-stock-scorer.local}"
NGINX_CONF_NAME="us-stock-scorer.conf"
TMP_NGINX_CONF="/tmp/${NGINX_CONF_NAME}"
WEB_ROOT="/var/www/us-stock-scorer/admin"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx is not installed. Install nginx first, then rerun this script." >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl is required for the production service." >&2
  exit 1
fi

if ! id "${APP_USER}" >/dev/null 2>&1; then
  echo "Application user does not exist: ${APP_USER}" >&2
  exit 1
fi

cd "${APP_ROOT}"

if ! runuser -u "${APP_USER}" -- bash -lc "cd '${APP_ROOT}' && command -v pnpm >/dev/null 2>&1"; then
  echo "pnpm is not installed or not in ${APP_USER}'s PATH." >&2
  exit 1
fi

if [ ! -x "${APP_ROOT}/apps/api/.venv/bin/uvicorn" ]; then
  echo "API virtualenv is missing uvicorn. Create apps/api/.venv and install the API first." >&2
  exit 1
fi

systemctl stop us-stock-scorer-api.service >/dev/null 2>&1 || true
systemctl stop us-stock-scorer-backtest.timer >/dev/null 2>&1 || true

mapfile -t existing_api_pids < <(
  pgrep -u "${APP_USER}" -f "stock_scorer.app:app.*--port 8000" || true
)
if [ "${#existing_api_pids[@]}" -gt 0 ]; then
  kill "${existing_api_pids[@]}" 2>/dev/null || true
fi

runuser -u "${APP_USER}" -- bash -lc "cd '${APP_ROOT}' && pnpm --filter @stock-scorer/api-client build"
runuser -u "${APP_USER}" -- bash -lc "cd '${APP_ROOT}' && pnpm --filter @stock-scorer/admin build"
runuser -u "${APP_USER}" -- bash -lc "cd '${APP_ROOT}/apps/api' && .venv/bin/python -m pip install -e ."

rm -rf "${WEB_ROOT}"
mkdir -p "${WEB_ROOT}"
cp -a "${APP_ROOT}/apps/admin/dist/." "${WEB_ROOT}/"
chown -R root:root /var/www/us-stock-scorer
find /var/www/us-stock-scorer -type d -exec chmod 0755 {} +
find /var/www/us-stock-scorer -type f -exec chmod 0644 {} +

sed "s/__SERVER_NAME__/${SERVER_NAME}/g" \
  "${APP_ROOT}/deploy/nginx/us-stock-scorer.conf.template" > "${TMP_NGINX_CONF}"

install -m 0644 "${APP_ROOT}/deploy/systemd/us-stock-scorer-api.service" \
  /etc/systemd/system/us-stock-scorer-api.service
install -m 0644 "${APP_ROOT}/deploy/systemd/us-stock-scorer-backtest.service" \
  /etc/systemd/system/us-stock-scorer-backtest.service
install -m 0644 "${APP_ROOT}/deploy/systemd/us-stock-scorer-backtest.timer" \
  /etc/systemd/system/us-stock-scorer-backtest.timer

if [ -d /etc/nginx/conf.d ]; then
  install -m 0644 "${TMP_NGINX_CONF}" "/etc/nginx/conf.d/${NGINX_CONF_NAME}"
elif [ -d /etc/nginx/sites-available ] && [ -d /etc/nginx/sites-enabled ]; then
  install -m 0644 "${TMP_NGINX_CONF}" "/etc/nginx/sites-available/${NGINX_CONF_NAME}"
  ln -sfn "/etc/nginx/sites-available/${NGINX_CONF_NAME}" "/etc/nginx/sites-enabled/${NGINX_CONF_NAME}"
else
  echo "Could not find /etc/nginx/conf.d or Debian-style sites directories." >&2
  exit 1
fi

systemctl daemon-reload
systemctl enable --now us-stock-scorer-api.service
systemctl enable --now us-stock-scorer-backtest.timer
systemctl enable --now nginx
nginx -t
systemctl reload nginx

echo "US Stock Scorer is deployed through Nginx."
echo "Server name: ${SERVER_NAME}"
