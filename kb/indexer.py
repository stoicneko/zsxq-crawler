"""Generate Obsidian index files from topics."""

from __future__ import annotations

from collections import defaultdict

from kb.models import Topic


def generate_by_type_index(topics: list[Topic]) -> str:
    groups: dict[str, list[Topic]] = defaultdict(list)
    for topic in topics:
        groups[topic.type].append(topic)

    lines = ["# Topics by Type", ""]
    for type_name in sorted(groups):
        lines.extend([f"## {type_name}", ""])
        for topic in _sort_topics(groups[type_name]):
            lines.append(f"- [[{topic.date}-{topic.topic_id}|{topic.display_text}]]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_by_author_index(topics: list[Topic]) -> str:
    groups: dict[str, list[Topic]] = defaultdict(list)
    for topic in topics:
        groups[topic.author.name or "匿名"].append(topic)

    lines = ["# Topics by Author", ""]
    for author in sorted(groups):
        lines.extend([f"## {author}", ""])
        for topic in _sort_topics(groups[author]):
            lines.append(f"- [[{topic.date}-{topic.topic_id}|{topic.display_text}]]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_by_month_index(topics: list[Topic]) -> str:
    groups: dict[str, list[Topic]] = defaultdict(list)
    for topic in topics:
        groups[topic.date[:7]].append(topic)

    lines = ["# Topics by Month", ""]
    for month in sorted(groups, reverse=True):
        lines.extend([f"## {month}", ""])
        for topic in _sort_topics(groups[month]):
            lines.append(f"- [[{topic.date}-{topic.topic_id}|{topic.display_text}]]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _sort_topics(topics: list[Topic]) -> list[Topic]:
    return sorted(topics, key=lambda topic: (topic.date, topic.time, topic.topic_id), reverse=True)
