# zsxq Monitor — Real-time Content Monitoring Service

**Date:** 2026-03-30
**Status:** Approved

## Summary

A daemon service that polls the zsxq API at regular intervals, detects new topics, crawls them using existing crawler logic, and notifies the Web Viewer to hot-reload its data.

## Requirements

- Poll zsxq API every 5 minutes (configurable via CLI)
- Detect new topics by comparing against existing topic IDs on disk
- Crawl new topics with full media/comments support (configurable)
- Log all activity to stdout for journalctl consumption
- Notify Web Viewer to reload topics into memory after crawl
- Run as standalone script or systemd service
- Graceful shutdown on SIGTERM/SIGINT

## Architecture

```
monitor.py (CLI entry)
    ↓
zsxq_crawler/monitor.py (Monitor class)
    ├── reuses: Config, ZsxqClient, Crawler, Storage
    ├── polls: GET /groups/{id}/topics?scope=all&count=20
    ├── crawls: Crawler._process_topic() for each new topic
    └── notifies: POST http://localhost:5000/api/reload

web/app.py
    └── new endpoint: POST /api/reload → reloads topics from disk
```

**Data flow:**
1. Monitor polls API → gets latest 20 topics
2. Filters against `storage.load_existing_topic_ids()`
3. For each new topic: `Crawler._process_topic()` → `storage.save_topic()`
4. After batch: `storage.save_all_topics()` to merge into `all_topics.json`
5. POST `/api/reload` → Web App reloads from disk

## Component Design

### 1. `zsxq_crawler/monitor.py` — Monitor Class

```python
class Monitor:
    __init__(config, client, storage, interval=300, notify_url=None)

    run()          # Main loop: poll → detect → crawl → notify, never exits on error
    _poll()        # Fetch latest 1 page (20 topics), return list of new raw topics
    _crawl_new()   # Process each new topic via Crawler logic
    _notify_web()  # POST to web app /api/reload endpoint
    _log_stats()   # Log: found N new topics, crawled successfully
```

**Key behaviors:**
- Each poll fetches only 1 page (20 topics) — sufficient for 5-min intervals
- Exceptions (network, API 1059, etc.) are caught and logged, never crash the loop
- Signal handling: SIGTERM and SIGINT set a `_running = False` flag for clean exit
- After crawling new topics, calls `storage.save_all_topics()` to persist
- Cumulative stats tracked across the session lifetime

### 2. `monitor.py` — CLI Entry Point

```
argparse parameters:
  --interval N       Polling interval in seconds (default: 300)
  --no-images        Skip image downloads
  --no-files         Skip file downloads
  --no-comments      Skip comment fetching
  --notify-url URL   Web App reload URL (default: http://localhost:5000/api/reload)
  --no-notify        Disable web app notification
  -v / --verbose     Debug logging
```

**Flow:**
1. Load Config from `.env` (reuses existing `Config.from_env()`)
2. Apply CLI overrides (same pattern as `main.py`)
3. Create ZsxqClient → Storage → Monitor
4. Call `monitor.run()` — blocks in polling loop
5. On Ctrl+C: print cumulative stats and exit cleanly

### 3. Web App Reload Endpoint

**Changes to `web/app.py`:**

- Extract existing startup topic-loading logic into a `_load_topics()` function
- Call `_load_topics()` at startup (existing behavior preserved)
- New endpoint `POST /api/reload`:
  - Calls `_load_topics()` to refresh in-memory topic data
  - Returns `{"success": true, "topics_count": N}`
- Optional token auth via `ZSXQ_RELOAD_TOKEN` env var (if set, request must include matching `Authorization: Bearer <token>` header)

### 4. systemd Configuration

Three files in `deploy/`:

**`deploy/zsxq-monitor.service`**
- `ExecStart`: python monitor.py
- `Restart=on-failure`, `RestartSec=30`
- `After=network-online.target`
- `WorkingDirectory` and `EnvironmentFile` for `.env`

**`deploy/zsxq-web.service`**
- `ExecStart`: python web/app.py
- `Restart=on-failure`

**`deploy/zsxq.target`**
- `Wants=zsxq-monitor.service zsxq-web.service`
- Single command to manage both: `systemctl --user start/stop zsxq.target`
- `systemctl --user enable zsxq.target` for boot autostart

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Network timeout | Log warning, wait for next poll |
| API error 1059 | Log warning, wait for next poll (no retry within poll) |
| Auth error (401) | Log error, exit with code 1 (cookie expired) |
| Web notify fails | Log warning, continue (web app may be down) |
| SIGTERM/SIGINT | Set `_running=False`, finish current operation, exit cleanly |

## Environment Variables

All existing `.env` variables apply. New additions:

| Variable | Default | Description |
|----------|---------|-------------|
| `ZSXQ_MONITOR_INTERVAL` | `300` | Polling interval in seconds |
| `ZSXQ_RELOAD_TOKEN` | (empty) | Optional auth token for /api/reload |

## Testing Strategy

- **Unit tests:** Monitor._poll() with mocked client responses (new topics, empty, errors)
- **Unit tests:** Monitor._notify_web() with mocked HTTP calls
- **Integration tests:** POST /api/reload endpoint returns correct response and reloads data
- **Integration tests:** Full monitor cycle with mocked API returning new topics
- Target: 80%+ coverage on new code
