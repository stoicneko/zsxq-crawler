# zsxq Monitor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daemon service that polls zsxq API for new topics, crawls them, and notifies the web viewer to hot-reload.

**Architecture:** Independent `Monitor` class reuses existing `Config`, `ZsxqClient`, `Crawler`, and `Storage`. Crawler gets a new public `process_and_save()` method. Web app gets a `POST /api/reload` endpoint. CLI entry in `monitor.py`. systemd units in `deploy/`.

**Tech Stack:** Python 3, httpx, Flask, pytest

**Spec:** `docs/superpowers/specs/2026-03-30-zsxq-monitor-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `zsxq_crawler/crawler.py:189-258` | Make `_process_topic()` public, add `process_and_save()` |
| Create | `zsxq_crawler/monitor.py` | `Monitor` class: poll loop, crawl new, notify web |
| Create | `monitor.py` | CLI entry point with argparse |
| Modify | `web/app.py` (before `# Startup` section) | Add `POST /api/reload` endpoint |
| Create | `tests/test_monitor.py` | Unit + integration tests for Monitor |
| Modify | `tests/test_web.py` | Add tests for `/api/reload` endpoint |
| Create | `deploy/zsxq-monitor.service` | systemd user service for monitor |
| Create | `deploy/zsxq-web.service` | systemd user service for web app |
| Create | `deploy/zsxq.target` | systemd target grouping both services |
| Modify | `.env.example` | Add `ZSXQ_MONITOR_INTERVAL`, `ZSXQ_RELOAD_TOKEN` |

---

## Task 1: Refactor Crawler — Expose Public API

**Files:**
- Modify: `zsxq_crawler/crawler.py:189-258`
- Test: `tests/test_crawler_public_api.py` (create)

This task makes `_process_topic()` callable from outside and adds `process_and_save()` that pairs processing with persistence.

- [ ] **Step 1: Write failing tests for the new public methods**

Create `tests/test_crawler_public_api.py`:

```python
"""Tests for Crawler public API: process_topic() and process_and_save()."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zsxq_crawler.config import Config
from zsxq_crawler.crawler import Crawler
from zsxq_crawler.storage import Storage


def _make_config(**overrides) -> Config:
    defaults = {
        "cookie": "fake_cookie",
        "group_id": "12345",
        "request_delay": 0,
        "batch_size": 100,
        "batch_pause": 0,
        "download_images": False,
        "download_files": False,
        "crawl_comments": False,
        "output_dir": "output",
        "max_pages": 0,
        "since": "",
    }
    defaults.update(overrides)
    return Config(**defaults)


RAW_TALK_TOPIC = {
    "topic_id": 111222333,
    "type": "talk",
    "create_time": "2026-03-30T10:00:00.000+0800",
    "owner": {"user_id": 99, "name": "TestUser"},
    "talk": {"text": "Hello world"},
    "likes_count": 5,
    "rewards_count": 0,
    "comments_count": 0,
    "reading_count": 10,
    "digested": False,
}


class TestProcessTopic:
    def test_process_topic_returns_dict(self):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        crawler = Crawler(config, client, storage)

        result = crawler.process_topic(RAW_TALK_TOPIC)

        assert result["topic_id"] == "111222333"
        assert result["type"] == "talk"
        assert result["text"] == "Hello world"
        assert result["author"]["name"] == "TestUser"

    def test_process_topic_does_not_save(self):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        crawler = Crawler(config, client, storage)

        crawler.process_topic(RAW_TALK_TOPIC)

        storage.save_topic.assert_not_called()


class TestProcessAndSave:
    def test_process_and_save_calls_save_topic(self):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        crawler = Crawler(config, client, storage)

        result = crawler.process_and_save(RAW_TALK_TOPIC)

        assert result["topic_id"] == "111222333"
        storage.save_topic.assert_called_once_with(result)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_crawler_public_api.py -v`
Expected: `AttributeError: 'Crawler' object has no attribute 'process_topic'`

- [ ] **Step 3: Implement — rename and add public method**

In `zsxq_crawler/crawler.py`, make two changes:

1. Rename `_process_topic` → `process_topic` (the method at line 189)
2. Update the call site in `_crawl_topics` (line 163) from `self._process_topic(raw_topic)` to `self.process_topic(raw_topic)`
3. Add `process_and_save` method after `process_topic`:

```python
def process_and_save(self, raw: dict[str, Any]) -> dict[str, Any]:
    """Process a raw topic and persist it. Returns the processed topic dict."""
    processed = self.process_topic(raw)
    self._storage.save_topic(processed)
    return processed
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/test_crawler_public_api.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `python -m pytest tests/ -v`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add zsxq_crawler/crawler.py tests/test_crawler_public_api.py
git commit -m "refactor: expose Crawler.process_topic() and process_and_save() as public API"
```

---

## Task 2: Add `POST /api/reload` Endpoint to Web App

**Files:**
- Modify: `web/app.py` (add route before the Startup section, around line 416)
- Modify: `tests/test_web.py` (add test class)

- [ ] **Step 1: Write failing tests for the reload endpoint**

Append to `tests/test_web.py`:

```python
@pytest.fixture()
def reload_client(tmp_path):
    """Function-scoped client for reload tests — isolates side effects."""
    import web.app as web_app

    group_id = "reload_test_group"
    topics_dir = tmp_path / group_id / "topics"
    topics_dir.mkdir(parents=True)

    for topic in ALL_FIXTURE_TOPICS:
        (topics_dir / f"{topic['topic_id']}.json").write_text(
            json.dumps(topic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    web_app.reload_config(tmp_path, group_id)
    web_app.load_topics()

    web_app.app.config["TESTING"] = True
    client = web_app.app.test_client()

    yield client, web_app, topics_dir


class TestReload:
    def test_api_reload_returns_success(self, reload_client):
        """POST /api/reload reloads topics and returns count."""
        client, _, _ = reload_client
        resp = client.post("/api/reload")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["topics_count"] == 5  # fixture has 5 topics

    def test_api_reload_picks_up_new_file(self, reload_client):
        """After adding a new topic JSON file, reload picks it up."""
        client, web_app, topics_dir = reload_client
        # Write a new topic file
        new_topic = {
            "topic_id": "topic_new",
            "type": "talk",
            "create_time": "2026-01-01T00:00:00+00:00",
            "text": "Brand new topic",
            "digested": False,
            "images": [],
            "comments": [],
        }
        new_path = web_app.TOPICS_DIR / "topic_new.json"
        new_path.write_text(
            json.dumps(new_topic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            # Reload
            resp = client.post("/api/reload")
            data = resp.get_json()
            assert data["topics_count"] == 6

            # Verify new topic is accessible
            resp2, data2 = get_json(client, "/api/topics?q=Brand+new")
            assert data2["meta"]["total"] == 1
            assert data2["data"][0]["topic_id"] == "topic_new"
        finally:
            # Cleanup: remove the new file and reload back to original state
            new_path.unlink(missing_ok=True)
            client.post("/api/reload")

    def test_api_reload_with_valid_token(self, reload_client):
        """When ZSXQ_RELOAD_TOKEN is set, valid token is accepted."""
        client, web_app, _ = reload_client
        original_token = os.environ.get("ZSXQ_RELOAD_TOKEN")
        os.environ["ZSXQ_RELOAD_TOKEN"] = "test-secret-token"
        try:
            resp = client.post(
                "/api/reload",
                headers={"Authorization": "Bearer test-secret-token"},
            )
            assert resp.status_code == 200
            assert resp.get_json()["success"] is True
        finally:
            if original_token is None:
                os.environ.pop("ZSXQ_RELOAD_TOKEN", None)
            else:
                os.environ["ZSXQ_RELOAD_TOKEN"] = original_token

    def test_api_reload_rejects_bad_token(self, reload_client):
        """When ZSXQ_RELOAD_TOKEN is set, wrong token returns 403."""
        client, web_app, _ = reload_client
        original_token = os.environ.get("ZSXQ_RELOAD_TOKEN")
        os.environ["ZSXQ_RELOAD_TOKEN"] = "test-secret-token"
        try:
            resp = client.post(
                "/api/reload",
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert resp.status_code == 403
            assert resp.get_json()["success"] is False
        finally:
            if original_token is None:
                os.environ.pop("ZSXQ_RELOAD_TOKEN", None)
            else:
                os.environ["ZSXQ_RELOAD_TOKEN"] = original_token
```

- [ ] **Step 1b: Add `import os` to `tests/test_web.py`**

Add at the top of `tests/test_web.py`, after the existing imports:

```python
import os
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_web.py::TestReload -v`
Expected: 404 errors (endpoint doesn't exist yet)

- [ ] **Step 3: Implement the reload endpoint**

In `web/app.py`, add this route before the `# Startup` section (before line 424):

```python
@app.route("/api/reload", methods=["POST"])
def api_reload() -> Response:
    """Reload all topics from disk into memory.

    If ZSXQ_RELOAD_TOKEN env var is set, the request must include a matching
    Authorization: Bearer <token> header.
    """
    reload_token = os.getenv("ZSXQ_RELOAD_TOKEN", "")
    if reload_token:
        auth_header = request.headers.get("Authorization", "")
        expected = f"Bearer {reload_token}"
        if auth_header != expected:
            return jsonify({"success": False, "error": "Forbidden"}), 403

    load_topics()
    return jsonify({"success": True, "topics_count": len(_topics)})
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/test_web.py::TestReload -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add web/app.py tests/test_web.py
git commit -m "feat: add POST /api/reload endpoint for web viewer hot-reload"
```

---

## Task 3: Implement Monitor Class

**Files:**
- Create: `zsxq_crawler/monitor.py`
- Create: `tests/test_monitor.py`

This is the core monitoring logic. Depends on Task 1 (Crawler public API).

- [ ] **Step 1: Write failing tests for Monitor**

Create `tests/test_monitor.py`:

```python
"""Tests for the Monitor class."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zsxq_crawler.config import Config
from zsxq_crawler.monitor import Monitor


def _make_config(**overrides) -> Config:
    defaults = {
        "cookie": "fake_cookie",
        "group_id": "12345",
        "request_delay": 0,
        "batch_size": 100,
        "batch_pause": 0,
        "download_images": False,
        "download_files": False,
        "crawl_comments": False,
        "output_dir": "output",
        "max_pages": 0,
        "since": "",
    }
    defaults.update(overrides)
    return Config(**defaults)


def _make_api_response(topics: list[dict]) -> dict:
    """Build a mock API response with the given topics."""
    return {"succeeded": True, "resp_data": {"topics": topics}}


RAW_TOPIC_1 = {
    "topic_id": 111,
    "type": "talk",
    "create_time": "2026-03-30T10:00:00.000+0800",
    "owner": {"user_id": 1, "name": "User1"},
    "talk": {"text": "Topic 1"},
    "likes_count": 0,
    "rewards_count": 0,
    "comments_count": 0,
    "reading_count": 0,
    "digested": False,
}

RAW_TOPIC_2 = {
    "topic_id": 222,
    "type": "talk",
    "create_time": "2026-03-30T11:00:00.000+0800",
    "owner": {"user_id": 2, "name": "User2"},
    "talk": {"text": "Topic 2"},
    "likes_count": 0,
    "rewards_count": 0,
    "comments_count": 0,
    "reading_count": 0,
    "digested": False,
}


class TestPoll:
    def test_poll_returns_new_topics(self):
        """_poll() returns only topics not in existing IDs."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.return_value = _make_api_response([RAW_TOPIC_1, RAW_TOPIC_2])

        monitor = Monitor(config, client, storage, interval=300)
        new_topics = monitor._poll()

        assert len(new_topics) == 2
        client.get.assert_called_once()

    def test_poll_filters_existing_ids(self):
        """_poll() skips topics already in storage."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = {"111"}
        client.get.return_value = _make_api_response([RAW_TOPIC_1, RAW_TOPIC_2])

        monitor = Monitor(config, client, storage, interval=300)
        new_topics = monitor._poll()

        assert len(new_topics) == 1
        assert new_topics[0]["topic_id"] == 222

    def test_poll_returns_empty_on_no_topics(self):
        """_poll() returns empty list when API returns no topics."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.return_value = {"succeeded": True, "resp_data": {"topics": []}}

        monitor = Monitor(config, client, storage, interval=300)
        new_topics = monitor._poll()

        assert new_topics == []

    def test_poll_handles_api_error(self):
        """_poll() returns empty list and logs on API exception."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.side_effect = RuntimeError("API error")

        monitor = Monitor(config, client, storage, interval=300)
        new_topics = monitor._poll()

        assert new_topics == []


class TestCrawlNew:
    def test_crawl_new_processes_and_saves(self):
        """_crawl_new() calls process_and_save for each topic and saves all."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()

        monitor = Monitor(config, client, storage, interval=300)

        # Mock the crawler's process_and_save
        processed_1 = {"topic_id": "111", "type": "talk", "text": "Topic 1"}
        processed_2 = {"topic_id": "222", "type": "talk", "text": "Topic 2"}
        monitor._crawler.process_and_save = MagicMock(
            side_effect=[processed_1, processed_2]
        )

        result = monitor._crawl_new([RAW_TOPIC_1, RAW_TOPIC_2])

        assert result == 2
        assert monitor._crawler.process_and_save.call_count == 2
        storage.save_all_topics.assert_called_once_with([processed_1, processed_2])


class TestNotifyWeb:
    @patch("zsxq_crawler.monitor.httpx")
    def test_notify_web_posts_to_url(self, mock_httpx):
        """_notify_web() sends POST to the configured URL."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.post.return_value = mock_response

        monitor = Monitor(
            config, client, storage, interval=300,
            notify_url="http://localhost:5000/api/reload",
        )
        monitor._notify_web()

        mock_httpx.post.assert_called_once_with(
            "http://localhost:5000/api/reload", headers={}, timeout=5.0
        )

    @patch("zsxq_crawler.monitor.httpx")
    def test_notify_web_sends_auth_token(self, mock_httpx):
        """_notify_web() includes Authorization header when reload_token is set."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.post.return_value = mock_response

        monitor = Monitor(
            config, client, storage, interval=300,
            notify_url="http://localhost:5000/api/reload",
            reload_token="my-secret",
        )
        monitor._notify_web()

        mock_httpx.post.assert_called_once_with(
            "http://localhost:5000/api/reload",
            headers={"Authorization": "Bearer my-secret"},
            timeout=5.0,
        )

    @patch("zsxq_crawler.monitor.httpx")
    def test_notify_web_logs_on_failure(self, mock_httpx, caplog):
        """_notify_web() logs warning on connection error, does not raise."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        mock_httpx.post.side_effect = Exception("Connection refused")

        monitor = Monitor(
            config, client, storage, interval=300,
            notify_url="http://localhost:5000/api/reload",
        )
        with caplog.at_level(logging.WARNING):
            monitor._notify_web()  # Should not raise

        assert "Connection refused" in caplog.text

    def test_notify_web_skipped_when_no_url(self):
        """_notify_web() does nothing when notify_url is None."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()

        monitor = Monitor(config, client, storage, interval=300, notify_url=None)
        monitor._notify_web()  # Should not raise


class TestRunLoop:
    @patch("zsxq_crawler.monitor.time")
    def test_run_stops_on_signal(self, mock_time):
        """run() exits cleanly when _running is set to False."""
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.return_value = _make_api_response([])

        monitor = Monitor(config, client, storage, interval=300)

        # Simulate: first poll succeeds, then signal arrives during sleep
        def stop_on_sleep(seconds):
            monitor._running = False

        mock_time.sleep.side_effect = stop_on_sleep

        stats = monitor.run()

        assert isinstance(stats, dict)
        assert "topics" in stats

    @patch("zsxq_crawler.monitor.time")
    def test_run_handles_auth_error(self, mock_time):
        """run() exits with AuthError propagated (cookie expired)."""
        from zsxq_crawler.client import AuthError

        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.side_effect = AuthError("Cookie expired")

        monitor = Monitor(config, client, storage, interval=300)

        with pytest.raises(AuthError):
            monitor.run()
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: `ModuleNotFoundError: No module named 'zsxq_crawler.monitor'`

- [ ] **Step 3: Implement Monitor class**

Create `zsxq_crawler/monitor.py`:

```python
"""Real-time monitoring service: polls for new topics and crawls them."""

from __future__ import annotations

import logging
import signal
import time
from typing import Any

import httpx

from zsxq_crawler.client import AuthError, ZsxqClient
from zsxq_crawler.config import Config
from zsxq_crawler.crawler import Crawler
from zsxq_crawler.storage import Storage

logger = logging.getLogger(__name__)


class Monitor:
    """Polls the zsxq API at intervals, crawls new topics, notifies web app."""

    def __init__(
        self,
        config: Config,
        client: ZsxqClient,
        storage: Storage,
        interval: int = 300,
        notify_url: str | None = "http://localhost:5000/api/reload",
        reload_token: str | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._storage = storage
        self._interval = interval
        self._notify_url = notify_url
        self._reload_token = reload_token
        self._crawler = Crawler(config, client, storage)
        self._running = True
        self._stats: dict[str, int] = {"topics": 0, "images": 0, "files": 0, "polls": 0}

    def run(self) -> dict[str, int]:
        """Main monitoring loop. Returns cumulative stats on exit.

        Raises AuthError if the API cookie has expired (non-recoverable).
        All other exceptions are caught and logged per-poll.
        """
        self._install_signal_handlers()
        logger.info(
            "Monitor started: group=%s, interval=%ds, notify=%s",
            self._config.group_id,
            self._interval,
            self._notify_url or "disabled",
        )

        while self._running:
            try:
                self._stats["polls"] += 1
                new_raw = self._poll()

                if new_raw:
                    count = self._crawl_new(new_raw)
                    logger.info("Poll #%d: crawled %d new topics", self._stats["polls"], count)
                    self._notify_web()
                else:
                    logger.info("Poll #%d: no new topics", self._stats["polls"])

            except AuthError:
                logger.error("Auth error: cookie expired or invalid. Exiting.")
                raise
            except Exception as exc:
                logger.warning("Poll #%d error: %s", self._stats["polls"], exc)

            if self._running:
                time.sleep(self._interval)

        logger.info("Monitor stopped. Stats: %s", self._stats)
        return dict(self._stats)

    def _poll(self) -> list[dict[str, Any]]:
        """Fetch latest topics and return only new ones."""
        existing_ids = self._storage.load_existing_topic_ids()

        try:
            data = self._client.get(
                f"/groups/{self._config.group_id}/topics",
                params={"scope": "all", "count": 20},
            )
        except AuthError:
            raise
        except Exception as exc:
            logger.warning("Failed to poll API: %s", exc)
            return []

        topics = data.get("resp_data", {}).get("topics", [])
        new_topics = [
            t for t in topics
            if str(t.get("topic_id", "")) not in existing_ids
        ]

        return new_topics

    def _crawl_new(self, raw_topics: list[dict[str, Any]]) -> int:
        """Process and save each new topic. Returns count of topics crawled."""
        processed: list[dict[str, Any]] = []
        for raw in raw_topics:
            try:
                result = self._crawler.process_and_save(raw)
                processed.append(result)
                self._stats["topics"] += 1
            except Exception as exc:
                topic_id = raw.get("topic_id", "unknown")
                logger.warning("Failed to process topic %s: %s", topic_id, exc)

        if processed:
            self._storage.save_all_topics(processed)

        return len(processed)

    def _notify_web(self) -> None:
        """POST to the web app reload endpoint."""
        if not self._notify_url:
            return

        try:
            headers = {}
            if self._reload_token:
                headers["Authorization"] = f"Bearer {self._reload_token}"
            resp = httpx.post(self._notify_url, headers=headers, timeout=5.0)
            logger.debug("Web reload response: %d", resp.status_code)
        except Exception as exc:
            logger.warning("Failed to notify web app: %s", exc)

    def _install_signal_handlers(self) -> None:
        """Install SIGTERM/SIGINT handlers for graceful shutdown."""
        def _handle_signal(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("Received %s, shutting down...", sig_name)
            self._running = False

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add zsxq_crawler/monitor.py tests/test_monitor.py
git commit -m "feat: add Monitor class for real-time topic polling"
```

---

## Task 4: Implement CLI Entry Point

**Files:**
- Create: `monitor.py`

Depends on Task 3 (Monitor class).

- [ ] **Step 1: Create `monitor.py`**

```python
"""zsxq monitor — real-time content monitoring service.

Usage:
    python monitor.py                    # poll every 5 minutes
    python monitor.py --interval 60      # poll every 60 seconds
    python monitor.py --no-notify        # don't notify web app
    python monitor.py -v                 # verbose logging
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from zsxq_crawler.client import AuthError, ZsxqClient
from zsxq_crawler.config import Config
from zsxq_crawler.monitor import Monitor
from zsxq_crawler.storage import Storage


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="zsxq monitor — 实时监控更新")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--interval", type=int, default=None, help="Polling interval in seconds (default: 300)")
    parser.add_argument("--no-images", action="store_true", help="Skip image downloads")
    parser.add_argument("--no-files", action="store_true", help="Skip file downloads")
    parser.add_argument("--no-comments", action="store_true", help="Skip comment fetching")
    parser.add_argument("--notify-url", type=str, default=None, help="Web app reload URL (default: http://localhost:5000/api/reload)")
    parser.add_argument("--no-notify", action="store_true", help="Disable web app notification")
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = Config.from_env()

    # Apply CLI overrides (frozen dataclass — must create new instance)
    if args.no_images or args.no_files or args.no_comments:
        config = Config(
            cookie=config.cookie,
            group_id=config.group_id,
            request_delay=config.request_delay,
            batch_size=config.batch_size,
            batch_pause=config.batch_pause,
            download_images=config.download_images and not args.no_images,
            download_files=config.download_files and not args.no_files,
            crawl_comments=config.crawl_comments and not args.no_comments,
            output_dir=config.output_dir,
            max_pages=config.max_pages,
            since=config.since,
        )

    # Resolve interval: CLI arg > env var > default 300
    interval = args.interval or int(os.getenv("ZSXQ_MONITOR_INTERVAL", "300"))

    # Resolve notify URL and reload token
    if args.no_notify:
        notify_url = None
    else:
        notify_url = args.notify_url or "http://localhost:5000/api/reload"

    reload_token = os.getenv("ZSXQ_RELOAD_TOKEN") or None

    storage = Storage(config.output_dir, config.group_id)

    with ZsxqClient(config) as client:
        monitor = Monitor(
            config, client, storage,
            interval=interval, notify_url=notify_url, reload_token=reload_token,
        )
        try:
            stats = monitor.run()
            print(f"\nMonitor stopped. {stats['polls']} polls, {stats['topics']} new topics crawled.")
        except AuthError as e:
            print(f"\nAuth error: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nMonitor stopped by user.")
            sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it parses args correctly**

Run: `python monitor.py --help`
Expected: help text with all options listed

- [ ] **Step 3: Commit**

```bash
git add monitor.py
git commit -m "feat: add monitor.py CLI entry point"
```

---

## Task 5: systemd Configuration

**Files:**
- Create: `deploy/zsxq-monitor.service`
- Create: `deploy/zsxq-web.service`
- Create: `deploy/zsxq.target`

No code dependencies — can run in parallel with other tasks.

- [ ] **Step 1: Create `deploy/zsxq-monitor.service`**

```ini
[Unit]
Description=zsxq Monitor — real-time content monitoring
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/Documents/zsxq
ExecStart=%h/Documents/zsxq/venv/bin/python monitor.py
EnvironmentFile=%h/Documents/zsxq/.env
Restart=on-failure
RestartSec=30

[Install]
WantedBy=zsxq.target
```

- [ ] **Step 2: Create `deploy/zsxq-web.service`**

```ini
[Unit]
Description=zsxq Web Viewer
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/Documents/zsxq
ExecStart=%h/Documents/zsxq/venv/bin/python web/app.py
EnvironmentFile=%h/Documents/zsxq/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=zsxq.target
```

- [ ] **Step 3: Create `deploy/zsxq.target`**

```ini
[Unit]
Description=zsxq Services (Monitor + Web Viewer)
Wants=zsxq-monitor.service zsxq-web.service

[Install]
WantedBy=default.target
```

- [ ] **Step 4: Commit**

```bash
git add deploy/
git commit -m "feat: add systemd user service files for monitor and web"
```

---

## Task 6: Update .env.example and CLAUDE.md

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add new env vars to `.env.example`**

Append to `.env.example`:

```bash
# Monitor settings
# ZSXQ_MONITOR_INTERVAL=300       # Polling interval in seconds (default: 300)
# ZSXQ_RELOAD_TOKEN=              # Optional auth token for /api/reload endpoint
```

- [ ] **Step 2: Update CLAUDE.md with monitor commands and architecture**

Add monitor commands to the Commands section:

```markdown
# Monitor (real-time updates)
python monitor.py                          # start monitoring (poll every 5 min)
python monitor.py --interval 60            # custom poll interval
python monitor.py --no-notify              # don't notify web app
python monitor.py --no-images --no-files   # lightweight mode

# systemd (deploy)
systemctl --user start zsxq.target         # start both monitor + web
systemctl --user enable zsxq.target        # enable on boot
journalctl --user -u zsxq-monitor -f       # monitor logs
```

Add `zsxq_crawler/monitor.py` to the Architecture section:

```
zsxq_crawler/
  monitor.py    → Monitor: polling loop, new topic detection, web reload notification
```

- [ ] **Step 3: Commit**

```bash
git add .env.example CLAUDE.md
git commit -m "docs: add monitor commands and config to CLAUDE.md and .env.example"
```

---

## Task 7: Coverage Check and Final Verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `python -m pytest tests/ -v --cov=zsxq_crawler --cov=web --cov-report=term-missing`
Expected: all tests pass, >=80% coverage on new code (`zsxq_crawler/monitor.py`)

- [ ] **Step 2: Run ruff lint**

Run: `ruff check zsxq_crawler/monitor.py monitor.py web/app.py`
Expected: no errors

- [ ] **Step 3: Fix any issues found, re-run tests**

- [ ] **Step 4: Final commit if any fixes**

```bash
git add -A
git commit -m "fix: address lint and coverage issues"
```
