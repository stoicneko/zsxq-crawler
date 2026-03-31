"""Tests for Crawler public API: process_topic() and process_and_save()."""

from __future__ import annotations

from unittest.mock import MagicMock

from zsxq_crawler.config import Config
from zsxq_crawler.crawler import Crawler


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
