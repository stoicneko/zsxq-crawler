"""Data persistence: save topics, images, and files."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Storage:
    """Manages output directories and file persistence."""

    def __init__(self, output_dir: str, group_id: str) -> None:
        self._base = Path(output_dir) / group_id
        self._topics_dir = self._base / "topics"
        self._images_dir = self._base / "images"
        self._files_dir = self._base / "files"
        self._data_file = self._base / "all_topics.json"

        for d in (self._topics_dir, self._images_dir, self._files_dir):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def images_dir(self) -> Path:
        return self._images_dir

    @property
    def files_dir(self) -> Path:
        return self._files_dir

    def load_existing_topic_ids(self) -> set[str]:
        """Load previously saved topic IDs for incremental crawling."""
        if not self._data_file.exists():
            return set()
        try:
            with open(self._data_file, encoding="utf-8") as f:
                topics = json.load(f)
            return {t["topic_id"] for t in topics}
        except (json.JSONDecodeError, KeyError):
            return set()

    def save_topic(self, topic: dict[str, Any]) -> None:
        """Save a single topic as a separate JSON file."""
        topic_id = str(topic.get("topic_id", "unknown"))
        path = self._topics_dir / f"{topic_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(topic, f, ensure_ascii=False, indent=2)

    def save_all_topics(self, topics: list[dict[str, Any]]) -> None:
        """Save all topics as a single JSON file (merged with existing)."""
        existing: list[dict[str, Any]] = []
        if self._data_file.exists():
            try:
                with open(self._data_file, encoding="utf-8") as f:
                    existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

        existing_ids = {t["topic_id"] for t in existing}
        merged = existing + [t for t in topics if t["topic_id"] not in existing_ids]

        # Sort by create_time descending
        merged.sort(key=lambda t: t.get("create_time", ""), reverse=True)

        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        logger.info("Saved %d topics total to %s", len(merged), self._data_file)

    def image_exists(self, filename: str) -> bool:
        return (self._images_dir / filename).exists()

    def file_exists(self, filename: str) -> bool:
        return (self._files_dir / filename).exists()

    def image_path(self, filename: str) -> str:
        return str(self._images_dir / filename)

    def file_path(self, filename: str) -> str:
        return str(self._files_dir / filename)

    def save_summary(self, total_topics: int, total_images: int, total_files: int) -> None:
        """Save a crawl summary."""
        summary = {
            "group_id": self._base.name,
            "total_topics": total_topics,
            "total_images": total_images,
            "total_files": total_files,
        }
        path = self._base / "summary.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
