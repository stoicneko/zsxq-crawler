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
        """Main monitoring loop. Returns cumulative stats on exit."""
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
        return [t for t in topics if str(t.get("topic_id", "")) not in existing_ids]

    def _crawl_new(self, raw_topics: list[dict[str, Any]]) -> int:
        """Process and save each new topic. Returns count of topics crawled."""
        processed: list[dict[str, Any]] = []
        for raw in raw_topics:
            try:
                before_images = self._crawler._stats["images"]
                before_files = self._crawler._stats["files"]
                result = self._crawler.process_and_save(raw)
                processed.append(result)
                self._stats["topics"] += 1
                self._stats["images"] += self._crawler._stats["images"] - before_images
                self._stats["files"] += self._crawler._stats["files"] - before_files
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
            headers: dict[str, str] = {}
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
