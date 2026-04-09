# zsxq-crawler

[中文文档](README.md)

A crawler and toolkit for [知识星球](https://zsxq.com) (Knowledge Planet) paid communities. Fetches topics, comments, images, and file attachments via the zsxq REST API — then browse them locally with a web viewer, monitor for new content in real time, or export to a Markdown knowledge base.

## Features

- **Incremental crawling** — skips already-downloaded topics, safe to interrupt and resume
- **Full content** — topics, comments, images, and file attachments
- **Rate limit handling** — configurable delays, batch pauses, and automatic retry on API error 1059
- **Web viewer** — Notion-style local UI with search, filtering, bookmarks, tags, and image lightbox
- **Real-time monitor** — polls for new topics and auto-refreshes the web viewer
- **Knowledge base export** — converts topics to Obsidian-compatible Markdown with indexes
- **systemd deployment** — run monitor + web viewer as user services

## Quick Start

```bash
git clone https://github.com/stoicneko/zsxq-crawler.git
cd zsxq-crawler
python3 -m venv venv
source venv/bin/activate        # bash/zsh
# source venv/bin/activate.fish  # fish shell
pip install -r requirements.txt
```

### Get Your Cookie

1. Open https://wx.zsxq.com in a browser and log in (WeChat QR scan)
2. Open DevTools (F12) → Network tab
3. Find any request to `api.zsxq.com`
4. Copy the `zsxq_access_token=...` value from the Cookie header

### Configure

```bash
cp .env.example .env
# Edit .env — set ZSXQ_COOKIE and ZSXQ_GROUP_ID
```

### Run the Crawler

```bash
python main.py                          # crawl everything
python main.py --max-pages 5            # limit to 5 pages (100 topics)
python main.py --no-images --no-files   # text and comments only
python main.py --no-comments            # skip comment fetching
python main.py -v                       # verbose logging
```

Press `Ctrl+C` to stop — progress is saved automatically.

## Web Viewer

A local Flask app that lets you browse crawled topics in a clean, Notion-inspired interface.

```bash
python web/app.py                       # start at http://localhost:5000
```

**Capabilities:**
- Infinite-scroll topic list with full-text search
- Filter by type (talk / Q&A / task), date range, digested status
- Star bookmarks and custom tags (persisted to `user_data.json`)
- Image lightbox with zoom (mouse wheel / +/-), pan (drag), and keyboard shortcuts
- `/api/reload` endpoint to refresh topics from disk (used by the monitor)

## Real-time Monitor

A polling service that watches for new topics and automatically downloads them.

```bash
python monitor.py                       # poll every 5 minutes (default)
python monitor.py --interval 60         # poll every 60 seconds
python monitor.py --no-notify           # don't notify web app on new topics
python monitor.py --no-images --no-files   # lightweight mode
python monitor.py -v                    # verbose logging
```

When new topics are found, the monitor processes them through the crawler pipeline and sends a reload signal to the web viewer so it picks up changes instantly.

### systemd Deployment

Run both monitor and web viewer as user services:

```bash
# Install service files
cp deploy/*.service deploy/*.target ~/.config/systemd/user/

# Start both services
systemctl --user start zsxq.target
systemctl --user enable zsxq.target     # enable on boot

# Check logs
journalctl --user -u zsxq-monitor -f
journalctl --user -u zsxq-web -f
```

## Knowledge Base Export

Convert crawled topics into Obsidian-compatible Markdown files with auto-generated indexes.

```bash
python convert_to_kb.py                           # auto-detect group, output to knowledge-base/
python convert_to_kb.py --output-dir my-kb         # custom output directory
python convert_to_kb.py --source-dir output        # custom source directory
python convert_to_kb.py --group-id 12345           # specify group ID
```

**Generates:**
- Individual Markdown files per topic (with metadata, images, comments)
- Index by month, by author, and by type
- Symlinked images directory for Obsidian attachment support

## Configuration

All settings are in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ZSXQ_COOKIE` | *(required)* | Browser cookie with `zsxq_access_token` |
| `ZSXQ_GROUP_ID` | *(required)* | Group ID from the community URL |
| `ZSXQ_REQUEST_DELAY` | `3` | Seconds between requests |
| `ZSXQ_BATCH_SIZE` | `15` | Requests per batch before pausing |
| `ZSXQ_BATCH_PAUSE` | `180` | Seconds to pause between batches |
| `ZSXQ_DOWNLOAD_IMAGES` | `true` | Download images |
| `ZSXQ_DOWNLOAD_FILES` | `true` | Download file attachments |
| `ZSXQ_CRAWL_COMMENTS` | `true` | Fetch comments |
| `ZSXQ_OUTPUT_DIR` | `output` | Output directory |
| `ZSXQ_MAX_PAGES` | `0` | Max pages to crawl (0 = unlimited) |
| `ZSXQ_MONITOR_INTERVAL` | `300` | Monitor polling interval in seconds |
| `ZSXQ_RELOAD_TOKEN` | *(empty)* | Bearer token for `/api/reload` auth |

## Output

```
output/{group_id}/
├── all_topics.json      # all topics merged, sorted by date
├── summary.json         # crawl statistics
├── user_data.json       # stars and tags from web viewer
├── topics/              # one JSON file per topic
│   ├── {topic_id}.json
│   └── ...
├── images/              # downloaded images
│   ├── {topic_id}_{image_id}.jpg
│   └── ...
└── files/               # downloaded attachments
    ├── {file_id}_{filename}
    └── ...
```

## License

MIT
