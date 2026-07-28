#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAMF_CLIENT_DIR="$SCRIPT_DIR/../jamf_client"

cd "$SCRIPT_DIR"

echo "==> Pulling latest run_lookup..."
git pull --ff-only

if [ -d "$JAMF_CLIENT_DIR/.git" ]; then
  echo "==> Pulling latest jamf_client..."
  (cd "$JAMF_CLIENT_DIR" && git pull --ff-only)
else
  echo "==> jamf_client not found at $JAMF_CLIENT_DIR, skipping"
fi

if [ -x "$SCRIPT_DIR/.venv/bin/pip" ]; then
  echo "==> Updating packages..."
  "$SCRIPT_DIR/.venv/bin/pip" install -r requirements.txt --upgrade
else
  echo "==> No .venv found at $SCRIPT_DIR/.venv, skipping package update"
fi

echo "==> Done."
