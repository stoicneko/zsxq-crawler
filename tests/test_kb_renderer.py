"""Tests for Topic-to-Markdown renderer."""

from __future__ import annotations

from kb.models import Author, Topic
from kb.renderer import render_markdown


def _make_topic(**overrides) -> Topic:
    defaults = {
        "topic_id": "111",
        "type": "talk",
        "author": Author(user_id="1", name="TestUser"),
        "date": "2026-03-05",
        "time": "17:28:16",
        "digested": False,
        "text": "Hello world",
        "images": [],
        "files": [],
        "answer_text": None,
        "answer_author": None,
        "answer_images": [],
    }
    defaults.update(overrides)
    return Topic(**defaults)


class TestRenderTalk:
    def test_basic_talk(self):
        md = render_markdown(_make_topic())
        assert 'topic_id: "111"' in md
        assert "type: talk" in md
        assert 'author: "TestUser"' in md
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
        assert "![](../../../images/img.jpg)" in md
        after_frontmatter = md.split("---\n", 2)[2]
        assert after_frontmatter.strip().startswith("![](")


class TestRenderQA:
    def test_qa_with_answer(self):
        md = render_markdown(
            _make_topic(
                type="q&a",
                text="Why?",
                answer_text="Because.",
                answer_author=Author(user_id="2", name="Expert"),
            )
        )
        assert "## 提问" in md
        assert "Why?" in md
        assert "## 回答" in md
        assert "> **Expert**" in md
        assert "Because." in md

    def test_qa_without_answer(self):
        md = render_markdown(_make_topic(type="q&a", text="Unanswered?"))
        assert "## 提问" in md
        assert "Unanswered?" in md
        assert "## 回答" not in md

    def test_qa_with_answer_images(self):
        md = render_markdown(
            _make_topic(
                type="q&a",
                text="Q?",
                answer_text="A.",
                answer_author=Author(user_id="2", name="E"),
                answer_images=["ans_img.jpg"],
            )
        )
        assert "![](../../../images/ans_img.jpg)" in md
        assert md.index("![](../../../images/ans_img.jpg)") > md.index("## 回答")

    def test_qa_with_question_images(self):
        md = render_markdown(
            _make_topic(
                type="q&a",
                text="Look at this",
                images=["q_img.jpg"],
                answer_text="Nice",
                answer_author=Author(user_id="2", name="E"),
            )
        )
        assert md.index("## 提问") < md.index("![](../../../images/q_img.jpg)") < md.index("## 回答")


class TestRenderUnknownType:
    def test_unknown_type_renders_as_plain(self):
        md = render_markdown(_make_topic(type="new_type", text="Content here"))
        assert "type: new_type" in md
        assert "Content here" in md
        assert "## 提问" not in md
        assert "## 回答" not in md


class TestRenderFrontmatter:
    def test_digested_true(self):
        md = render_markdown(_make_topic(digested=True))
        assert "digested: true" in md

    def test_author_with_quotes(self):
        md = render_markdown(_make_topic(author=Author(user_id="1", name='He said "hi"')))
        assert 'author: "He said \\"hi\\""' in md

    def test_multiline_text_preserved(self):
        md = render_markdown(_make_topic(text="Line 1\nLine 2\nLine 3"))
        assert "Line 1\nLine 2\nLine 3" in md
