"""Flask web app for browsing zsxq crawled data."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory

load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(os.getenv("ZSXQ_OUTPUT_DIR", "output"))
_explicit_group_id = os.getenv("ZSXQ_GROUP_ID", "")


def _detect_group_id() -> str:
    """Return the group_id directory found inside output/, preferring env var."""
    if _explicit_group_id:
        return _explicit_group_id
    if OUTPUT_DIR.exists():
        candidates = [p for p in OUTPUT_DIR.iterdir() if p.is_dir()]
        if candidates:
            return candidates[0].name
    return ""


GROUP_ID = _detect_group_id()
GROUP_DIR = OUTPUT_DIR / GROUP_ID
TOPICS_DIR = GROUP_DIR / "topics"
IMAGES_DIR = GROUP_DIR / "images"
USER_DATA_FILE = GROUP_DIR / "user_data.json"

# ---------------------------------------------------------------------------
# Tag parsing
# ---------------------------------------------------------------------------

_WEB_TAG_RE = re.compile(r'<e type="web" href="([^"]*)" title="([^"]*)" />')


def _parse_embedded_tags(text: str) -> str:
    """Replace <e type="web" .../> tags with HTML anchor elements."""

    def _replace(m: re.Match) -> str:
        href = urllib.parse.unquote(m.group(1))
        title = urllib.parse.unquote(m.group(2)) or href
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{title}</a>'

    # Escape < and > for plain text parts while keeping the replaced anchors safe.
    # Strategy: split on the tag, escape each plain segment, reassemble.
    parts = _WEB_TAG_RE.split(text)
    # _WEB_TAG_RE has 2 groups so split produces: [plain, href, title, plain, href, title, ...]
    result_parts: list[str] = []
    i = 0
    while i < len(parts):
        # Plain text segment — HTML-escape and convert newlines
        segment = parts[i]
        segment = segment.replace("&", "&amp;")
        segment = segment.replace("<", "&lt;").replace(">", "&gt;")
        segment = segment.replace("\n", "<br>")
        result_parts.append(segment)
        if i + 2 < len(parts):
            href = urllib.parse.unquote(parts[i + 1])
            title = urllib.parse.unquote(parts[i + 2]) or href
            result_parts.append(
                f'<a href="{href}" target="_blank" rel="noopener noreferrer">{title}</a>'
            )
            i += 3
        else:
            break
    return "".join(result_parts)


# ---------------------------------------------------------------------------
# In-memory topic store
# ---------------------------------------------------------------------------

# List of topic dicts loaded from disk, sorted newest-first.
_topics: list[dict[str, Any]] = []
# Map topic_id -> index in _topics for O(1) lookup.
_topic_index: dict[str, int] = {}


def load_topics() -> None:
    """Load all topics from the topics directory into memory."""
    global _topics, _topic_index
    if not TOPICS_DIR.exists():
        app.logger.warning("Topics directory not found: %s", TOPICS_DIR)
        return

    loaded: list[dict[str, Any]] = []
    for path in TOPICS_DIR.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                topic = json.load(f)
            loaded.append(topic)
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("Failed to load %s: %s", path, exc)

    # Sort newest first
    loaded.sort(key=lambda t: t.get("create_time", ""), reverse=True)
    _topics = loaded
    _topic_index = {t["topic_id"]: i for i, t in enumerate(_topics)}
    app.logger.info("Loaded %d topics from %s", len(_topics), TOPICS_DIR)


# ---------------------------------------------------------------------------
# User data (stars + tags) persistence
# ---------------------------------------------------------------------------

def _load_user_data() -> dict[str, Any]:
    """Load user_data.json from disk, returning empty structure on missing/error."""
    if USER_DATA_FILE.exists():
        try:
            with USER_DATA_FILE.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("Failed to read user_data.json: %s", exc)
    return {"stars": {}, "tags": {}}


def _save_user_data(data: dict[str, Any]) -> None:
    """Persist user_data to disk."""
    USER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USER_DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(USER_DATA_FILE)


# ---------------------------------------------------------------------------
# Topic enrichment
# ---------------------------------------------------------------------------

def _enrich(topic: dict[str, Any], user_data: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with extra display fields added."""
    tid = topic["topic_id"]
    text = topic.get("text") or ""
    enriched = dict(topic)
    enriched["text_html"] = _parse_embedded_tags(text)

    # Also enrich answer text if present
    answer = topic.get("answer")
    if answer and answer.get("text"):
        enriched["answer"] = dict(answer)
        enriched["answer"]["text_html"] = _parse_embedded_tags(answer["text"])

    enriched["is_starred"] = bool(user_data["stars"].get(tid))
    enriched["user_tags"] = list(user_data["tags"].get(tid, []))
    return enriched


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _matches_query(topic: dict[str, Any], q: str) -> bool:
    """Case-insensitive substring search across text, answer, and comments."""
    q_lower = q.lower()
    if q_lower in (topic.get("text") or "").lower():
        return True
    answer = topic.get("answer") or {}
    if q_lower in (answer.get("text") or "").lower():
        return True
    for comment in topic.get("comments") or []:
        if q_lower in (comment.get("text") or "").lower():
            return True
    return False


def _parse_date(s: str) -> datetime:
    """Parse ISO 8601 date/datetime string; returns UTC-aware datetime."""
    # Support both date-only "2024-03-16" and full ISO with offset
    s = s.strip()
    if len(s) == 10:
        return datetime(int(s[:4]), int(s[5:7]), int(s[8:10]), tzinfo=timezone.utc)
    # Try ISO format with +HH:MM offset (Python 3.7+)
    try:
        # Replace trailing Z
        s_norm = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s_norm)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index() -> str:
    """Main SPA page."""
    return render_template("index.html", group_id=GROUP_ID)


@app.route("/api/topics")
def api_topics() -> Response:
    """
    Paginated, filtered, searchable topic list.

    Query params:
      page      int  (default 1)
      per_page  int  (default 20, max 100)
      q         str  — case-insensitive substring search
      type      str  — 'talk' | 'q&a' | 'task' | 'solution'
      digested  bool — '1' | 'true' for digested only
      since     str  — ISO date lower bound (create_time >=)
      until     str  — ISO date upper bound (create_time <=)
      tag       str  — user tag filter
      starred   bool — '1' | 'true' for starred only
    """
    user_data = _load_user_data()

    # --- Parse params ---
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        per_page = 20

    q = request.args.get("q", "").strip()
    type_filter = request.args.get("type", "").strip()
    digested_raw = request.args.get("digested", "").lower()
    digested_filter = digested_raw in ("1", "true") if digested_raw else None
    since_raw = request.args.get("since", "").strip()
    until_raw = request.args.get("until", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    starred_raw = request.args.get("starred", "").lower()
    starred_filter = starred_raw in ("1", "true") if starred_raw else None

    since_dt = _parse_date(since_raw) if since_raw else None
    until_dt = _parse_date(until_raw) if until_raw else None

    # --- Filter ---
    filtered: list[dict[str, Any]] = []
    for topic in _topics:
        if type_filter and topic.get("type") != type_filter:
            continue
        if digested_filter is not None and bool(topic.get("digested")) != digested_filter:
            continue
        tid = topic["topic_id"]
        if starred_filter is not None:
            is_starred = bool(user_data["stars"].get(tid))
            if is_starred != starred_filter:
                continue
        if tag_filter:
            user_tags = user_data["tags"].get(tid, [])
            if tag_filter not in user_tags:
                continue
        if since_dt or until_dt:
            ct = _parse_date(topic.get("create_time", ""))
            if since_dt and ct < since_dt:
                continue
            if until_dt and ct > until_dt:
                continue
        if q and not _matches_query(topic, q):
            continue
        filtered.append(topic)

    total = len(filtered)
    start = (page - 1) * per_page
    page_topics = filtered[start : start + per_page]

    # Enrich
    enriched = [_enrich(t, user_data) for t in page_topics]

    return jsonify(
        {
            "success": True,
            "data": enriched,
            "meta": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if per_page else 1,
            },
        }
    )


@app.route("/api/topics/<topic_id>/star", methods=["POST"])
def api_star_topic(topic_id: str) -> Response:
    """Toggle or set star on a topic. Body JSON: {"starred": true|false} (optional; toggles if absent)."""
    if topic_id not in _topic_index:
        return jsonify({"success": False, "error": "Topic not found"}), 404

    user_data = _load_user_data()
    body = request.get_json(silent=True) or {}

    if "starred" in body:
        new_state = bool(body["starred"])
    else:
        new_state = not bool(user_data["stars"].get(topic_id))

    # Immutable update pattern
    new_stars = {**user_data["stars"], topic_id: new_state}
    new_data = {**user_data, "stars": new_stars}
    _save_user_data(new_data)

    return jsonify({"success": True, "data": {"topic_id": topic_id, "starred": new_state}})


@app.route("/api/topics/<topic_id>/tags", methods=["POST"])
def api_tag_topic(topic_id: str) -> Response:
    """Set tags for a topic. Body JSON: {"tags": ["tag1", "tag2"]}."""
    if topic_id not in _topic_index:
        return jsonify({"success": False, "error": "Topic not found"}), 404

    body = request.get_json(silent=True) or {}
    tags = body.get("tags")
    if not isinstance(tags, list):
        return jsonify({"success": False, "error": "'tags' must be a list"}), 400

    # Validate: each tag must be a non-empty string
    tags_clean: list[str] = []
    for t in tags:
        if not isinstance(t, str) or not t.strip():
            return jsonify({"success": False, "error": "Each tag must be a non-empty string"}), 400
        tags_clean.append(t.strip())

    user_data = _load_user_data()
    new_tags = {**user_data["tags"], topic_id: tags_clean}
    new_data = {**user_data, "tags": new_tags}
    _save_user_data(new_data)

    return jsonify({"success": True, "data": {"topic_id": topic_id, "tags": tags_clean}})


@app.route("/api/tags")
def api_tags() -> Response:
    """Return all unique user tags across all topics with their counts."""
    user_data = _load_user_data()
    tag_counts: dict[str, int] = {}
    for tags in user_data["tags"].values():
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    return jsonify(
        {"success": True, "data": [{"tag": t, "count": c} for t, c in sorted_tags]}
    )


@app.route("/api/stats")
def api_stats() -> Response:
    """Return aggregate statistics about the loaded topics."""
    user_data = _load_user_data()
    total = len(_topics)
    type_counts: dict[str, int] = {}
    digested_count = 0
    starred_count = sum(1 for v in user_data["stars"].values() if v)

    for t in _topics:
        ttype = t.get("type", "unknown")
        type_counts[ttype] = type_counts.get(ttype, 0) + 1
        if t.get("digested"):
            digested_count += 1

    return jsonify(
        {
            "success": True,
            "data": {
                "group_id": GROUP_ID,
                "total_topics": total,
                "by_type": type_counts,
                "digested_count": digested_count,
                "starred_count": starred_count,
                "total_tags": len(user_data["tags"]),
            },
        }
    )


@app.route("/images/<path:filename>")
def serve_image(filename: str) -> Response:
    """Serve images from the images output directory."""
    return send_from_directory(IMAGES_DIR, filename)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

with app.app_context():
    load_topics()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
