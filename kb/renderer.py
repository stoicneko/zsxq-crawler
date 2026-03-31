"""Render Topic models to Obsidian-compatible Markdown."""

from __future__ import annotations

from kb.models import Topic

_IMAGE_REF = "../../../images"
_FILE_REF = "../../../files"


def render_markdown(topic: Topic) -> str:
    parts = [_render_frontmatter(topic), ""]
    if topic.type == "q&a":
        parts.extend(_render_qa_body(topic))
    elif topic.type == "task":
        parts.extend(_render_task_body(topic))
    elif topic.type == "solution":
        parts.extend(_render_solution_body(topic))
    else:
        parts.extend(_render_plain_body(topic))
    return "\n".join(parts).rstrip() + "\n"


def _render_frontmatter(topic: Topic) -> str:
    author = topic.author.name.replace('"', '\\"')
    return "\n".join(
        [
            "---",
            f'topic_id: "{topic.topic_id}"',
            f"type: {topic.type}",
            f'author: "{author}"',
            f"date: {topic.date}",
            f'time: "{topic.time}"',
            f"digested: {'true' if topic.digested else 'false'}",
            "tags: []",
            "---",
        ]
    )


def _render_plain_body(topic: Topic) -> list[str]:
    lines: list[str] = []
    if topic.text:
        lines.extend([topic.text, ""])
    lines.extend(_render_media(topic.images, topic.files))
    return lines


def _render_task_body(topic: Topic) -> list[str]:
    lines = ["## 任务", ""]
    if topic.text:
        lines.extend([topic.text, ""])
    lines.extend(_render_media(topic.images, topic.files))
    return lines


def _render_solution_body(topic: Topic) -> list[str]:
    lines = ["## 问题", ""]
    if topic.text:
        lines.extend([topic.text, ""])
    lines.extend(_render_media(topic.images, topic.files))
    if topic.answer_text is not None:
        lines.extend(["## 解答", "", topic.answer_text, ""])
        for image in topic.answer_images:
            lines.extend([f"![]({_IMAGE_REF}/{image})", ""])
    return lines


def _render_qa_body(topic: Topic) -> list[str]:
    lines = ["## 提问", ""]
    if topic.text:
        lines.extend([topic.text, ""])
    for image in topic.images:
        lines.extend([f"![]({_IMAGE_REF}/{image})", ""])
    for file in topic.files:
        lines.extend([f"[{file}]({_FILE_REF}/{file})", ""])
    if topic.answer_text is not None:
        author = topic.answer_author.name if topic.answer_author else "匿名"
        lines.extend(["## 回答", "", f"> **{author}**：{topic.answer_text}", ""])
        for image in topic.answer_images:
            lines.extend([f"![]({_IMAGE_REF}/{image})", ""])
    return lines


def _render_media(images: list[str], files: list[str]) -> list[str]:
    lines: list[str] = []
    for image in images:
        lines.extend([f"![]({_IMAGE_REF}/{image})", ""])
    for file in files:
        lines.extend([f"[{file}]({_FILE_REF}/{file})", ""])
    return lines
