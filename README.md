# zsxq-crawler

[中文文档](README_CN.md)

A crawler for [知识星球](https://zsxq.com) (Knowledge Planet) paid communities. Fetches topics, comments, images, and file attachments via the zsxq REST API.

## Features

- **Incremental crawling** — skips already-downloaded topics, safe to interrupt and resume
- **Full content** — topics, comments, images, and file attachments
- **Rate limit handling** — configurable delays, batch pauses, and automatic retry on API error 1059
- **Pagination** — cursor-based, crawls all history or a specified number of pages

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

### Run

```bash
python main.py                          # crawl everything
python main.py --max-pages 5            # limit to 5 pages (100 topics)
python main.py --no-images --no-files   # text and comments only
python main.py --no-comments            # skip comment fetching
python main.py -v                       # verbose logging
```

Press `Ctrl+C` to stop — progress is saved automatically.

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

## Output

```
output/{group_id}/
├── all_topics.json      # all topics merged, sorted by date
├── summary.json         # crawl statistics
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
