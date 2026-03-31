"""Tests for index file generation."""

from __future__ import annotations

from kb.indexer import generate_by_author_index, generate_by_month_index, generate_by_type_index
from kb.models import Author, Topic


def _make_topic(**overrides) -> Topic:
    defaults = {
        "topic_id": "111",
        "type": "talk",
        "author": Author(user_id="1", name="Alice"),
        "date": "2026-03-05",
        "time": "10:00:00",
        "digested": False,
        "text": "Hello",
        "images": [],
        "files": [],
        "answer_text": None,
        "answer_author": None,
        "answer_images": [],
    }
    defaults.update(overrides)
    return Topic(**defaults)


class TestByTypeIndex:
    def test_groups_by_type(self):
        topics = [
            _make_topic(topic_id="1", type="talk", text="Talk 1"),
            _make_topic(topic_id="2", type="q&a", text="QA 1"),
            _make_topic(topic_id="3", type="talk", text="Talk 2"),
        ]
        md = generate_by_type_index(topics)
        assert "# Topics by Type" in md
        assert "## talk" in md
        assert "## q&a" in md
        assert "[[2026-03-05-1|Talk 1]]" in md
        assert "[[2026-03-05-2|QA 1]]" in md
        assert "[[2026-03-05-3|Talk 2]]" in md

    def test_empty_topics(self):
        md = generate_by_type_index([])
        assert "# Topics by Type" in md


class TestByAuthorIndex:
    def test_groups_by_author(self):
        topics = [
            _make_topic(topic_id="1", author=Author(user_id="1", name="Alice")),
            _make_topic(topic_id="2", author=Author(user_id="2", name="Bob")),
            _make_topic(topic_id="3", author=Author(user_id="1", name="Alice")),
        ]
        md = generate_by_author_index(topics)
        assert "# Topics by Author" in md
        assert "## Alice" in md
        assert "## Bob" in md

    def test_empty_author_name(self):
        topics = [_make_topic(topic_id="1", author=Author(user_id="1", name=""))]
        md = generate_by_author_index(topics)
        assert "## 匿名" in md


class TestByMonthIndex:
    def test_groups_by_month(self):
        topics = [
            _make_topic(topic_id="1", date="2026-03-05"),
            _make_topic(topic_id="2", date="2026-03-15"),
            _make_topic(topic_id="3", date="2026-02-01"),
        ]
        md = generate_by_month_index(topics)
        assert "# Topics by Month" in md
        assert "## 2026-03" in md
        assert "## 2026-02" in md

    def test_sorted_descending(self):
        topics = [
            _make_topic(topic_id="1", date="2024-01-01"),
            _make_topic(topic_id="2", date="2026-12-01"),
        ]
        md = generate_by_month_index(topics)
        assert md.index("## 2026-12") < md.index("## 2024-01")
