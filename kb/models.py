"""Data models for knowledge base topics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Author:
    user_id: str
    name: str


@dataclass(frozen=True)
class Topic:
    topic_id: str
    type: str
    author: Author
    date: str
    time: str
    digested: bool
    text: str
    images: list[str]
    files: list[str]
    answer_text: str | None
    answer_author: Author | None
    answer_images: list[str]

    @property
    def filename(self) -> str:
        return f"{self.date}-{self.topic_id}.md"

    @property
    def display_text(self) -> str:
        text = " ".join(self.text.split()).strip()
        if not text:
            if self.images:
                return "[图片]"
            return "[无内容]"
        if len(text) <= 50:
            return text
        return f"{text[:50]}..."
