"""Tests for the Monitor class."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from zsxq_crawler.client import AuthError
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
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.return_value = _make_api_response([])

        monitor = Monitor(config, client, storage, interval=300)
        new_topics = monitor._poll()

        assert new_topics == []

    def test_poll_handles_api_error(self):
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
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()

        monitor = Monitor(config, client, storage, interval=300)
        processed_1 = {"topic_id": "111", "type": "talk", "text": "Topic 1"}
        processed_2 = {"topic_id": "222", "type": "talk", "text": "Topic 2"}
        monitor._crawler.process_and_save = MagicMock(side_effect=[processed_1, processed_2])

        result = monitor._crawl_new([RAW_TOPIC_1, RAW_TOPIC_2])

        assert result == 2
        assert monitor._crawler.process_and_save.call_count == 2
        storage.save_all_topics.assert_called_once_with([processed_1, processed_2])


class TestNotifyWeb:
    @patch("zsxq_crawler.monitor.httpx")
    def test_notify_web_posts_to_url(self, mock_httpx):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.post.return_value = mock_response

        monitor = Monitor(
            config,
            client,
            storage,
            interval=300,
            notify_url="http://localhost:5000/api/reload",
        )
        monitor._notify_web()

        mock_httpx.post.assert_called_once_with(
            "http://localhost:5000/api/reload",
            headers={},
            timeout=5.0,
        )

    @patch("zsxq_crawler.monitor.httpx")
    def test_notify_web_sends_auth_token(self, mock_httpx):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.post.return_value = mock_response

        monitor = Monitor(
            config,
            client,
            storage,
            interval=300,
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
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        mock_httpx.post.side_effect = Exception("Connection refused")

        monitor = Monitor(
            config,
            client,
            storage,
            interval=300,
            notify_url="http://localhost:5000/api/reload",
        )
        with caplog.at_level(logging.WARNING):
            monitor._notify_web()

        assert "Connection refused" in caplog.text

    def test_notify_web_skipped_when_no_url(self):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()

        monitor = Monitor(config, client, storage, interval=300, notify_url=None)
        monitor._notify_web()


class TestRunLoop:
    @patch("zsxq_crawler.monitor.time")
    def test_run_stops_on_signal(self, mock_time):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.return_value = _make_api_response([])

        monitor = Monitor(config, client, storage, interval=300)

        def stop_on_sleep(seconds):
            monitor._running = False

        mock_time.sleep.side_effect = stop_on_sleep

        stats = monitor.run()

        assert isinstance(stats, dict)
        assert "topics" in stats

    @patch("zsxq_crawler.monitor.time")
    def test_run_handles_auth_error(self, mock_time):
        config = _make_config()
        client = MagicMock()
        storage = MagicMock()
        storage.load_existing_topic_ids.return_value = set()
        client.get.side_effect = AuthError("Cookie expired")

        monitor = Monitor(config, client, storage, interval=300)

        with pytest.raises(AuthError):
            monitor.run()
