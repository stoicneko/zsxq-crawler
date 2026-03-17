"""Core crawler: fetches topics, comments, images, and files."""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any

from zsxq_crawler.client import ZsxqClient
from zsxq_crawler.config import Config
from zsxq_crawler.storage import Storage

logger = logging.getLogger(__name__)


def _extract_text(topic: dict[str, Any]) -> str:
    """Extract the main text content from a topic."""
    for section in ("talk", "question", "answer", "task", "solution"):
        if section in topic and "text" in topic[section]:
            return topic[section]["text"]
    return ""


def _extract_images(topic: dict[str, Any]) -> list[dict[str, str]]:
    """Extract image URLs from a topic."""
    images = []
    for section in ("talk", "question", "answer", "task", "solution"):
        if section in topic and "images" in topic[section]:
            for img in topic[section]["images"]:
                url = (
                    img.get("large", {}).get("url")
                    or img.get("original", {}).get("url")
                    or img.get("thumbnail", {}).get("url")
                    or ""
                )
                if url:
                    image_id = str(img.get("image_id", ""))
                    images.append({"image_id": image_id, "url": url})
    return images


def _extract_files(topic: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract file info from a topic."""
    files = []
    for section in ("talk", "question", "answer", "task", "solution"):
        if section in topic and "files" in topic[section]:
            for f in topic[section]["files"]:
                files.append({
                    "file_id": str(f.get("file_id", "")),
                    "name": f.get("name", "unknown"),
                })
    return files


class Crawler:
    """Orchestrates the crawling process."""

    def __init__(self, config: Config, client: ZsxqClient, storage: Storage) -> None:
        self._config = config
        self._client = client
        self._storage = storage
        self._stats = {"topics": 0, "images": 0, "files": 0, "comments": 0}

    def run(self) -> dict[str, int]:
        """Run the full crawl. Returns stats dict."""
        logger.info("Starting crawl for group %s", self._config.group_id)

        # Load existing topic IDs for incremental crawling
        existing_ids = self._storage.load_existing_topic_ids()
        if existing_ids:
            logger.info("Found %d existing topics, will skip duplicates", len(existing_ids))

        all_topics = self._crawl_topics(existing_ids)

        if all_topics:
            self._storage.save_all_topics(all_topics)

        self._storage.save_summary(
            self._stats["topics"],
            self._stats["images"],
            self._stats["files"],
        )

        logger.info(
            "Crawl complete: %d topics, %d images, %d files, %d comments",
            self._stats["topics"],
            self._stats["images"],
            self._stats["files"],
            self._stats["comments"],
        )
        return dict(self._stats)

    def _crawl_topics(self, existing_ids: set[str]) -> list[dict[str, Any]]:
        """Crawl all topics with cursor-based pagination."""
        all_topics: list[dict[str, Any]] = []
        end_time: str | None = None
        page = 0

        while True:
            page += 1
            params: dict[str, Any] = {"scope": "all", "count": 20}
            if end_time:
                params["end_time"] = end_time

            logger.info("Fetching page %d (end_time=%s)...", page, end_time or "latest")

            data = self._client.get(
                f"/groups/{self._config.group_id}/topics",
                params=params,
            )

            topics = data.get("resp_data", {}).get("topics", [])
            if not topics:
                logger.info("No more topics, stopping.")
                break

            new_count = 0
            for raw_topic in topics:
                topic_id = str(raw_topic.get("topic_id", ""))
                if topic_id in existing_ids:
                    continue

                processed = self._process_topic(raw_topic)
                all_topics.append(processed)
                self._storage.save_topic(processed)
                new_count += 1
                self._stats["topics"] += 1

            logger.info("Page %d: %d topics fetched, %d new", page, len(topics), new_count)

            # Check max pages limit
            if self._config.max_pages > 0 and page >= self._config.max_pages:
                logger.info("Reached max pages limit (%d), stopping.", self._config.max_pages)
                break

            # Compute next cursor: last topic's create_time minus 1ms
            last_time = topics[-1].get("create_time", "")
            if not last_time:
                break

            end_time = self._decrement_time(last_time)

        return all_topics

    def _process_topic(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Process a single topic: extract data, download media, fetch comments."""
        topic_id = str(raw.get("topic_id", ""))
        topic_type = raw.get("type", "unknown")
        text = _extract_text(raw)
        images = _extract_images(raw)
        files = _extract_files(raw)

        # Download images
        downloaded_images = []
        if self._config.download_images and images:
            for img in images:
                downloaded = self._download_image(topic_id, img)
                if downloaded:
                    downloaded_images.append(downloaded)

        # Download files
        downloaded_files = []
        if self._config.download_files and files:
            for f in files:
                downloaded = self._download_file(f)
                if downloaded:
                    downloaded_files.append(downloaded)

        # Fetch comments
        comments = []
        if self._config.crawl_comments:
            comments = self._crawl_comments(topic_id)

        owner = raw.get("owner", {})

        return {
            "topic_id": topic_id,
            "type": topic_type,
            "create_time": raw.get("create_time", ""),
            "author": {
                "user_id": str(owner.get("user_id", "")),
                "name": owner.get("name", ""),
            },
            "text": text,
            "likes_count": raw.get("likes_count", 0),
            "rewards_count": raw.get("rewards_count", 0),
            "comments_count": raw.get("comments_count", 0),
            "reading_count": raw.get("reading_count", 0),
            "digested": raw.get("digested", False),
            "images": downloaded_images,
            "files": downloaded_files,
            "comments": comments,
        }

    def _download_image(self, topic_id: str, img: dict[str, str]) -> dict[str, str] | None:
        """Download a single image. Returns metadata or None on failure."""
        image_id = img["image_id"]
        url = img["url"]

        # Derive filename from URL or image_id
        ext = self._guess_extension(url, default=".jpg")
        filename = f"{topic_id}_{image_id}{ext}"

        if self._storage.image_exists(filename):
            return {"image_id": image_id, "filename": filename}

        try:
            dest = self._storage.image_path(filename)
            self._client.download(url, dest)
            self._stats["images"] += 1
            logger.debug("Downloaded image %s", filename)
            return {"image_id": image_id, "filename": filename}
        except Exception as e:
            logger.warning("Failed to download image %s: %s", image_id, e)
            return None

    def _download_file(self, file_info: dict[str, Any]) -> dict[str, str] | None:
        """Download a file attachment. Returns metadata or None on failure."""
        file_id = file_info["file_id"]
        original_name = file_info["name"]

        # Sanitize filename
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", original_name)
        filename = f"{file_id}_{safe_name}"

        if self._storage.file_exists(filename):
            return {"file_id": file_id, "filename": filename, "original_name": original_name}

        try:
            # First get the download URL
            data = self._client.get(f"/files/{file_id}/download_url")
            download_url = data.get("resp_data", {}).get("download_url", "")
            if not download_url:
                logger.warning("No download URL for file %s", file_id)
                return None

            dest = self._storage.file_path(filename)
            self._client.download(download_url, dest)
            self._stats["files"] += 1
            logger.debug("Downloaded file %s", filename)
            return {"file_id": file_id, "filename": filename, "original_name": original_name}
        except Exception as e:
            logger.warning("Failed to download file %s (%s): %s", file_id, original_name, e)
            return None

    def _crawl_comments(self, topic_id: str) -> list[dict[str, Any]]:
        """Fetch all comments for a topic."""
        comments: list[dict[str, Any]] = []

        try:
            data = self._client.get(
                f"/topics/{topic_id}/comments",
                params={"sort": "asc", "count": 30},
            )

            raw_comments = data.get("resp_data", {}).get("comments", [])
            for c in raw_comments:
                owner = c.get("owner", {})
                comments.append({
                    "comment_id": str(c.get("comment_id", "")),
                    "author": {
                        "user_id": str(owner.get("user_id", "")),
                        "name": owner.get("name", ""),
                    },
                    "text": c.get("text", ""),
                    "create_time": c.get("create_time", ""),
                    "likes_count": c.get("likes_count", 0),
                    "repliee": c.get("repliee", {}).get("name", ""),
                })
                self._stats["comments"] += 1
        except Exception as e:
            logger.warning("Failed to fetch comments for topic %s: %s", topic_id, e)

        return comments

    @staticmethod
    def _decrement_time(time_str: str) -> str:
        """Subtract 1 millisecond from a zsxq timestamp to avoid duplicates.

        Input format example: '2026-02-20T10:30:00.123+0800'
        """
        # Find milliseconds and decrement
        match = re.search(r"\.(\d{3})", time_str)
        if match:
            ms = int(match.group(1))
            if ms > 0:
                new_ms = ms - 1
                return time_str[: match.start(1)] + f"{new_ms:03d}" + time_str[match.end(1) :]
        # Fallback: just return as-is (tiny risk of duplicate)
        return time_str

    @staticmethod
    def _guess_extension(url: str, default: str = ".jpg") -> str:
        """Guess file extension from URL."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            if path.endswith(ext):
                return ext
        return default
