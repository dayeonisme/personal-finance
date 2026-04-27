# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Always use `python3` and `pip3` (not `python` / `pip`).

```bash
# Install dependencies
pip3 install -r requirements.txt
playwright install chromium

# Run all tests
pytest -v

# Run a single test file
pytest tests/test_database.py -v

# First-time Toss login (opens browser, saves session to data/toss_session.json)
python3 run.py --login

# Daily sync (automated via n8n, or run manually)
python3 run.py --days 7

# Dry run (fetch and categorize without writing to DB)
python3 run.py --dry-run

# Start dashboard
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501

# Start webhook server (for n8n integration)
python webhook_server.py

# Start n8n
docker-compose up -d
```

## Architecture

Data flows: Playwright (Toss) → `models.Transaction` list → `parser/categorizer.py` → `models.CategorizedTransaction` list → `db/database.py` (SQLite) → Streamlit dashboard.

`run.py` is the crawl entrypoint. It writes a two-phase `crawl_log` entry (INSERT on start, UPDATE on finish). Exit codes: 0=success, 1=unexpected error, 2=auth failure.

`webhook_server.py` is a tiny HTTP server at `127.0.0.1:9000` that n8n calls daily to trigger `run.py`. The Streamlit dashboard's "지금 동기화" button also POSTs to this endpoint.

All crawlers inherit `BaseCrawler` (context manager). To add a new source (Naver Pay etc.), create `crawler/naver_pay.py` implementing `login()`, `fetch_transactions()`, `logout()`.

## Security

- `data/`, `logs/`, `.env`, `n8n_data/` are gitignored — never commit them
- All local servers bound to `127.0.0.1` only (ports 8501, 9000, 5678)
- `.env` contains Toss credentials — restrict permissions: `icacls .env /inheritance:r /grant:r "%USERNAME%:F"`
