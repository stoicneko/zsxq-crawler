"""Convert zsxq topic JSON files to an Obsidian-compatible knowledge base."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path

from kb.indexer import generate_by_author_index, generate_by_month_index, generate_by_type_index
from kb.models import Topic
from kb.parser import ParseError, parse_topic
from kb.renderer import render_markdown

logger = logging.getLogger(__name__)


def discover_group_id(source_dir: Path) -> str:
    candidates = sorted(
        entry.name
        for entry in source_dir.iterdir()
        if entry.is_dir() and entry.name != "YOUR_GROUP_ID_HERE" and (entry / "topics").is_dir()
    )
    if not candidates:
        print("No group directories found in source directory.", file=sys.stderr)
        raise SystemExit(1)
    if len(candidates) > 1:
        print(f"Multiple groups found: {candidates}. Use --group-id to specify.", file=sys.stderr)
        raise SystemExit(1)
    return candidates[0]


def convert(
    source_dir: Path,
    output_dir: Path,
    group_id: str,
    incremental: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    topics_dir = source_dir / group_id / "topics"
    json_files = sorted(topics_dir.glob("*.json"))
    existing_ids = _find_existing_topic_ids(output_dir) if incremental else set()

    stats = {"total": 0, "converted": 0, "skipped": 0, "errors": 0}
    all_topics: list[Topic] = []

    for json_file in json_files:
        stats["total"] += 1
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse %s: %s", json_file, exc)
            stats["errors"] += 1
            continue

        try:
            topic = parse_topic(data)
        except ParseError as exc:
            logger.warning("Skipping %s: %s", json_file, exc)
            stats["errors"] += 1
            continue

        topic = _filter_missing_media(topic, source_dir / group_id)
        all_topics.append(topic)

        if incremental and topic.topic_id in existing_ids:
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"Would write: topics/{topic.date[:4]}/{topic.date[5:7]}/{topic.filename}")
            stats["converted"] += 1
            continue

        topic_output_dir = output_dir / "topics" / topic.date[:4] / topic.date[5:7]
        topic_output_dir.mkdir(parents=True, exist_ok=True)
        (topic_output_dir / topic.filename).write_text(render_markdown(topic), encoding="utf-8")
        stats["converted"] += 1

    if dry_run:
        return stats

    _create_media_link(source_dir / group_id / "images", output_dir / "images")
    _create_media_link(source_dir / group_id / "files", output_dir / "files")
    _write_indexes(output_dir, all_topics)
    _write_readme(output_dir, group_id, all_topics)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert zsxq topics to Obsidian Markdown vault")
    parser.add_argument("--group-id", default="", help="zsxq group ID (auto-detect if omitted)")
    parser.add_argument("--source-dir", default="./output", help="Path to crawler output")
    parser.add_argument("--output-dir", default="./knowledge-base", help="Path to vault root")
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
    print(
        f"\nDone! Total: {stats['total']}, Converted: {stats['converted']}, "
        f"Skipped: {stats['skipped']}, Errors: {stats['errors']}"
    )


def _find_existing_topic_ids(output_dir: Path) -> set[str]:
    topics_dir = output_dir / "topics"
    if not topics_dir.exists():
        return set()

    topic_ids: set[str] = set()
    for markdown_file in topics_dir.rglob("*.md"):
        parts = markdown_file.stem.split("-", 3)
        if len(parts) == 4:
            topic_ids.add(parts[3])
    return topic_ids


def _filter_missing_media(topic: Topic, source_group_dir: Path) -> Topic:
    images_dir = source_group_dir / "images"
    files_dir = source_group_dir / "files"

    images = _existing_names(images_dir, topic.images, "image", topic.topic_id)
    files = _existing_names(files_dir, topic.files, "file", topic.topic_id)
    answer_images = _existing_names(images_dir, topic.answer_images, "answer image", topic.topic_id)
    return replace(topic, images=images, files=files, answer_images=answer_images)


def _existing_names(base_dir: Path, names: list[str], label: str, topic_id: str) -> list[str]:
    existing: list[str] = []
    for name in names:
        if (base_dir / name).exists():
            existing.append(name)
        else:
            logger.warning("Missing %s for topic %s: %s", label, topic_id, name)
    return existing


def _create_media_link(source: Path, target: Path) -> None:
    if not source.exists() or not any(source.iterdir()):
        return
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return
        target.unlink()
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source.resolve(), target_is_directory=True)


def _write_indexes(output_dir: Path, topics: list[Topic]) -> None:
    indexes_dir = output_dir / "indexes"
    indexes_dir.mkdir(parents=True, exist_ok=True)
    (indexes_dir / "by-type.md").write_text(generate_by_type_index(topics), encoding="utf-8")
    (indexes_dir / "by-author.md").write_text(generate_by_author_index(topics), encoding="utf-8")
    (indexes_dir / "by-month.md").write_text(generate_by_month_index(topics), encoding="utf-8")


def _write_readme(output_dir: Path, group_id: str, topics: list[Topic]) -> None:
    counts: dict[str, int] = {}
    for topic in topics:
        counts[topic.type] = counts.get(topic.type, 0) + 1

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
    for type_name in sorted(counts):
        lines.append(f"| {type_name} | {counts[type_name]} |")
    lines.extend(
        [
            "",
            "Generated by `convert_to_kb.py`. Tags in frontmatter are for manual/AI annotation.",
            "",
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
