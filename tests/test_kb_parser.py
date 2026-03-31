"""Tests for JSON-to-Topic parser."""

from __future__ import annotations

import pytest

from kb.parser import ParseError, parse_topic

TALK_JSON = {
    "topic_id": "14588121528885522",
    "type": "talk",
    "create_time": "2026-03-05T17:28:16.104+0800",
    "author": {"user_id": "841511128148452", "name": "幻夜梦屿"},
    "text": "消费满1000➕我微信就有这好处",
    "digested": False,
    "images": [
        {"image_id": "1522851252554222", "filename": "14588121528885522_1522851252554222.jpg"}
    ],
    "files": [],
    "likes_count": 17,
    "rewards_count": 0,
    "comments_count": 8,
    "reading_count": 1,
    "comments": [{"text": "should be stripped"}],
}

QA_WITH_ANSWER_JSON = {
    "topic_id": "14588121115225882",
    "type": "q&a",
    "create_time": "2026-03-07T12:13:16.989+0800",
    "author": {"user_id": "", "name": ""},
    "text": "合租遇到精神病了",
    "digested": False,
    "images": [],
    "files": [],
    "likes_count": 14,
    "comments": [],
    "answer": {
        "text": "这都是小事",
        "author": {"user_id": "841511128148452", "name": "幻夜梦屿"},
        "images": [{"image_id": "999", "filename": "answer_img.jpg"}],
    },
}

QA_NO_ANSWER_JSON = {
    "topic_id": "333",
    "type": "q&a",
    "create_time": "2026-01-01T00:00:00.000+0800",
    "author": {"user_id": "1", "name": "Asker"},
    "text": "Question?",
    "digested": False,
    "images": [],
    "files": [],
    "answer": None,
}

EMPTY_TEXT_JSON = {
    "topic_id": "444",
    "type": "talk",
    "create_time": "2026-02-01T10:00:00.000+0800",
    "author": {"user_id": "1", "name": "Poster"},
    "text": "",
    "digested": False,
    "images": [{"image_id": "555", "filename": "img.jpg"}],
    "files": [],
}


class TestParseTopic:
    def test_parse_talk(self):
        topic = parse_topic(TALK_JSON)
        assert topic.topic_id == "14588121528885522"
        assert topic.type == "talk"
        assert topic.author.name == "幻夜梦屿"
        assert topic.date == "2026-03-05"
        assert topic.time == "17:28:16"
        assert topic.digested is False
        assert topic.text == "消费满1000➕我微信就有这好处"
        assert topic.images == ["14588121528885522_1522851252554222.jpg"]
        assert topic.answer_text is None
        assert topic.answer_author is None

    def test_parse_qa_with_answer(self):
        topic = parse_topic(QA_WITH_ANSWER_JSON)
        assert topic.type == "q&a"
        assert topic.answer_text == "这都是小事"
        assert topic.answer_author.name == "幻夜梦屿"
        assert topic.answer_images == ["answer_img.jpg"]

    def test_parse_qa_without_answer(self):
        topic = parse_topic(QA_NO_ANSWER_JSON)
        assert topic.type == "q&a"
        assert topic.answer_text is None
        assert topic.answer_author is None
        assert topic.answer_images == []

    def test_parse_empty_text(self):
        topic = parse_topic(EMPTY_TEXT_JSON)
        assert topic.text == ""
        assert topic.images == ["img.jpg"]

    def test_social_fields_excluded(self):
        topic = parse_topic(TALK_JSON)
        assert not hasattr(topic, "likes_count")
        assert not hasattr(topic, "comments")

    def test_missing_topic_id_raises(self):
        bad = {"type": "talk", "create_time": "2026-01-01T00:00:00.000+0800"}
        with pytest.raises(ParseError, match="topic_id"):
            parse_topic(bad)

    def test_missing_type_raises(self):
        bad = {"topic_id": "1", "create_time": "2026-01-01T00:00:00.000+0800"}
        with pytest.raises(ParseError, match="type"):
            parse_topic(bad)

    def test_missing_create_time_raises(self):
        bad = {"topic_id": "1", "type": "talk"}
        with pytest.raises(ParseError, match="create_time"):
            parse_topic(bad)

    def test_unknown_type_still_parses(self):
        data = {
            "topic_id": "999",
            "type": "new_type",
            "create_time": "2026-06-01T08:00:00.000+0800",
            "author": {"user_id": "1", "name": "Test"},
            "text": "Something",
            "digested": False,
            "images": [],
            "files": [],
        }
        topic = parse_topic(data)
        assert topic.type == "new_type"
        assert topic.text == "Something"

    def test_parse_datetime_extracts_date_and_time(self):
        topic = parse_topic(TALK_JSON)
        assert topic.date == "2026-03-05"
        assert topic.time == "17:28:16"

    def test_qa_with_empty_answer_text(self):
        data = {
            "topic_id": "555",
            "type": "q&a",
            "create_time": "2026-01-01T00:00:00.000+0800",
            "author": {"user_id": "1", "name": "A"},
            "text": "Q?",
            "digested": False,
            "images": [],
            "files": [],
            "answer": {"text": "", "author": {"user_id": "2", "name": "B"}, "images": []},
        }
        topic = parse_topic(data)
        assert topic.answer_text is None
