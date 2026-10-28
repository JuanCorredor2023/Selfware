#!/usr/bin/env bash
# Update the app on the VM: pull, install, build the dashboard, restart the API.
# Usage:  PUBLIC_URL=http://<vm-ip-or-domain> ./deploy/deploy.sh
# Run it from the app checkout (/srv/selfware/app). It never touches the data folder.
set -euo pipefail

: "${PUBLIC_URL:?set PUBLIC_URL to the public origin, e.g. http://203.0.113.10}"
BRANCH="${BRANCH:-main-vm}"

git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

uv sync --locked

(
  cd web
  npm ci
  VITE_API_URL="$PUBLIC_URL" npm run build
)

sudo systemctl restart selfware-api
sleep 3
curl -fsS http://127.0.0.1:8000/health && echo " <- API is up"
echo "Dashboard: $PUBLIC_URL"
