"""Tests for knowledge base data models."""

from __future__ import annotations

import pytest

from kb.models import Author, Topic


class TestAuthor:
    def test_create_author(self):
        author = Author(user_id="123", name="Alice")
        assert author.user_id == "123"
        assert author.name == "Alice"

    def test_author_is_frozen(self):
        author = Author(user_id="123", name="Alice")
        with pytest.raises(AttributeError):
            author.name = "Bob"


class TestTopic:
    def test_create_talk_topic(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="Hello world",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert topic.topic_id == "111"
        assert topic.type == "talk"
        assert topic.text == "Hello world"

    def test_create_qa_topic_with_answer(self):
        topic = Topic(
            topic_id="222",
            type="q&a",
            author=Author(user_id="1", name="Asker"),
            date="2026-03-07",
            time="12:00:00",
            digested=True,
            text="How?",
            images=[],
            files=[],
            answer_text="Like this.",
            answer_author=Author(user_id="2", name="Expert"),
            answer_images=[],
        )
        assert topic.answer_text == "Like this."
        assert topic.answer_author.name == "Expert"
        assert topic.digested is True

    def test_create_qa_topic_without_answer(self):
        topic = Topic(
            topic_id="333",
            type="q&a",
            author=Author(user_id="1", name="Asker"),
            date="2026-03-07",
            time="12:00:00",
            digested=False,
            text="Unanswered?",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert topic.answer_text is None

    def test_topic_is_frozen(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="Hello",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        with pytest.raises(AttributeError):
            topic.text = "Changed"

    def test_filename(self):
        topic = Topic(
            topic_id="14588121528885522",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="Hello",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert topic.filename == "2026-03-05-14588121528885522.md"

    def test_display_text_normal(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="This is a short text",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert topic.display_text == "This is a short text"

    def test_display_text_truncated(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="A" * 100,
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert len(topic.display_text) == 53
        assert topic.display_text.endswith("...")

    def test_display_text_empty_with_images(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="",
            images=["img.jpg"],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert topic.display_text == "[图片]"

    def test_display_text_empty_no_images(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert topic.display_text == "[无内容]"

    def test_display_text_newlines_replaced(self):
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text="Line 1\nLine 2\nLine 3",
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert "\n" not in topic.display_text
        assert topic.display_text == "Line 1 Line 2 Line 3"
