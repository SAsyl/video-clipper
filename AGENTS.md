# Agent notes

## Backlog

- Planned features and bugs live in **GitHub Issues**: https://github.com/SAsyl/video-clipper/issues
- Before starting work, check open issues. When a new feature or idea comes up, create an issue instead of keeping it in chat or in code comments.
- Reference the issue in the commit or PR (`Closes #N`) so it closes on merge to `main`.

## Layout

- `app/` FastAPI backend (yt-dlp, ffmpeg, ffprobe wrappers). `web/` vanilla JS frontend served by the backend. `tests/` pytest + jsdom. See `README.md`.
- Setup: `uv sync --group dev && npm install`. Run: `./run.sh` (http://127.0.0.1:8420). Check: `uv run --group dev pytest && npm test`.

## Rules

- Single branch `main`; use short `feat/...` branches for larger changes.
- Never commit `.env`, `media/`, downloaded videos, or any tokens. The repo is public.
- Requires `ffmpeg`/`ffprobe` on `PATH` and `uv`; Python is pinned to 3.12 by `run.sh` (yt-dlp needs 3.11+).
- `node_modules`/`package.json` exist only for the jsdom stepper test; the frontend has no build step.
- Identifiers become filenames: always validate them through `app/storage.py` (`SAFE_ID_PATTERN` in `app/config.py`).
- Jobs are in memory (`app/jobs.py`); restarting the server drops job state, not files.
