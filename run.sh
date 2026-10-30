#!/usr/bin/env bash
# Start the Video Clipper web app on http://127.0.0.1:8420
set -euo pipefail
cd "$(dirname "$0")"
exec uv run --python 3.12 uvicorn app.main:app --host 127.0.0.1 --port 8420 "$@"
