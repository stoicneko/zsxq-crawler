"""Integration tests for convert_to_kb.py end-to-end conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from convert_to_kb import convert, discover_group_id


@pytest.fixture
def sample_source(tmp_path: Path) -> Path:
    group_dir = tmp_path / "source" / "12345"
    topics_dir = group_dir / "topics"
    images_dir = group_dir / "images"
    files_dir = group_dir / "files"
    topics_dir.mkdir(parents=True)
    images_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)

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

        assert (output_dir / "topics" / "2026" / "03" / "2026-03-05-100.md").exists()
        assert (output_dir / "topics" / "2026" / "02" / "2026-02-15-200.md").exists()

        talk_md = (output_dir / "topics" / "2026" / "03" / "2026-03-05-100.md").read_text(
            encoding="utf-8"
        )
        assert "Hello world" in talk_md
        assert 'topic_id: "100"' in talk_md

        qa_md = (output_dir / "topics" / "2026" / "02" / "2026-02-15-200.md").read_text(
            encoding="utf-8"
        )
        assert "## 提问" in qa_md
        assert "## 回答" in qa_md

    def test_index_files_generated(self, sample_source: Path, output_dir: Path):
        convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        assert (output_dir / "indexes" / "by-type.md").exists()
        assert (output_dir / "indexes" / "by-author.md").exists()
        assert (output_dir / "indexes" / "by-month.md").exists()

        by_type = (output_dir / "indexes" / "by-type.md").read_text(encoding="utf-8")
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
        assert "2" in readme.read_text(encoding="utf-8")

    def test_incremental_skips_existing(self, sample_source: Path, output_dir: Path):
        convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        stats = convert(
            source_dir=sample_source,
            output_dir=output_dir,
            group_id="12345",
            incremental=True,
        )
        assert stats["converted"] == 0
        assert stats["skipped"] == 2

    def test_malformed_json_skipped(self, sample_source: Path, output_dir: Path):
        bad_file = sample_source / "12345" / "topics" / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")

        stats = convert(source_dir=sample_source, output_dir=output_dir, group_id="12345")
        assert stats["errors"] == 1
        assert stats["converted"] == 2


class TestDiscoverGroupId:
    def test_auto_detect(self, sample_source: Path):
        assert discover_group_id(sample_source) == "12345"

    def test_no_groups_raises(self, tmp_path: Path):
        empty_source = tmp_path / "empty"
        empty_source.mkdir()
        with pytest.raises(SystemExit):
            discover_group_id(empty_source)
