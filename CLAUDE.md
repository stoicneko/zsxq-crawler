# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

知识星球 (zsxq.com) crawler — scrapes topics, comments, images, and files from paid communities using the zsxq REST API (`api.zsxq.com/v2`). Authentication via browser cookie.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate.fish   # fish shell (this project uses fish)
pip install -r requirements.txt

# Run
python main.py                          # full crawl
python main.py --max-pages 5            # limit pages
python main.py --no-images --no-files   # text + comments only
python main.py -v                       # verbose (includes httpcore debug logs)

# Configuration: copy .env.example to .env and set ZSXQ_COOKIE and ZSXQ_GROUP_ID
```

## Architecture

```
main.py           → CLI entry point, argparse, orchestration
zsxq_crawler/
  config.py       → frozen dataclass Config, loaded from .env via python-dotenv
  client.py       → ZsxqClient: httpx-based HTTP client with rate limiting + retry
  crawler.py      → Crawler: pagination, topic processing, media download, comment fetch
  storage.py      → Storage: JSON persistence, file/image download paths
```

**Data flow:** `main.py` creates `Config` → `ZsxqClient` → `Crawler` → `Storage`

**Key behaviors:**
- Cursor-based pagination via `end_time` parameter (last topic's `create_time` minus 1ms)
- Incremental crawling: skips already-saved topic IDs from `all_topics.json`
- Rate limiting: configurable delay between requests + batch pause after N requests
- API error 1059 triggers automatic retry with exponential backoff (2s/5s/10s, up to 6 retries)
- X-Signature computed as `SHA1("{api_path} {timestamp_ms} zsxqapi2020")`

**Output structure:** `output/{group_id}/` with `topics/`, `images/`, `files/` subdirs, plus `all_topics.json` and `summary.json`

## API Notes

- Base URL: `https://api.zsxq.com/v2`
- Topic types: `talk`, `q&a`, `task`, `solution` — each has different JSON nesting for text/images/files
- Cookie obtained from browser DevTools after WeChat QR login; token field is `zsxq_access_token`
- Error code 1059 = rate limit / internal error (not HTTP status, embedded in JSON response body with HTTP 200)
