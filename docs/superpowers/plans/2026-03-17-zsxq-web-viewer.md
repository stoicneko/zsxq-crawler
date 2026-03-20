# ZSXQ Web Viewer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Flask web app to browse, search, filter, and bookmark 16K zsxq topics with a minimalist Notion-like UI.

**Architecture:** Flask backend loads all topic JSON files into memory at startup, provides REST APIs for paginated browsing/searching/filtering. Single-column centered layout with vanilla HTML/CSS/JS frontend. User data (stars, tags) persisted to a local JSON file.

**Tech Stack:** Flask, Jinja2, vanilla JS/CSS, Python standard library for search

---

## File Structure

```
web/
  app.py              → Flask app: routes, API endpoints, topic loading, search/filter logic
  static/
    style.css          → Minimalist CSS (Notion-like theme, responsive, lightbox)
    app.js             → Frontend: infinite scroll, search, filter, star/tag, lightbox
  templates/
    index.html         → Main page template (Jinja2)
```

**Existing files referenced (read-only):**
- `output/{group_id}/topics/*.json` — topic data source
- `output/{group_id}/images/*` — image files served statically

**New data file:**
- `output/{group_id}/user_data.json` — stars and tags persistence

---

### Task 1: Flask App Skeleton + Topic Loading

**Files:**
- Create: `web/app.py`
- Create: `web/templates/index.html` (minimal placeholder)

- [ ] **Step 1: Add flask to requirements.txt**

Append `flask>=3.0.0` to `requirements.txt`.

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 3: Create `web/app.py` with topic loading**

```python
"""ZSXQ Web Viewer — Flask application."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global state
TOPICS: list[dict] = []
TOPICS_BY_ID: dict[str, dict] = {}
USER_DATA: dict = {"stars": [], "tags": {}}
GROUP_ID: str = ""
OUTPUT_DIR: Path = Path("output")


def load_topics() -> None:
    """Load all topic JSON files into memory."""
    global TOPICS, TOPICS_BY_ID, GROUP_ID, OUTPUT_DIR

    GROUP_ID = os.environ.get("ZSXQ_GROUP_ID", "")
    output_base = os.environ.get("ZSXQ_OUTPUT_DIR", "output")
    OUTPUT_DIR = Path(output_base)

    if not GROUP_ID:
        # Auto-detect: use first subdirectory in output/
        candidates = [d for d in OUTPUT_DIR.iterdir() if d.is_dir()]
        if candidates:
            GROUP_ID = candidates[0].name
        else:
            logger.error("No group directory found in %s", OUTPUT_DIR)
            return

    topics_dir = OUTPUT_DIR / GROUP_ID / "topics"
    if not topics_dir.exists():
        logger.error("Topics directory not found: %s", topics_dir)
        return

    topics = []
    for f in topics_dir.glob("*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                topic = json.load(fh)
                topics.append(topic)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s: %s", f, e)

    topics.sort(key=lambda t: t.get("create_time", ""), reverse=True)
    TOPICS = topics
    TOPICS_BY_ID = {t["topic_id"]: t for t in topics}
    logger.info("Loaded %d topics for group %s", len(TOPICS), GROUP_ID)


def load_user_data() -> None:
    """Load user stars and tags from disk."""
    global USER_DATA
    path = OUTPUT_DIR / GROUP_ID / "user_data.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                USER_DATA = json.load(f)
        except (json.JSONDecodeError, OSError):
            USER_DATA = {"stars": [], "tags": {}}
    else:
        USER_DATA = {"stars": [], "tags": {}}


def save_user_data() -> None:
    """Persist user stars and tags to disk."""
    path = OUTPUT_DIR / GROUP_ID / "user_data.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(USER_DATA, f, ensure_ascii=False, indent=2)


def parse_embedded_tags(text: str) -> str:
    """Convert <e type="web" .../> tags to HTML links."""
    def replace_tag(m: re.Match) -> str:
        attrs = m.group(0)
        href_m = re.search(r'href="([^"]*)"', attrs)
        title_m = re.search(r'title="([^"]*)"', attrs)
        href = href_m.group(1) if href_m else "#"
        title = title_m.group(1) if title_m else href
        return f'<a href="{href}" target="_blank" rel="noopener">{title}</a>'

    return re.sub(r'<e\s+type="web"[^/]*/>', replace_tag, text)


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html", total=len(TOPICS), group_id=GROUP_ID)


@app.route("/api/topics")
def api_topics():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    q = request.args.get("q", "").strip()
    topic_type = request.args.get("type", "")
    digested = request.args.get("digested", "")
    since = request.args.get("since", "")
    until = request.args.get("until", "")
    tag = request.args.get("tag", "")
    starred = request.args.get("starred", "")

    filtered = TOPICS

    # Search
    if q:
        q_lower = q.lower()
        filtered = [
            t for t in filtered
            if q_lower in t.get("text", "").lower()
            or q_lower in t.get("answer", {}).get("text", "").lower()
            or any(q_lower in c.get("text", "").lower() for c in t.get("comments", []))
        ]

    # Filter by type
    if topic_type:
        filtered = [t for t in filtered if t.get("type") == topic_type]

    # Filter by digested
    if digested == "true":
        filtered = [t for t in filtered if t.get("digested")]

    # Filter by date range
    if since:
        filtered = [t for t in filtered if t.get("create_time", "") >= since]
    if until:
        filtered = [t for t in filtered if t.get("create_time", "") <= until]

    # Filter by star
    if starred == "true":
        filtered = [t for t in filtered if t["topic_id"] in USER_DATA["stars"]]

    # Filter by tag
    if tag:
        tagged_ids = {
            tid for tid, tags in USER_DATA["tags"].items() if tag in tags
        }
        filtered = [t for t in filtered if t["topic_id"] in tagged_ids]

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    page_topics = filtered[start:end]

    # Enrich with user data
    results = []
    for t in page_topics:
        enriched = {
            **t,
            "text_html": parse_embedded_tags(t.get("text", "")),
            "is_starred": t["topic_id"] in USER_DATA["stars"],
            "user_tags": USER_DATA["tags"].get(t["topic_id"], []),
        }
        if "answer" in t and t["answer"]:
            enriched["answer"] = {
                **t["answer"],
                "text_html": parse_embedded_tags(t["answer"].get("text", "")),
            }
        results.append(enriched)

    return jsonify({
        "topics": results,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": end < total,
    })


@app.route("/api/topics/<topic_id>/star", methods=["POST"])
def api_toggle_star(topic_id: str):
    if topic_id not in TOPICS_BY_ID:
        return jsonify({"error": "Topic not found"}), 404
    stars = USER_DATA["stars"]
    if topic_id in stars:
        stars.remove(topic_id)
        is_starred = False
    else:
        stars.append(topic_id)
        is_starred = True
    save_user_data()
    return jsonify({"is_starred": is_starred})


@app.route("/api/topics/<topic_id>/tags", methods=["POST"])
def api_update_tags(topic_id: str):
    if topic_id not in TOPICS_BY_ID:
        return jsonify({"error": "Topic not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    action = data.get("action", "add")
    tag_name = data.get("tag", "").strip()
    if not tag_name:
        return jsonify({"error": "Tag name required"}), 400

    tags = USER_DATA["tags"]
    topic_tags = tags.get(topic_id, [])

    if action == "add" and tag_name not in topic_tags:
        topic_tags.append(tag_name)
    elif action == "remove" and tag_name in topic_tags:
        topic_tags.remove(tag_name)

    if topic_tags:
        tags[topic_id] = topic_tags
    elif topic_id in tags:
        del tags[topic_id]

    save_user_data()
    return jsonify({"tags": tags.get(topic_id, [])})


@app.route("/api/tags")
def api_all_tags():
    all_tags: set[str] = set()
    for tag_list in USER_DATA["tags"].values():
        all_tags.update(tag_list)
    return jsonify({"tags": sorted(all_tags)})


@app.route("/api/stats")
def api_stats():
    type_counts: dict[str, int] = {}
    digested_count = 0
    total_images = 0
    total_comments = 0
    for t in TOPICS:
        tp = t.get("type", "unknown")
        type_counts[tp] = type_counts.get(tp, 0) + 1
        if t.get("digested"):
            digested_count += 1
        total_images += len(t.get("images", []))
        total_comments += len(t.get("comments", []))

    return jsonify({
        "total_topics": len(TOPICS),
        "type_counts": type_counts,
        "digested_count": digested_count,
        "total_images": total_images,
        "total_comments": total_comments,
        "total_stars": len(USER_DATA["stars"]),
        "total_tags": len(USER_DATA["tags"]),
    })


@app.route("/images/<path:filename>")
def serve_image(filename: str):
    images_dir = OUTPUT_DIR / GROUP_ID / "images"
    return send_from_directory(str(images_dir), filename)


# --- Startup ---

with app.app_context():
    load_topics()
    load_user_data()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    load_topics()
    load_user_data()
    app.run(debug=True, port=5000)
```

- [ ] **Step 4: Create minimal `web/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZSXQ Viewer</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>ZSXQ Viewer</h1>
            <p>{{ total }} topics</p>
        </header>
        <div id="topics"></div>
    </div>
    <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 5: Create placeholder static files**

Create empty `web/static/style.css` and `web/static/app.js`.

- [ ] **Step 6: Test server starts and loads topics**

Run: `cd /home/zhaole_lv/Documents/zsxq && python -c "from web.app import app, TOPICS; print(f'Loaded {len(TOPICS)} topics')"`
Expected: `Loaded 15976 topics` (approximately)

- [ ] **Step 7: Commit**

```bash
git add web/ requirements.txt
git commit -m "feat: flask app skeleton with topic loading and API endpoints"
```

---

### Task 2: CSS Styling (Minimalist Notion-like Theme)

**Files:**
- Create: `web/static/style.css`

- [ ] **Step 1: Write the complete CSS**

Key design:
- Max-width 768px centered container
- System font stack, 16px base
- Cards with subtle bottom border (no box shadow)
- Q&A answer section with light gray background + left border
- Image grid (max 3 per row, thumbnails)
- Lightbox overlay for image zoom
- Responsive: full-width on mobile
- Filter bar: horizontal, collapsible
- Star/tag buttons: subtle, icon-based
- Infinite scroll loading indicator
- Color palette: white bg, #37352f text, #f7f6f3 secondary bg, #2eaadc accent

- [ ] **Step 2: Verify CSS loads**

Run: `cd /home/zhaole_lv/Documents/zsxq && python web/app.py &` then check `curl -s http://localhost:5000/static/style.css | head -5`

- [ ] **Step 3: Commit**

```bash
git add web/static/style.css
git commit -m "feat: minimalist Notion-like CSS theme"
```

---

### Task 3: HTML Template

**Files:**
- Modify: `web/templates/index.html`

- [ ] **Step 1: Write the full template**

Structure:
```
header: title + stats badge
search bar: input + search button
filter bar: type dropdown, digested toggle, date range, tag select, star filter
topics container: #topics div (populated by JS)
lightbox overlay: hidden by default
tag modal: hidden by default (for adding tags)
loading spinner
```

- [ ] **Step 2: Commit**

```bash
git add web/templates/index.html
git commit -m "feat: main page template with search, filter, and controls"
```

---

### Task 4: Frontend JavaScript

**Files:**
- Create: `web/static/app.js`

- [ ] **Step 1: Write the complete JavaScript**

Modules (all in one file, organized by section):
1. **State**: current page, filters, loading flag
2. **API**: `fetchTopics(params)`, `toggleStar(id)`, `updateTag(id, action, tag)`, `fetchTags()`, `fetchStats()`
3. **Rendering**: `renderTopic(topic)` → HTML string, `renderComment(comment)`, `renderImages(images)`
4. **Text processing**: convert `\n` to `<br>`, parse embedded `<e>` tags (already done server-side via `text_html`)
5. **Infinite scroll**: `IntersectionObserver` on sentinel element, loads next page
6. **Search**: debounced input handler, resets page and reloads
7. **Filters**: event listeners on type/digested/date/tag/star controls, resets page and reloads
8. **Lightbox**: click image → show overlay with full-size image, click/ESC to close
9. **Star**: click handler → POST to API, toggle icon
10. **Tags**: click handler → show modal, add/remove tags via API

- [ ] **Step 2: Test core flow in browser**

Run: `cd /home/zhaole_lv/Documents/zsxq && python web/app.py`
Open: `http://localhost:5000`
Expected: Topics load, infinite scroll works, images display

- [ ] **Step 3: Commit**

```bash
git add web/static/app.js
git commit -m "feat: frontend JS with infinite scroll, search, filter, star, and tags"
```

---

### Task 5: Integration Testing

**Files:**
- Create: `tests/test_web.py`

- [ ] **Step 1: Write tests**

Test cases:
1. `test_index_returns_200` — GET / returns 200
2. `test_api_topics_pagination` — GET /api/topics returns correct page structure
3. `test_api_topics_search` — GET /api/topics?q=keyword filters results
4. `test_api_topics_filter_type` — GET /api/topics?type=talk filters by type
5. `test_api_topics_filter_digested` — GET /api/topics?digested=true
6. `test_api_toggle_star` — POST /api/topics/{id}/star toggles star
7. `test_api_update_tags` — POST /api/topics/{id}/tags adds/removes tags
8. `test_api_all_tags` — GET /api/tags returns all tags
9. `test_api_stats` — GET /api/stats returns correct stats
10. `test_serve_image` — GET /images/filename returns image or 404
11. `test_parse_embedded_tags` — embedded `<e>` tags convert to `<a>` links

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_web.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_web.py
git commit -m "test: web viewer API and rendering tests"
```

---

### Task 6: Polish and Final Verification

- [ ] **Step 1: Add `web` run command to help text**

Add instructions to run the web viewer in the project. Update `.env.example` if needed.

- [ ] **Step 2: Manual verification checklist**

- [ ] Server starts and loads all topics
- [ ] Topics display with correct formatting
- [ ] Q&A topics show answer with gray background
- [ ] Images display as thumbnails, click opens lightbox
- [ ] Search works for Chinese text
- [ ] Filter by type (talk/q&a) works
- [ ] Filter by digested works
- [ ] Date range filter works
- [ ] Star toggle works and persists
- [ ] Tag add/remove works and persists
- [ ] Filter by star works
- [ ] Filter by tag works
- [ ] Infinite scroll loads more topics
- [ ] Responsive on mobile viewport

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: zsxq web viewer with browse, search, filter, and bookmarks"
```
