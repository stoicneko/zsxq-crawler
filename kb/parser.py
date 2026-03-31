"""Parse zsxq topic JSON into Topic models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kb.models import Author, Topic

REQUIRED_FIELDS = ("topic_id", "type", "create_time")


class ParseError(ValueError):
    """Raised when a topic JSON is missing required fields."""


def parse_topic(data: dict[str, Any]) -> Topic:
    for field in REQUIRED_FIELDS:
        if field not in data:
            raise ParseError(f"Missing required field: {field}")

    date, time = _parse_datetime(str(data["create_time"]))
    author_data = data.get("author", {})
    raw_answer = data.get("answer")

    answer_text = None
    answer_author = None
    answer_images: list[str] = []
    if raw_answer and raw_answer.get("text"):
        answer_text = raw_answer["text"]
        answer_author_data = raw_answer.get("author", {})
        answer_author = Author(
            user_id=str(answer_author_data.get("user_id", "")),
            name=answer_author_data.get("name", ""),
        )
        answer_images = [
            image["filename"]
            for image in raw_answer.get("images", [])
            if "filename" in image
        ]

    return Topic(
        topic_id=str(data["topic_id"]),
        type=str(data["type"]),
        author=Author(
            user_id=str(author_data.get("user_id", "")),
            name=author_data.get("name", ""),
        ),
        date=date,
        time=time,
        digested=bool(data.get("digested", False)),
        text=data.get("text", ""),
        images=[image["filename"] for image in data.get("images", []) if "filename" in image],
        files=[file["filename"] for file in data.get("files", []) if "filename" in file],
        answer_text=answer_text,
        answer_author=answer_author,
        answer_images=answer_images,
    )


def _parse_datetime(iso_str: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
