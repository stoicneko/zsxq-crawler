"""Integration tests for the Flask web viewer API (web/app.py)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so `web.app` is importable.
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Fixture topic data
# ---------------------------------------------------------------------------

TOPIC_TALK_WITH_IMAGES = {
    "topic_id": "topic_001",
    "type": "talk",
    "create_time": "2024-06-15T10:00:00+00:00",
    "text": "This is a talk with images",
    "digested": True,
    "images": [
        {"image_id": "img_001", "url": "https://example.com/img1.jpg"},
        {"image_id": "img_002", "url": "https://example.com/img2.jpg"},
    ],
    "comments": [],
}

TOPIC_QA_WITH_ANSWER = {
    "topic_id": "topic_002",
    "type": "q&a",
    "create_time": "2024-05-20T08:30:00+00:00",
    "text": "What is the best practice for Python?",
    "digested": False,
    "images": [],
    "answer": {
        "text": "Use virtual environments and follow PEP8",
        "images": [
            {"image_id": "img_003", "url": "https://example.com/answer_img.jpg"},
        ],
    },
    "comments": [],
}

TOPIC_TALK_NO_IMAGES = {
    "topic_id": "topic_003",
    "type": "talk",
    "create_time": "2024-04-10T14:00:00+00:00",
    "text": "Simple talk without images",
    "digested": False,
    "images": [],
    "comments": [],
}

TOPIC_WITH_EMBEDDED_LINK = {
    "topic_id": "topic_004",
    "type": "talk",
    "create_time": "2024-03-05T09:00:00+00:00",
    "text": 'Check this link: <e type="web" href="https://example.com" title="Example" />',
    "digested": True,
    "images": [],
    "comments": [],
}

TOPIC_WITH_COMMENTS = {
    "topic_id": "topic_005",
    "type": "talk",
    "create_time": "2024-02-01T12:00:00+00:00",
    "text": "Topic with comments",
    "digested": False,
    "images": [],
    "comments": [
        {"comment_id": "c001", "text": "Great post!", "create_time": "2024-02-01T13:00:00+00:00"},
        {"comment_id": "c002", "text": "Very helpful", "create_time": "2024-02-01T14:00:00+00:00"},
    ],
}

ALL_FIXTURE_TOPICS = [
    TOPIC_TALK_WITH_IMAGES,
    TOPIC_QA_WITH_ANSWER,
    TOPIC_TALK_NO_IMAGES,
    TOPIC_WITH_EMBEDDED_LINK,
    TOPIC_WITH_COMMENTS,
]


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app_client(tmp_path_factory):
    """Create a Flask test client pointed at a fixture topics directory.

    Scope is 'module' so the directory is shared across all tests in this file.
    Per-test state mutation (stars/tags) is handled by individual tests cleaning up.
    """
    import web.app as web_app

    tmp = tmp_path_factory.mktemp("zsxq_test")
    group_id = "test_group"
    topics_dir = tmp / group_id / "topics"
    topics_dir.mkdir(parents=True)

    # Write fixture JSON files
    for topic in ALL_FIXTURE_TOPICS:
        (topics_dir / f"{topic['topic_id']}.json").write_text(
            json.dumps(topic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Point the app at our fixture directory
    web_app.reload_config(tmp, group_id)
    web_app.load_topics()
    web_app._load_user_data()  # Ensure user_data is reset (file absent → empty)

    web_app.app.config["TESTING"] = True
    client = web_app.app.test_client()

    yield client, web_app

    # Cleanup: remove user_data.json if created during tests
    user_data_file = tmp / group_id / "user_data.json"
    if user_data_file.exists():
        user_data_file.unlink()


@pytest.fixture(autouse=True)
def reset_user_data(app_client):
    """Reset user_data.json before each test so tests are isolated."""
    _, web_app = app_client
    # Delete the file if it exists (reset to empty state)
    if web_app.USER_DATA_FILE.exists():
        web_app.USER_DATA_FILE.unlink()
    yield
    # Also clean up after each test
    if web_app.USER_DATA_FILE.exists():
        web_app.USER_DATA_FILE.unlink()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_json(client, url, **kwargs):
    """GET url and return parsed JSON."""
    resp = client.get(url, **kwargs)
    return resp, resp.get_json()


@pytest.fixture()
def reload_client(tmp_path):
    """Function-scoped client for reload tests — isolates side effects."""
    import web.app as web_app

    group_id = "reload_test_group"
    topics_dir = tmp_path / group_id / "topics"
    topics_dir.mkdir(parents=True)

    for topic in ALL_FIXTURE_TOPICS:
        (topics_dir / f"{topic['topic_id']}.json").write_text(
            json.dumps(topic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    web_app.reload_config(tmp_path, group_id)
    web_app.load_topics()

    web_app.app.config["TESTING"] = True
    client = web_app.app.test_client()

    yield client, web_app, topics_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIndex:
    def test_index_returns_200(self, app_client):
        client, _ = app_client
        resp = client.get("/")
        assert resp.status_code == 200


class TestApiTopics:
    def test_api_topics_pagination(self, app_client):
        """Verify page/per_page/total/pages fields in meta."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?page=1&per_page=2")
        assert resp.status_code == 200
        assert data["success"] is True
        meta = data["meta"]
        assert meta["total"] == 5
        assert meta["page"] == 1
        assert meta["per_page"] == 2
        assert meta["pages"] == 3  # ceil(5/2)
        assert len(data["data"]) == 2

    def test_api_topics_pagination_page2(self, app_client):
        """Page 2 with per_page=2 should return 2 items."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?page=2&per_page=2")
        assert resp.status_code == 200
        assert data["meta"]["page"] == 2
        assert len(data["data"]) == 2

    def test_api_topics_search(self, app_client):
        """Search by keyword returns only matching topics."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?q=Python")
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["meta"]["total"] == 1
        assert data["data"][0]["topic_id"] == "topic_002"

    def test_api_topics_search_in_comment(self, app_client):
        """Search finds keywords in comments."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?q=Great+post")
        assert resp.status_code == 200
        assert data["meta"]["total"] == 1
        assert data["data"][0]["topic_id"] == "topic_005"

    def test_api_topics_search_in_answer(self, app_client):
        """Search finds keywords inside the answer text of a Q&A topic."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?q=virtual+environments")
        assert resp.status_code == 200
        assert data["meta"]["total"] == 1
        assert data["data"][0]["topic_id"] == "topic_002"

    def test_api_topics_filter_type_talk(self, app_client):
        """Filter by type=talk returns only talk topics."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?type=talk")
        assert resp.status_code == 200
        assert data["success"] is True
        topic_ids = {t["topic_id"] for t in data["data"]}
        assert "topic_002" not in topic_ids  # topic_002 is q&a
        for t in data["data"]:
            assert t["type"] == "talk"

    def test_api_topics_filter_type_qa(self, app_client):
        """Filter by type=q&a returns only Q&A topics."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?type=q%26a")
        assert resp.status_code == 200
        assert data["meta"]["total"] == 1
        assert data["data"][0]["topic_id"] == "topic_002"

    def test_api_topics_filter_digested(self, app_client):
        """Filter digested=true returns only digested topics."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?digested=true")
        assert resp.status_code == 200
        assert data["success"] is True
        for t in data["data"]:
            assert t["digested"] is True
        assert data["meta"]["total"] == 2  # topic_001 and topic_004

    def test_api_topics_filter_digested_false(self, app_client):
        """Filter digested=false filters to non-digested topics.

        The app evaluates: digested_filter = ("false" in ("1", "true")) = False
        which filters for topics where digested == False.
        Fixture: topic_002, topic_003, topic_005 are non-digested → total 3.
        """
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?digested=false")
        assert resp.status_code == 200
        assert data["meta"]["total"] == 3
        for t in data["data"]:
            assert not t["digested"]

    def test_api_topics_filter_date_range_since(self, app_client):
        """since param filters topics created on or after the date."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?since=2024-05-01")
        assert resp.status_code == 200
        for t in data["data"]:
            assert t["create_time"] >= "2024-05-01"
        assert data["meta"]["total"] == 2  # topic_001 (Jun) and topic_002 (May)

    def test_api_topics_filter_date_range_until(self, app_client):
        """until param filters topics created on or before the date."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?until=2024-03-31")
        assert resp.status_code == 200
        for t in data["data"]:
            assert t["create_time"] <= "2024-03-31T23:59:59"
        assert data["meta"]["total"] == 2  # topic_004 (Mar) and topic_005 (Feb)

    def test_api_topics_filter_date_range_since_until(self, app_client):
        """since+until together returns topics within the range."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?since=2024-04-01&until=2024-05-31")
        assert resp.status_code == 200
        assert data["meta"]["total"] == 2  # topic_002 (May) and topic_003 (Apr)

    def test_api_invalid_date_returns_400(self, app_client):
        """Invalid since/until returns HTTP 400."""
        client, _ = app_client
        resp = client.get("/api/topics?since=not-a-date")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert "since" in data["error"].lower()

    def test_api_invalid_until_returns_400(self, app_client):
        """Invalid until value returns HTTP 400."""
        client, _ = app_client
        resp = client.get("/api/topics?until=2024-13-99")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False


class TestStar:
    def test_api_toggle_star(self, app_client):
        """POST /api/topics/{id}/star toggles star and returns correct state."""
        client, _ = app_client
        resp = client.post("/api/topics/topic_001/star", content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["starred"] is True
        assert data["data"]["topic_id"] == "topic_001"

    def test_api_toggle_star_twice_unsets(self, app_client):
        """Toggling star twice returns to unstarred state."""
        client, _ = app_client
        client.post("/api/topics/topic_001/star", content_type="application/json")
        resp = client.post("/api/topics/topic_001/star", content_type="application/json")
        data = resp.get_json()
        assert data["data"]["starred"] is False

    def test_api_set_star_explicitly(self, app_client):
        """POST with body {"starred": true} sets star to true."""
        client, _ = app_client
        resp = client.post(
            "/api/topics/topic_001/star",
            data=json.dumps({"starred": True}),
            content_type="application/json",
        )
        assert resp.get_json()["data"]["starred"] is True

    def test_api_star_persists(self, app_client):
        """Star is reflected in subsequent GET /api/topics responses."""
        client, _ = app_client
        # Star topic_001
        client.post("/api/topics/topic_001/star", content_type="application/json")
        # Fetch topics and verify is_starred field
        resp, data = get_json(client, "/api/topics")
        topic = next(t for t in data["data"] if t["topic_id"] == "topic_001")
        assert topic["is_starred"] is True

    def test_api_topics_not_found_star(self, app_client):
        """POST star on nonexistent topic_id returns 404."""
        client, _ = app_client
        resp = client.post("/api/topics/nonexistent_id/star", content_type="application/json")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False


class TestTags:
    def test_api_update_tags(self, app_client):
        """POST /api/topics/{id}/tags sets tags and returns them."""
        client, _ = app_client
        resp = client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": ["python", "important"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["topic_id"] == "topic_001"
        assert set(data["data"]["tags"]) == {"python", "important"}

    def test_api_update_tags_empty(self, app_client):
        """POST with empty tags list clears all tags."""
        client, _ = app_client
        # First add some tags
        client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": ["python"]}),
            content_type="application/json",
        )
        # Then clear them
        resp = client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": []}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["tags"] == []

    def test_api_update_tags_invalid_not_list(self, app_client):
        """POST with tags as a string (not list) returns 400."""
        client, _ = app_client
        resp = client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": "not-a-list"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_api_update_tags_invalid_empty_string(self, app_client):
        """POST with an empty string tag returns 400."""
        client, _ = app_client
        resp = client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": ["valid", ""]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_api_update_tags_not_found(self, app_client):
        """POST tags on nonexistent topic_id returns 404."""
        client, _ = app_client
        resp = client.post(
            "/api/topics/nonexistent_id/tags",
            data=json.dumps({"tags": ["foo"]}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_api_all_tags(self, app_client):
        """GET /api/tags returns all unique tags with counts."""
        client, _ = app_client
        # Add tags to two topics
        client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": ["python", "important"]}),
            content_type="application/json",
        )
        client.post(
            "/api/topics/topic_002/tags",
            data=json.dumps({"tags": ["python", "qa"]}),
            content_type="application/json",
        )
        resp, data = get_json(client, "/api/tags")
        assert resp.status_code == 200
        assert data["success"] is True
        tags_by_name = {item["tag"]: item["count"] for item in data["data"]}
        assert tags_by_name["python"] == 2
        assert tags_by_name["important"] == 1
        assert tags_by_name["qa"] == 1

    def test_api_all_tags_empty(self, app_client):
        """GET /api/tags returns empty list when no tags set."""
        client, _ = app_client
        resp, data = get_json(client, "/api/tags")
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["data"] == []

    def test_api_filter_by_tag(self, app_client):
        """GET /api/topics?tag=X returns only topics tagged with X."""
        client, _ = app_client
        client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": ["featured"]}),
            content_type="application/json",
        )
        resp, data = get_json(client, "/api/topics?tag=featured")
        assert resp.status_code == 200
        assert data["meta"]["total"] == 1
        assert data["data"][0]["topic_id"] == "topic_001"


class TestStats:
    def test_api_stats(self, app_client):
        """GET /api/stats returns correct aggregate counts."""
        client, _ = app_client
        resp, data = get_json(client, "/api/stats")
        assert resp.status_code == 200
        assert data["success"] is True
        stats = data["data"]
        assert stats["total_topics"] == 5
        assert stats["by_type"]["talk"] == 4
        assert stats["by_type"]["q&a"] == 1
        assert stats["digested_count"] == 2
        assert stats["starred_count"] == 0
        assert stats["total_images"] == 2  # topic_001 has 2 images
        assert stats["total_comments"] == 2  # topic_005 has 2 comments
        assert "group_id" in stats

    def test_api_stats_starred_count(self, app_client):
        """stats.starred_count reflects starred topics."""
        client, _ = app_client
        client.post("/api/topics/topic_001/star", content_type="application/json")
        client.post("/api/topics/topic_003/star", content_type="application/json")
        resp, data = get_json(client, "/api/stats")
        assert data["data"]["starred_count"] == 2

    def test_api_stats_total_tags(self, app_client):
        """stats.total_tags counts topics that have at least one tag."""
        client, _ = app_client
        client.post(
            "/api/topics/topic_001/tags",
            data=json.dumps({"tags": ["t1"]}),
            content_type="application/json",
        )
        client.post(
            "/api/topics/topic_002/tags",
            data=json.dumps({"tags": ["t2"]}),
            content_type="application/json",
        )
        resp, data = get_json(client, "/api/stats")
        assert data["data"]["total_tags"] == 2


class TestReload:
    def test_api_reload_returns_success(self, reload_client):
        """POST /api/reload reloads topics and returns count."""
        client, _, _ = reload_client
        resp = client.post("/api/reload")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["topics_count"] == 5

    def test_api_reload_picks_up_new_file(self, reload_client):
        """After adding a new topic JSON file, reload picks it up."""
        client, web_app, _ = reload_client
        new_topic = {
            "topic_id": "topic_new",
            "type": "talk",
            "create_time": "2026-01-01T00:00:00+00:00",
            "text": "Brand new topic",
            "digested": False,
            "images": [],
            "comments": [],
        }
        new_path = web_app.TOPICS_DIR / "topic_new.json"
        new_path.write_text(
            json.dumps(new_topic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            resp = client.post("/api/reload")
            data = resp.get_json()
            assert data["topics_count"] == 6

            resp2, data2 = get_json(client, "/api/topics?q=Brand+new")
            assert resp2.status_code == 200
            assert data2["meta"]["total"] == 1
            assert data2["data"][0]["topic_id"] == "topic_new"
        finally:
            new_path.unlink(missing_ok=True)
            client.post("/api/reload")

    def test_api_reload_with_valid_token(self, reload_client):
        """When ZSXQ_RELOAD_TOKEN is set, valid token is accepted."""
        client, _, _ = reload_client
        original_token = os.environ.get("ZSXQ_RELOAD_TOKEN")
        os.environ["ZSXQ_RELOAD_TOKEN"] = "test-secret-token"
        try:
            resp = client.post(
                "/api/reload",
                headers={"Authorization": "Bearer test-secret-token"},
            )
            assert resp.status_code == 200
            assert resp.get_json()["success"] is True
        finally:
            if original_token is None:
                os.environ.pop("ZSXQ_RELOAD_TOKEN", None)
            else:
                os.environ["ZSXQ_RELOAD_TOKEN"] = original_token

    def test_api_reload_rejects_bad_token(self, reload_client):
        """When ZSXQ_RELOAD_TOKEN is set, wrong token returns 403."""
        client, _, _ = reload_client
        original_token = os.environ.get("ZSXQ_RELOAD_TOKEN")
        os.environ["ZSXQ_RELOAD_TOKEN"] = "test-secret-token"
        try:
            resp = client.post(
                "/api/reload",
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert resp.status_code == 403
            assert resp.get_json()["success"] is False
        finally:
            if original_token is None:
                os.environ.pop("ZSXQ_RELOAD_TOKEN", None)
            else:
                os.environ["ZSXQ_RELOAD_TOKEN"] = original_token


class TestEmbeddedTags:
    def test_parse_embedded_tags(self, app_client):
        """Topic with <e type="web"> gets text_html with <a> link."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics")
        topic = next(t for t in data["data"] if t["topic_id"] == "topic_004")
        assert '<a href="https://example.com"' in topic["text_html"]
        assert "Example" in topic["text_html"]
        assert "target=\"_blank\"" in topic["text_html"]

    def test_parse_embedded_tags_function(self):
        """Unit test _parse_embedded_tags directly."""
        from web.app import _parse_embedded_tags

        text = 'Visit <e type="web" href="https://example.com" title="Example" /> now'
        result = _parse_embedded_tags(text)
        assert '<a href="https://example.com"' in result
        assert "Example" in result
        assert "<e" not in result

    def test_parse_embedded_tags_escapes_plain_text(self):
        """Plain text with < and > is HTML-escaped."""
        from web.app import _parse_embedded_tags

        text = "2 < 3 and 4 > 2"
        result = _parse_embedded_tags(text)
        assert "&lt;" in result
        assert "&gt;" in result
        assert "<" not in result.replace("<br>", "")

    def test_parse_embedded_tags_newline_to_br(self):
        """Newlines in plain text become <br> elements."""
        from web.app import _parse_embedded_tags

        text = "line one\nline two"
        result = _parse_embedded_tags(text)
        assert "<br>" in result

    def test_answer_text_html_enriched(self, app_client):
        """Q&A topic's answer gets text_html field populated."""
        client, _ = app_client
        resp, data = get_json(client, "/api/topics?type=q%26a")
        assert resp.status_code == 200
        topic = data["data"][0]
        assert "answer" in topic
        assert "text_html" in topic["answer"]
        assert "virtual environments" in topic["answer"]["text_html"]
