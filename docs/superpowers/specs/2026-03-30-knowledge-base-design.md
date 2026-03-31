# Knowledge Base Design Spec

## Overview

Convert 16,000+ zsxq topic JSON files into an Obsidian-compatible Markdown vault, serving as a personal knowledge base for both human browsing and AI (Claude Code) local retrieval.

## Goals

1. **Human use**: Browse, search, tag, and organize topics in Obsidian
2. **AI use**: Claude Code can Grep/Read Markdown files for knowledge retrieval
3. **No social data**: Strip comments, likes, rewards, reading counts
4. **Incremental**: Support re-running to pick up new topics from monitor

## Non-Goals

- Vector database / RAG (out of scope for v1)
- AI auto-classification of topics (can be done later via tags)
- Web-based viewer for the knowledge base (Obsidian is the viewer)
- Comment or reply data preservation

## Data Source

- **Location**: `output/{group_id}/topics/*.json`
- **Count**: ~16,000 topic files
- **Types**: `talk` (~8,200), `q&a` (~7,800); `task` and `solution` types not present in current dataset
- **Media**: Images downloaded to `output/{group_id}/images/`

### Source JSON Schema (relevant fields)

```json
{
  "topic_id": "string",
  "type": "talk | q&a | task | solution",
  "create_time": "ISO 8601 with timezone",
  "author": { "user_id": "string", "name": "string" },
  "text": "string (main content)",
  "digested": "boolean (curated/featured flag)",
  "images": [{ "image_id": "string", "filename": "string" }],
  "files": [{ "file_id": "string", "filename": "string" }],
  "answer": {
    "text": "string",
    "author": { "user_id": "string", "name": "string" },
    "images": []
  }
}
```

Fields **excluded** from conversion: `likes_count`, `rewards_count`, `comments_count`, `reading_count`, `comments`.

## Output Format

### Markdown File Structure

Each topic becomes one `.md` file with YAML frontmatter.

**Filename**: `{YYYY-MM-DD}-{topic_id}.md`

#### talk type

```markdown
---
topic_id: "14588121528885522"
type: talk
author: "幻夜梦屿"
date: 2026-03-05
time: "17:28:16"
digested: false
tags: []
---

消费满1000➕我微信就有这好处，你随便发，反正我不看😁

![](../../../images/14588121528885522_1522851252554222.jpg)
```

#### q&a type

```markdown
---
topic_id: "14588121115225882"
type: q&a
author: ""
date: 2026-03-07
time: "12:13:16"
digested: false
tags: []
---

## 提问

我的妈呀哥哥，合租遇到精神病了……

## 回答

> **幻夜梦屿**：这都是小事 说白了你不能完全打赢她……

*(Answer may also include images, rendered below the text)*
```

#### task type

```markdown
---
topic_id: "xxx"
type: task
author: "作者名"
date: 2026-01-01
time: "10:00:00"
digested: false
tags: []
---

## 任务

任务内容……
```

#### solution type

```markdown
---
topic_id: "xxx"
type: solution
author: "作者名"
date: 2026-01-01
time: "10:00:00"
digested: false
tags: []
---

## 问题

问题内容……

## 解答

解答内容……
```

### Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `topic_id` | string | Original zsxq topic ID |
| `type` | string | Topic type: talk, q&a, task, solution |
| `author` | string | Author display name |
| `date` | date | Creation date (YYYY-MM-DD) |
| `time` | string | Creation time (HH:MM:SS) |
| `digested` | boolean | Whether marked as curated/featured |
| `tags` | list | Empty array, for manual/AI tagging later |

### Image References

- Images referenced via relative path: `../../../images/{filename}` (3 levels up from `topics/YYYY/MM/`)
- Image files are **symlinked** from `output/{group_id}/images/` to `knowledge-base/images/`
- If source image doesn't exist, skip the image reference and log a warning
- **Answer images** (q&a type): rendered after the answer text blockquote

### File Attachments

- Files referenced via relative path: `../../../files/{filename}` (3 levels up from `topics/YYYY/MM/`)
- File attachments are **symlinked** from `output/{group_id}/files/` to `knowledge-base/files/`
- If source `files/` directory is empty or missing, skip symlink creation

## Directory Structure

```
knowledge-base/                     # Obsidian Vault root
├── topics/                         # Topic content
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── 2024-01-15-xxxxx.md
│   │   │   └── ...
│   │   ├── 02/
│   │   └── ...
│   ├── 2025/
│   └── 2026/
├── images/                         # Symlinked from output/
├── files/                          # Symlinked from output/
├── indexes/                        # Auto-generated index files
│   ├── by-type.md                  # Topics grouped by type (talk/q&a)
│   ├── by-author.md                # Topics grouped by author
│   └── by-month.md                 # Topics grouped by year/month
└── README.md                       # Vault description + stats
```

### Index File Format

Each index groups topics with Obsidian wiki-links:

```markdown
# Topics by Type

## talk

- [[2026-03-05-14588121528885522|消费满1000➕我微信就有...]]
- ...

## q&a

- [[2026-03-07-14588121115225882|合租遇到精神病了]]
- ...
```

Link display text is truncated to first 50 characters of topic text. For empty-text topics (image-only), use `[图片]` as fallback display text.

## Conversion Script: `convert_to_kb.py`

### Location

`convert_to_kb.py` in project root (outside the vault to avoid Obsidian indexing)

### CLI Interface

```bash
python convert_to_kb.py                                    # full conversion
python convert_to_kb.py --incremental                      # only new topics
python convert_to_kb.py --group-id 48412145525258          # specific group
python convert_to_kb.py --output-dir ./my-kb               # custom output
python convert_to_kb.py --source-dir ./output              # custom source
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--group-id` | Auto-detect from output/ | zsxq group ID |
| `--source-dir` | `./output` | Path to crawler output |
| `--output-dir` | `./knowledge-base` | Path to vault root |
| `--incremental` | false | Skip already-converted topics |
| `--dry-run` | false | Print what would be done without writing |

### Processing Pipeline

1. **Discover**: Scan `{source_dir}/{group_id}/topics/*.json`
2. **Filter** (incremental mode): Compare topic IDs against existing `.md` files
3. **Parse**: Load each JSON, extract relevant fields
4. **Transform**: Convert to Markdown with frontmatter
5. **Write**: Save to `topics/YYYY/MM/{date}-{topic_id}.md`
6. **Link media**: Create symlinks for images/ and files/ directories
7. **Index**: Generate index files in `indexes/`
8. **Report**: Print summary (total, new, skipped, errors)

### Error Handling

- JSON parse failure → log warning, skip file, continue
- Missing image file → omit image reference, log warning
- Missing required fields (topic_id, type, create_time) → skip, log error
- Q&A with null/empty answer → render "提问" section only, omit "回答" section
- Empty text (image-only posts) → render images directly without text paragraph
- Existing file in non-incremental mode → overwrite
- Unknown topic type → convert with generic format (just text body), log warning

### Text Processing

- Preserve original text as-is (including emoji text like `[呲牙]`)
- Newlines in source text → preserved as Markdown paragraphs
- No HTML sanitization needed (source is plain text)

## Testing Strategy

### Unit Tests

- `test_parse_topic()` — JSON to internal model for each topic type
- `test_render_markdown()` — internal model to Markdown string
- `test_frontmatter_generation()` — correct YAML frontmatter output
- `test_filename_generation()` — date + topic_id format
- `test_image_reference()` — correct relative path generation
- `test_incremental_detection()` — correctly identifies new vs existing topics
- `test_text_processing()` — emoji text, newlines, edge cases

### Integration Tests

- `test_full_conversion()` — end-to-end with sample JSON files
- `test_incremental_conversion()` — only converts new topics
- `test_index_generation()` — indexes contain correct links
- `test_symlink_creation()` — media symlinks point correctly

### Coverage Target

80%+ line coverage on `convert_to_kb.py`.

## Future Extensions (out of scope)

- AI auto-tagging via Claude API (populate `tags` field)
- Vector embedding + semantic search
- Obsidian Dataview queries for advanced filtering
- Monitor integration: auto-convert new topics on arrival
