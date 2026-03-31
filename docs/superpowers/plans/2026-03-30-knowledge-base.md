# Knowledge Base Converter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert 16,000+ zsxq topic JSON files into an Obsidian-compatible Markdown vault with indexes.

**Architecture:** A standalone `convert_to_kb.py` script reads topic JSON files from `output/{group_id}/topics/`, converts each to a Markdown file with YAML frontmatter, organizes into `knowledge-base/topics/YYYY/MM/` directories, symlinks media, and generates index files. Dataclass `Topic` as intermediate model; pure functions for parsing and rendering.

**Tech Stack:** Python 3.14, stdlib only (json, pathlib, dataclasses, argparse, logging). PyYAML NOT needed — frontmatter is simple enough to template as a string. pytest for testing.

**Spec:** `docs/superpowers/specs/2026-03-30-knowledge-base-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `convert_to_kb.py` | CLI entry point, orchestration, argparse |
| `kb/models.py` | `Topic` and `Author` frozen dataclasses |
| `kb/parser.py` | JSON dict → `Topic` model (one function per concern) |
| `kb/renderer.py` | `Topic` model → Markdown string with frontmatter |
| `kb/indexer.py` | Generate by-type, by-author, by-month index files |
| `kb/__init__.py` | Package init (empty) |
| `tests/test_kb_models.py` | Model construction and edge cases |
| `tests/test_kb_parser.py` | JSON parsing tests |
| `tests/test_kb_renderer.py` | Markdown rendering tests |
| `tests/test_kb_indexer.py` | Index generation tests |
| `tests/test_kb_integration.py` | End-to-end conversion with real sample files |

---

### Task 1: Topic Data Model

**Files:**
- Create: `kb/__init__.py`
- Create: `kb/models.py`
- Test: `tests/test_kb_models.py`

- [ ] **Step 1: Write failing tests for Topic model**

```python
# tests/test_kb_models.py
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
        long_text = "A" * 100
        topic = Topic(
            topic_id="111",
            type="talk",
            author=Author(user_id="1", name="Test"),
            date="2026-03-05",
            time="17:28:16",
            digested=False,
            text=long_text,
            images=[],
            files=[],
            answer_text=None,
            answer_author=None,
            answer_images=[],
        )
        assert len(topic.display_text) == 53  # 50 + "..."
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_kb_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kb'`

- [ ] **Step 3: Implement models**

```python
# kb/__init__.py
```

```python
# kb/models.py
"""Data models for knowledge base topics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Author:
    """Topic or answer author."""

    user_id: str
    name: str


@dataclass(frozen=True)
class Topic:
    """Parsed topic ready for Markdown rendering."""

    topic_id: str
    type: str
    author: Author
    date: str  # YYYY-MM-DD
    time: str  # HH:MM:SS
    digested: bool
    text: str
    images: list[str]  # list of image filenames
    files: list[str]  # list of file filenames
    answer_text: str | None
    answer_author: Author | None
    answer_images: list[str]  # list of answer image filenames

    @property
    def filename(self) -> str:
        """Generate Markdown filename: {date}-{topic_id}.md"""
        return f"{self.date}-{self.topic_id}.md"

    @property
    def display_text(self) -> str:
        """Truncated text for index display (max 50 chars). Newlines replaced with spaces."""
        text = self.text.replace("\n", " ").strip()
        if not text:
            if self.images:
                return "[图片]"
            return "[无内容]"
        if len(text) <= 50:
            return text
        return text[:50] + "..."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kb_models.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kb/__init__.py kb/models.py tests/test_kb_models.py
git commit -m "feat(kb): add Topic and Author data models"
```

---

### Task 2: JSON Parser

**Files:**
- Create: `kb/parser.py`
- Test: `tests/test_kb_parser.py`

- [ ] **Step 1: Write failing tests for parser**

```python
# tests/test_kb_parser.py
"""Tests for JSON-to-Topic parser."""

from __future__ import annotations

import pytest

from kb.parser import parse_topic, ParseError


# --- Fixtures: raw JSON dicts ---

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
        "images": [
            {"image_id": "999", "filename": "answer_img.jpg"}
        ],
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
        """Social data fields should not appear in the parsed Topic."""
        topic = parse_topic(TALK_JSON)
        # Topic dataclass has no likes/comments/rewards fields
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
        # Empty answer text is treated as no answer
        assert topic.answer_text is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_kb_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_topic' from 'kb.parser'`

- [ ] **Step 3: Implement parser**

```python
# kb/parser.py
"""Parse zsxq topic JSON into Topic model."""

from __future__ import annotations

import logging
from datetime import datetime

from kb.models import Author, Topic

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("topic_id", "type", "create_time")


class ParseError(ValueError):
    """Raised when a topic JSON is missing required fields."""


def parse_topic(data: dict) -> Topic:
    """Parse a raw JSON dict into a Topic model.

    Raises ParseError if required fields are missing.
    """
    for field in REQUIRED_FIELDS:
        if field not in data:
            raise ParseError(f"Missing required field: {field}")

    topic_id = str(data["topic_id"])
    topic_type = data["type"]

    # Parse datetime
    date, time = _parse_datetime(data["create_time"])

    # Parse author
    author_data = data.get("author", {})
    author = Author(
        user_id=str(author_data.get("user_id", "")),
        name=author_data.get("name", ""),
    )

    # Parse images
    images = [img["filename"] for img in data.get("images", []) if "filename" in img]

    # Parse files
    files = [f["filename"] for f in data.get("files", []) if "filename" in f]

    # Parse answer (q&a type)
    answer_text = None
    answer_author = None
    answer_images: list[str] = []

    raw_answer = data.get("answer")
    if raw_answer and raw_answer.get("text"):
        answer_text = raw_answer["text"]
        ans_author_data = raw_answer.get("author", {})
        answer_author = Author(
            user_id=str(ans_author_data.get("user_id", "")),
            name=ans_author_data.get("name", ""),
        )
        answer_images = [
            img["filename"] for img in raw_answer.get("images", []) if "filename" in img
        ]

    return Topic(
        topic_id=topic_id,
        type=topic_type,
        author=author,
        date=date,
        time=time,
        digested=data.get("digested", False),
        text=data.get("text", ""),
        images=images,
        files=files,
        answer_text=answer_text,
        answer_author=answer_author,
        answer_images=answer_images,
    )


def _parse_datetime(iso_str: str) -> tuple[str, str]:
    """Extract date (YYYY-MM-DD) and time (HH:MM:SS) from ISO 8601 string."""
    # Handle format like "2026-03-05T17:28:16.104+0800"
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kb_parser.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kb/parser.py tests/test_kb_parser.py
git commit -m "feat(kb): add JSON-to-Topic parser"
```

---

### Task 3: Markdown Renderer

**Files:**
- Create: `kb/renderer.py`
- Test: `tests/test_kb_renderer.py`

- [ ] **Step 1: Write failing tests for renderer**

```python
# tests/test_kb_renderer.py
"""Tests for Topic-to-Markdown renderer."""

from __future__ import annotations

from kb.models import Author, Topic
from kb.renderer import render_markdown


def _make_topic(**overrides) -> Topic:
    defaults = dict(
        topic_id="111",
        type="talk",
        author=Author(user_id="1", name="TestUser"),
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
    defaults.update(overrides)
    return Topic(**defaults)


class TestRenderTalk:
    def test_basic_talk(self):
        md = render_markdown(_make_topic())
        assert "topic_id: \"111\"" in md
        assert "type: talk" in md
        assert "author: \"TestUser\"" in md
        assert "date: 2026-03-05" in md
        assert 'time: "17:28:16"' in md
        assert "digested: false" in md
        assert "tags: []" in md
        assert "Hello world" in md

    def test_talk_with_images(self):
        md = render_markdown(_make_topic(images=["img1.jpg", "img2.jpg"]))
        assert "![](../../../images/img1.jpg)" in md
        assert "![](../../../images/img2.jpg)" in md

    def test_talk_with_files(self):
        md = render_markdown(_make_topic(files=["doc.pdf"]))
        assert "[doc.pdf](../../../files/doc.pdf)" in md

    def test_talk_empty_text_with_images(self):
        md = render_markdown(_make_topic(text="", images=["img.jpg"]))
        # Should have image but no empty paragraph
        assert "![](../../../images/img.jpg)" in md
        # Frontmatter should end, then directly images (no blank text block)
        lines = md.split("\n")
        after_frontmatter = md.split("---\n", 2)[2]
        assert after_frontmatter.strip().startswith("![](")


class TestRenderQA:
    def test_qa_with_answer(self):
        md = render_markdown(_make_topic(
            type="q&a",
            text="Why?",
            answer_text="Because.",
            answer_author=Author(user_id="2", name="Expert"),
        ))
        assert "## 提问" in md
        assert "Why?" in md
        assert "## 回答" in md
        assert "> **Expert**" in md
        assert "Because." in md

    def test_qa_without_answer(self):
        md = render_markdown(_make_topic(
            type="q&a",
            text="Unanswered?",
        ))
        assert "## 提问" in md
        assert "Unanswered?" in md
        assert "## 回答" not in md

    def test_qa_with_answer_images(self):
        md = render_markdown(_make_topic(
            type="q&a",
            text="Q?",
            answer_text="A.",
            answer_author=Author(user_id="2", name="E"),
            answer_images=["ans_img.jpg"],
        ))
        assert "![](../../../images/ans_img.jpg)" in md
        # Answer image should be after the answer text
        ans_pos = md.index("## 回答")
        img_pos = md.index("![](../../../images/ans_img.jpg)")
        assert img_pos > ans_pos

    def test_qa_with_question_images(self):
        md = render_markdown(_make_topic(
            type="q&a",
            text="Look at this",
            images=["q_img.jpg"],
            answer_text="Nice",
            answer_author=Author(user_id="2", name="E"),
        ))
        # Question image should be between 提问 and 回答
        q_pos = md.index("## 提问")
        img_pos = md.index("![](../../../images/q_img.jpg)")
        a_pos = md.index("## 回答")
        assert q_pos < img_pos < a_pos


class TestRenderUnknownType:
    def test_unknown_type_renders_as_plain(self):
        md = render_markdown(_make_topic(type="new_type", text="Content here"))
        assert "type: new_type" in md
        assert "Content here" in md
        # No section headers for unknown types
        assert "## 提问" not in md
        assert "## 回答" not in md


class TestRenderFrontmatter:
    def test_digested_true(self):
        md = render_markdown(_make_topic(digested=True))
        assert "digested: true" in md

    def test_author_with_quotes(self):
        md = render_markdown(_make_topic(author=Author(user_id="1", name='He said "hi"')))
        # Author name with quotes should be properly escaped
        assert "author:" in md

    def test_multiline_text_preserved(self):
        md = render_markdown(_make_topic(text="Line 1\nLine 2\nLine 3"))
        assert "Line 1\nLine 2\nLine 3" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_kb_renderer.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_markdown' from 'kb.renderer'`

- [ ] **Step 3: Implement renderer**

```python
# kb/renderer.py
"""Render Topic model to Obsidian-compatible Markdown."""

from __future__ import annotations

from kb.models import Topic

_IMAGE_REF = "../../../images"
_FILE_REF = "../../../files"


def render_markdown(topic: Topic) -> str:
    """Render a Topic to a Markdown string with YAML frontmatter."""
    parts = [_render_frontmatter(topic), ""]  # frontmatter + blank line

    if topic.type == "q&a":
        parts.extend(_render_qa_body(topic))
    elif topic.type == "task":
        parts.extend(_render_task_body(topic))
    elif topic.type == "solution":
        parts.extend(_render_solution_body(topic))
    else:
        # talk and unknown types
        parts.extend(_render_plain_body(topic))

    return "\n".join(parts) + "\n"


def _render_frontmatter(topic: Topic) -> str:
    """Render YAML frontmatter block."""
    author_escaped = topic.author.name.replace('"', '\\"')
    return "\n".join([
        "---",
        f'topic_id: "{topic.topic_id}"',
        f"type: {topic.type}",
        f'author: "{author_escaped}"',
        f"date: {topic.date}",
        f'time: "{topic.time}"',
        f"digested: {'true' if topic.digested else 'false'}",
        "tags: []",
        "---",
    ])


def _render_plain_body(topic: Topic) -> list[str]:
    """Render body for talk/task/solution/unknown types."""
    lines: list[str] = []
    if topic.text:
        lines.append(topic.text)
        lines.append("")
    for img in topic.images:
        lines.append(f"![]({_IMAGE_REF}/{img})")
        lines.append("")
    for f in topic.files:
        lines.append(f"[{f}]({_FILE_REF}/{f})")
        lines.append("")
    return lines


def _render_task_body(topic: Topic) -> list[str]:
    """Render body for task type with 任务 section."""
    lines: list[str] = ["## 任务", ""]
    if topic.text:
        lines.append(topic.text)
        lines.append("")
    for img in topic.images:
        lines.append(f"![]({_IMAGE_REF}/{img})")
        lines.append("")
    for f in topic.files:
        lines.append(f"[{f}]({_FILE_REF}/{f})")
        lines.append("")
    return lines


def _render_solution_body(topic: Topic) -> list[str]:
    """Render body for solution type with 问题/解答 sections."""
    lines: list[str] = ["## 问题", ""]
    if topic.text:
        lines.append(topic.text)
        lines.append("")
    for img in topic.images:
        lines.append(f"![]({_IMAGE_REF}/{img})")
        lines.append("")
    if topic.answer_text is not None:
        lines.append("## 解答")
        lines.append("")
        lines.append(topic.answer_text)
        lines.append("")
        for img in topic.answer_images:
            lines.append(f"![]({_IMAGE_REF}/{img})")
            lines.append("")
    return lines


def _render_qa_body(topic: Topic) -> list[str]:
    """Render body for q&a type with 提问/回答 sections."""
    lines: list[str] = []

    # Question section
    lines.append("## 提问")
    lines.append("")
    if topic.text:
        lines.append(topic.text)
        lines.append("")
    for img in topic.images:
        lines.append(f"![]({_IMAGE_REF}/{img})")
        lines.append("")

    # Answer section (only if answer exists)
    if topic.answer_text is not None:
        lines.append("## 回答")
        lines.append("")
        author_name = topic.answer_author.name if topic.answer_author else "匿名"
        lines.append(f"> **{author_name}**：{topic.answer_text}")
        lines.append("")
        for img in topic.answer_images:
            lines.append(f"![]({_IMAGE_REF}/{img})")
            lines.append("")

    return lines
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kb_renderer.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kb/renderer.py tests/test_kb_renderer.py
git commit -m "feat(kb): add Markdown renderer for topics"
```

---

### Task 4: Index Generator

**Files:**
- Create: `kb/indexer.py`
- Test: `tests/test_kb_indexer.py`

- [ ] **Step 1: Write failing tests for indexer**

```python
# tests/test_kb_indexer.py
"""Tests for index file generation."""

from __future__ import annotations

from kb.indexer import generate_by_type_index, generate_by_author_index, generate_by_month_index
from kb.models import Author, Topic


def _make_topic(**overrides) -> Topic:
    defaults = dict(
        topic_id="111",
        type="talk",
        author=Author(user_id="1", name="Alice"),
        date="2026-03-05",
        time="10:00:00",
        digested=False,
        text="Hello",
        images=[],
        files=[],
        answer_text=None,
        answer_author=None,
        answer_images=[],
    )
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
        # 2026-12 should appear before 2024-01
        pos_2026 = md.index("## 2026-12")
        pos_2024 = md.index("## 2024-01")
        assert pos_2026 < pos_2024
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_kb_indexer.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement indexer**

```python
# kb/indexer.py
"""Generate Obsidian index files from topics."""

from __future__ import annotations

from collections import defaultdict

from kb.models import Topic


def generate_by_type_index(topics: list[Topic]) -> str:
    """Generate index grouped by topic type."""
    groups: dict[str, list[Topic]] = defaultdict(list)
    for t in topics:
        groups[t.type].append(t)

    lines = ["# Topics by Type", ""]
    for type_name in sorted(groups.keys()):
        lines.append(f"## {type_name}")
        lines.append("")
        for t in sorted(groups[type_name], key=lambda x: x.date, reverse=True):
            lines.append(f"- [[{t.date}-{t.topic_id}|{t.display_text}]]")
        lines.append("")
    return "\n".join(lines) + "\n"


def generate_by_author_index(topics: list[Topic]) -> str:
    """Generate index grouped by author name."""
    groups: dict[str, list[Topic]] = defaultdict(list)
    for t in topics:
        name = t.author.name if t.author.name else "匿名"
        groups[name].append(t)

    lines = ["# Topics by Author", ""]
    for author in sorted(groups.keys()):
        lines.append(f"## {author}")
        lines.append("")
        for t in sorted(groups[author], key=lambda x: x.date, reverse=True):
            lines.append(f"- [[{t.date}-{t.topic_id}|{t.display_text}]]")
        lines.append("")
    return "\n".join(lines) + "\n"


def generate_by_month_index(topics: list[Topic]) -> str:
    """Generate index grouped by year-month, sorted descending."""
    groups: dict[str, list[Topic]] = defaultdict(list)
    for t in topics:
        month_key = t.date[:7]  # "YYYY-MM"
        groups[month_key].append(t)

    lines = ["# Topics by Month", ""]
    for month in sorted(groups.keys(), reverse=True):
        lines.append(f"## {month}")
        lines.append("")
        for t in sorted(groups[month], key=lambda x: x.date, reverse=True):
            lines.append(f"- [[{t.date}-{t.topic_id}|{t.display_text}]]")
        lines.append("")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kb_indexer.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add kb/indexer.py tests/test_kb_indexer.py
git commit -m "feat(kb): add index generators (by-type, by-author, by-month)"
```

---

### Task 5: CLI Entry Point & Orchestration

**Files:**
- Create: `convert_to_kb.py`
- Test: `tests/test_kb_integration.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/test_kb_integration.py
"""Integration tests for convert_to_kb.py end-to-end conversion."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from convert_to_kb import convert, discover_group_id


@pytest.fixture
def sample_source(tmp_path: Path) -> Path:
    """Create a minimal source directory with sample topics."""
    group_dir = tmp_path / "source" / "12345"
    topics_dir = group_dir / "topics"
    images_dir = group_dir / "images"
    files_dir = group_dir / "files"
    topics_dir.mkdir(parents=True)
    images_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)

    # Talk topic
    talk = {
        "topic_id": "100",
        "type": "talk",
        "create_time": "2026-03-05T10:00:00.000+0800",
        "author": {"user_id": "1", "name": "Alice"},
        "text": "Hello world",
        "digested": False,
        "images": [{"image_id": "img1", "filename": "100_img1.jpg"}],
        "files": [],
    }
    (topics_dir / "100.json").write_text(json.dumps(talk), encoding="utf-8")

    # Q&A topic
    qa = {
        "topic_id": "200",
        "type": "q&a",
        "create_time": "2026-02-15T08:30:00.000+0800",
        "author": {"user_id": "2", "name": "Bob"},
        "text": "Why?",
        "digested": True,
        "images": [],
        "files": [],
        "answer": {
            "text": "Because.",
            "author": {"user_id": "3", "name": "Carol"},
            "images": [],
        },
    }
    (topics_dir / "200.json").write_text(json.dumps(qa), encoding="utf-8")

    # Create a dummy image
    (images_dir / "100_img1.jpg").write_bytes(b"\xff\xd8fake")

    return tmp_path / "source"


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "kb"


class TestConvert:
    def test_full_conversion(self, sample_source: Path, output_dir: Path):
        stats = convert(
            source_dir=sample_source,
            output_dir=output_dir,
            group_id="12345",
            incremental=False,
        )
        assert stats["total"] == 2
        assert stats["converted"] == 2
        assert stats["errors"] == 0

        # Check files exist
        assert (output_dir / "topics" / "2026" / "03" / "2026-03-05-100.md").exists()
        assert (output_dir / "topics" / "2026" / "02" / "2026-02-15-200.md").exists()

        # Check content
        talk_md = (output_dir / "topics" / "2026" / "03" / "2026-03-05-100.md").read_text()
        assert "Hello world" in talk_md
        assert 'topic_id: "100"' in talk_md

        qa_md = (output_dir / "topics" / "2026" / "02" / "2026-02-15-200.md").read_text()
        assert "## 提问" in qa_md
        assert "## 回答" in qa_md

    def test_index_files_generated(self, sample_source: Path, output_dir: Path):
        convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        assert (output_dir / "indexes" / "by-type.md").exists()
        assert (output_dir / "indexes" / "by-author.md").exists()
        assert (output_dir / "indexes" / "by-month.md").exists()

        by_type = (output_dir / "indexes" / "by-type.md").read_text()
        assert "## talk" in by_type
        assert "## q&a" in by_type

    def test_images_symlinked(self, sample_source: Path, output_dir: Path):
        convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        images_link = output_dir / "images"
        assert images_link.is_symlink() or images_link.is_dir()

    def test_readme_generated(self, sample_source: Path, output_dir: Path):
        convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        readme = output_dir / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "2" in content  # total topics count

    def test_incremental_skips_existing(self, sample_source: Path, output_dir: Path):
        # First run
        convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        # Second run incremental
        stats = convert(
            source_dir=sample_source,
            output_dir=output_dir,
            group_id="12345",
            incremental=True,
        )
        assert stats["converted"] == 0
        assert stats["skipped"] == 2

    def test_malformed_json_skipped(self, sample_source: Path, output_dir: Path):
        # Add a bad JSON file
        bad_file = sample_source / "12345" / "topics" / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")

        stats = convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        assert stats["errors"] == 1
        assert stats["converted"] == 2  # other 2 still converted


class TestDiscoverGroupId:
    def test_auto_detect(self, sample_source: Path):
        group_id = discover_group_id(sample_source)
        assert group_id == "12345"

    def test_no_groups_raises(self, tmp_path: Path):
        empty_source = tmp_path / "empty"
        empty_source.mkdir()
        with pytest.raises(SystemExit):
            discover_group_id(empty_source)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_kb_integration.py -v`
Expected: FAIL — `ImportError: cannot import name 'convert' from 'convert_to_kb'`

- [ ] **Step 3: Implement CLI entry point**

```python
# convert_to_kb.py
"""Convert zsxq topic JSON files to Obsidian-compatible Markdown vault.

Usage:
    python convert_to_kb.py                         # full conversion
    python convert_to_kb.py --incremental           # only new topics
    python convert_to_kb.py --group-id 12345        # specific group
    python convert_to_kb.py --output-dir ./my-kb    # custom output
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from kb.indexer import generate_by_author_index, generate_by_month_index, generate_by_type_index
from kb.models import Topic
from kb.parser import ParseError, parse_topic
from kb.renderer import render_markdown

logger = logging.getLogger(__name__)


def discover_group_id(source_dir: Path) -> str:
    """Auto-detect group ID from source directory."""
    candidates = [
        d.name
        for d in source_dir.iterdir()
        if d.is_dir() and d.name != "YOUR_GROUP_ID_HERE" and (d / "topics").is_dir()
    ]
    if not candidates:
        print("No group directories found in source directory.", file=sys.stderr)
        sys.exit(1)
    if len(candidates) > 1:
        print(f"Multiple groups found: {candidates}. Use --group-id to specify.", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def _find_existing_topic_ids(output_dir: Path) -> set[str]:
    """Scan existing .md files to find already-converted topic IDs."""
    ids: set[str] = set()
    topics_dir = output_dir / "topics"
    if not topics_dir.exists():
        return ids
    for md_file in topics_dir.rglob("*.md"):
        # Filename: YYYY-MM-DD-{topic_id}.md
        stem = md_file.stem  # e.g. "2026-03-05-14588121528885522"
        parts = stem.split("-", 3)  # ["2026", "03", "05", "14588121528885522"]
        if len(parts) == 4:
            ids.add(parts[3])
    return ids


def _create_media_symlinks(source_dir: Path, group_id: str, output_dir: Path) -> None:
    """Create symlinks for images/ and files/ directories."""
    for media_type in ("images", "files"):
        source = source_dir / group_id / media_type
        target = output_dir / media_type
        if not source.exists() or not any(source.iterdir()):
            continue
        if target.is_symlink():
            target.unlink()
        if not target.exists():
            target.symlink_to(source.resolve())
            logger.info("Symlinked %s -> %s", target, source.resolve())


def _generate_readme(output_dir: Path, topics: list[Topic], group_id: str) -> None:
    """Generate vault README with stats."""
    type_counts: dict[str, int] = {}
    for t in topics:
        type_counts[t.type] = type_counts.get(t.type, 0) + 1

    lines = [
        "# 知识星球知识库",
        "",
        f"Group ID: `{group_id}`",
        "",
        f"Total topics: **{len(topics)}**",
        "",
        "| Type | Count |",
        "|------|-------|",
    ]
    for type_name, count in sorted(type_counts.items()):
        lines.append(f"| {type_name} | {count} |")
    lines.append("")
    lines.append("Generated by `convert_to_kb.py`. Tags in frontmatter are for manual/AI annotation.")
    lines.append("")

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def convert(
    source_dir: Path,
    output_dir: Path,
    group_id: str,
    incremental: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run the full conversion pipeline. Returns stats dict."""
    topics_source = source_dir / group_id / "topics"
    json_files = sorted(topics_source.glob("*.json"))

    existing_ids = _find_existing_topic_ids(output_dir) if incremental else set()

    stats = {"total": 0, "converted": 0, "skipped": 0, "errors": 0}
    all_topics: list[Topic] = []

    for json_file in json_files:
        stats["total"] += 1
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse %s: %s", json_file.name, e)
            stats["errors"] += 1
            continue

        try:
            topic = parse_topic(data)
        except ParseError as e:
            logger.warning("Skipping %s: %s", json_file.name, e)
            stats["errors"] += 1
            continue

        all_topics.append(topic)

        if incremental and topic.topic_id in existing_ids:
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"Would write: topics/{topic.date[:4]}/{topic.date[5:7]}/{topic.filename}")
            stats["converted"] += 1
            continue

        # Write markdown file
        md_dir = output_dir / "topics" / topic.date[:4] / topic.date[5:7]
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / topic.filename
        md_path.write_text(render_markdown(topic), encoding="utf-8")
        stats["converted"] += 1

    if not dry_run:
        # Symlink media
        _create_media_symlinks(source_dir, group_id, output_dir)

        # Generate indexes
        indexes_dir = output_dir / "indexes"
        indexes_dir.mkdir(parents=True, exist_ok=True)
        (indexes_dir / "by-type.md").write_text(
            generate_by_type_index(all_topics), encoding="utf-8"
        )
        (indexes_dir / "by-author.md").write_text(
            generate_by_author_index(all_topics), encoding="utf-8"
        )
        (indexes_dir / "by-month.md").write_text(
            generate_by_month_index(all_topics), encoding="utf-8"
        )

        # Generate README
        _generate_readme(output_dir, all_topics, group_id)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert zsxq topics to Obsidian Markdown vault")
    parser.add_argument("--group-id", type=str, default="", help="zsxq group ID (auto-detect if omitted)")
    parser.add_argument("--source-dir", type=str, default="./output", help="Path to crawler output")
    parser.add_argument("--output-dir", type=str, default="./knowledge-base", help="Path to vault root")
    parser.add_argument("--incremental", action="store_true", help="Skip already-converted topics")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    group_id = args.group_id or discover_group_id(source_dir)

    print(f"Converting group {group_id}: {source_dir} -> {output_dir}")
    if args.incremental:
        print("Mode: incremental (skipping existing)")
    if args.dry_run:
        print("Mode: dry-run (no files written)")

    stats = convert(
        source_dir=source_dir,
        output_dir=output_dir,
        group_id=group_id,
        incremental=args.incremental,
        dry_run=args.dry_run,
    )

    print(f"\nDone! Total: {stats['total']}, Converted: {stats['converted']}, "
          f"Skipped: {stats['skipped']}, Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_kb_integration.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add convert_to_kb.py tests/test_kb_integration.py
git commit -m "feat(kb): add CLI entry point and end-to-end conversion"
```

---

### Task 6: Coverage Check & Final Verification

**Files:**
- All files from Tasks 1-5

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/test_kb_*.py -v`
Expected: All tests PASS

- [ ] **Step 2: Check coverage**

Run: `python -m pytest tests/test_kb_*.py --cov=kb --cov=convert_to_kb --cov-report=term-missing`
Expected: 80%+ coverage on all modules

- [ ] **Step 3: Run linter**

Run: `ruff check kb/ convert_to_kb.py tests/test_kb_*.py && ruff format --check kb/ convert_to_kb.py tests/test_kb_*.py`
Expected: No errors

- [ ] **Step 4: Dry-run on real data**

Run: `python convert_to_kb.py --dry-run`
Expected: Prints list of ~16,000 files that would be written, no errors

- [ ] **Step 5: Run actual conversion**

Run: `python convert_to_kb.py`
Expected: Prints stats, `knowledge-base/` directory created with topics, indexes, symlinks

- [ ] **Step 6: Verify output**

Run:
```bash
ls knowledge-base/topics/ | head -5
head -20 knowledge-base/topics/2026/03/$(ls knowledge-base/topics/2026/03/ | head -1)
wc -l knowledge-base/indexes/by-type.md
ls -la knowledge-base/images
```
Expected: Directory structure matches spec, markdown content is correct, symlink points to output/

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat(kb): knowledge base converter - complete implementation"
```
