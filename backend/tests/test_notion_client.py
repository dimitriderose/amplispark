"""Tests for backend.services.notion_client."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.notion_client import (
    _build_page_body,
    _build_post_properties,
    _extract_title,
    create_page,
    ensure_database_schema,
    exchange_code,
    search_databases,
)

NOTION_API = "https://api.notion.com/v1"


def _make_mock_client(json_return=None, status_code=200):
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_return or {}
    mock_resp.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.patch = AsyncMock(return_value=mock_resp)
    return mock_client, mock_resp


def _patch_async_client(mock_client):
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return patch("httpx.AsyncClient", return_value=mock_ctx)


class TestExtractTitle:
    def test_extracts_plain_text_from_list(self):
        db = {"title": [{"plain_text": "My Database"}]}
        assert _extract_title(db) == "My Database"

    def test_concatenates_multiple_parts(self):
        db = {"title": [{"plain_text": "Hello "}, {"plain_text": "World"}]}
        assert _extract_title(db) == "Hello World"

    def test_returns_untitled_when_title_is_not_list(self):
        db = {"title": "not a list"}
        assert _extract_title(db) == "Untitled"

    def test_returns_empty_string_when_title_list_is_empty(self):
        db = {"title": []}
        assert _extract_title(db) == ""

    def test_returns_empty_string_when_title_key_missing(self):
        db = {}
        assert _extract_title(db) == ""

    def test_handles_missing_plain_text_key_in_parts(self):
        db = {"title": [{"other_key": "ignored"}, {"plain_text": "real"}]}
        assert _extract_title(db) == "real"


class TestBuildPostProperties:
    def test_builds_required_properties(self):
        post = {"theme": "Growth", "caption": "Hello", "status": "draft", "content_type": "photo"}
        props = _build_post_properties(post, 0, "instagram")
        assert props["Name"]["title"][0]["text"]["content"] == "Day 1 - Instagram - Growth"
        assert props["Platform"]["select"]["name"] == "Instagram"
        assert props["Day"]["number"] == 1
        assert props["Status"]["select"]["name"] == "draft"
        assert props["Content Type"]["select"]["name"] == "photo"

    def test_day_index_is_one_based(self):
        post = {}
        props = _build_post_properties(post, 4, "linkedin")
        assert props["Day"]["number"] == 5
        assert "Day 5 - Linkedin" in props["Name"]["title"][0]["text"]["content"]

    def test_title_omits_theme_when_empty(self):
        post = {"theme": ""}
        props = _build_post_properties(post, 0, "twitter")
        assert props["Name"]["title"][0]["text"]["content"] == "Day 1 - Twitter"

    def test_hashtags_joined_with_hash_prefix(self):
        post = {"hashtags": ["marketing", "#growth"]}
        props = _build_post_properties(post, 0, "instagram")
        assert props["Hashtags"]["rich_text"][0]["text"]["content"] == "#marketing #growth"

    def test_hashtags_property_absent_when_empty(self):
        post = {"hashtags": []}
        props = _build_post_properties(post, 0, "instagram")
        assert "Hashtags" not in props

    def test_image_url_set_from_first_image(self):
        post = {"image_urls": ["https://example.com/img1.png", "https://example.com/img2.png"]}
        props = _build_post_properties(post, 0, "instagram")
        assert props["Image URL"]["url"] == "https://example.com/img1.png"

    def test_image_url_absent_when_no_images(self):
        post = {}
        props = _build_post_properties(post, 0, "instagram")
        assert "Image URL" not in props

    def test_caption_truncated_to_2000_chars(self):
        post = {"caption": "x" * 3000}
        props = _build_post_properties(post, 0, "instagram")
        assert len(props["Caption"]["rich_text"][0]["text"]["content"]) == 2000

    def test_posting_time_included(self):
        post = {"posting_time": "9:00 AM"}
        props = _build_post_properties(post, 0, "instagram")
        assert props["Posting Time"]["rich_text"][0]["text"]["content"] == "9:00 AM"


class TestBuildPageBody:
    def test_builds_paragraph_blocks_from_caption(self):
        blocks = _build_page_body("Hello World", [])
        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Hello World"

    def test_splits_on_double_newline(self):
        blocks = _build_page_body("Para one\n\nPara two", [])
        assert len(blocks) == 2
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Para one"
        assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == "Para two"

    def test_appends_hashtag_block(self):
        blocks = _build_page_body("Caption text", ["marketing", "growth"])
        assert blocks[-1]["paragraph"]["rich_text"][0]["text"]["content"] == "#marketing #growth"

    def test_returns_empty_list_for_empty_caption_and_no_hashtags(self):
        blocks = _build_page_body("", [])
        assert blocks == []

    def test_skips_blank_paragraphs(self):
        blocks = _build_page_body("Para one\n\n\n\nPara two", [])
        assert len(blocks) == 2

    def test_paragraph_content_truncated_to_2000(self):
        long_caption = "x" * 3000
        blocks = _build_page_body(long_caption, [])
        assert len(blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]) == 2000

    def test_all_blocks_have_correct_object_type(self):
        blocks = _build_page_body("Hello", ["tag1"])
        for block in blocks:
            assert block["object"] == "block"
            assert block["type"] == "paragraph"


class TestExchangeCode:
    async def test_returns_token_data_on_success(self):
        mock_client, mock_resp = _make_mock_client(
            json_return={"access_token": "token-abc", "workspace_id": "ws-1"}
        )
        with _patch_async_client(mock_client):
            result = await exchange_code(
                "auth-code", "client-id", "client-secret", "https://redirect.uri"
            )
        assert result["access_token"] == "token-abc"
        assert result["workspace_id"] == "ws-1"

    async def test_sends_basic_auth_header(self):
        mock_client, _ = _make_mock_client(json_return={"access_token": "t"})
        with _patch_async_client(mock_client):
            await exchange_code("code", "my-client", "my-secret", "https://redirect.uri")
        call_kwargs = mock_client.post.call_args
        expected_credentials = base64.b64encode(b"my-client:my-secret").decode()
        assert call_kwargs.kwargs["headers"]["Authorization"] == f"Basic {expected_credentials}"

    async def test_sends_correct_grant_type(self):
        mock_client, _ = _make_mock_client(json_return={"access_token": "t"})
        with _patch_async_client(mock_client):
            await exchange_code("code", "cid", "csec", "https://redirect.uri")
        json_body = mock_client.post.call_args.kwargs["json"]
        assert json_body["grant_type"] == "authorization_code"
        assert json_body["code"] == "code"
        assert json_body["redirect_uri"] == "https://redirect.uri"

    async def test_raises_on_http_error(self):
        mock_client, mock_resp = _make_mock_client(status_code=401)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_resp
        )
        with _patch_async_client(mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await exchange_code("bad-code", "cid", "csec", "https://redirect.uri")


class TestSearchDatabases:
    async def test_returns_list_of_databases(self):
        mock_client, _ = _make_mock_client(
            json_return={
                "results": [
                    {"id": "db-1", "title": [{"plain_text": "My DB"}]},
                    {"id": "db-2", "title": [{"plain_text": "Another DB"}]},
                ]
            }
        )
        with _patch_async_client(mock_client):
            result = await search_databases("access-token")
        assert len(result) == 2
        assert result[0] == {"id": "db-1", "title": "My DB"}
        assert result[1] == {"id": "db-2", "title": "Another DB"}

    async def test_returns_empty_list_when_no_results(self):
        mock_client, _ = _make_mock_client(json_return={"results": []})
        with _patch_async_client(mock_client):
            result = await search_databases("access-token")
        assert result == []

    async def test_sends_database_filter(self):
        mock_client, _ = _make_mock_client(json_return={"results": []})
        with _patch_async_client(mock_client):
            await search_databases("tok")
        json_body = mock_client.post.call_args.kwargs["json"]
        assert json_body["filter"]["value"] == "database"
        assert json_body["filter"]["property"] == "object"

    async def test_sends_bearer_auth_header(self):
        mock_client, _ = _make_mock_client(json_return={"results": []})
        with _patch_async_client(mock_client):
            await search_databases("my-access-token")
        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-access-token"

    async def test_raises_on_http_error(self):
        mock_client, mock_resp = _make_mock_client(status_code=403)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_resp
        )
        with _patch_async_client(mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await search_databases("bad-token")


class TestCreatePage:
    async def test_returns_created_page_data(self):
        mock_client, _ = _make_mock_client(json_return={"id": "page-id-1", "object": "page"})
        post = {
            "caption": "Hello",
            "hashtags": ["#test"],
            "status": "draft",
            "content_type": "photo",
        }
        with _patch_async_client(mock_client):
            result = await create_page("access-tok", "db-id", post, 0, "instagram")
        assert result["id"] == "page-id-1"

    async def test_sends_parent_database_id(self):
        mock_client, _ = _make_mock_client(json_return={"id": "p"})
        post = {"caption": "x"}
        with _patch_async_client(mock_client):
            await create_page("tok", "database-xyz", post, 0, "instagram")
        json_body = mock_client.post.call_args.kwargs["json"]
        assert json_body["parent"]["database_id"] == "database-xyz"

    async def test_includes_children_when_caption_has_content(self):
        mock_client, _ = _make_mock_client(json_return={"id": "p"})
        post = {"caption": "My caption text"}
        with _patch_async_client(mock_client):
            await create_page("tok", "db-id", post, 0, "instagram")
        json_body = mock_client.post.call_args.kwargs["json"]
        assert "children" in json_body
        assert len(json_body["children"]) > 0

    async def test_omits_children_when_caption_is_empty(self):
        mock_client, _ = _make_mock_client(json_return={"id": "p"})
        post = {"caption": ""}
        with _patch_async_client(mock_client):
            await create_page("tok", "db-id", post, 0, "instagram")
        json_body = mock_client.post.call_args.kwargs["json"]
        assert "children" not in json_body

    async def test_raises_permission_error_on_401(self):
        mock_client, mock_resp = _make_mock_client(status_code=401)
        mock_resp.raise_for_status = MagicMock()
        post = {"caption": "x"}
        with _patch_async_client(mock_client):
            with pytest.raises(PermissionError, match="Notion token expired"):
                await create_page("expired-tok", "db-id", post, 0, "instagram")

    async def test_raises_http_error_on_non_401_failure(self):
        mock_client, mock_resp = _make_mock_client(status_code=500)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_resp
        )
        post = {"caption": "x"}
        with _patch_async_client(mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await create_page("tok", "db-id", post, 0, "instagram")


class TestEnsureDatabaseSchema:
    async def test_adds_missing_properties(self):
        existing = {"Name": {"title": {}}}
        get_resp = MagicMock()
        get_resp.json.return_value = {"properties": existing}
        get_resp.raise_for_status = MagicMock()
        get_resp.status_code = 200

        patch_resp = MagicMock()
        patch_resp.raise_for_status = MagicMock()
        patch_resp.status_code = 200

        mock_client_get = AsyncMock()
        mock_client_get.get = AsyncMock(return_value=get_resp)

        mock_client_patch = AsyncMock()
        mock_client_patch.patch = AsyncMock(return_value=patch_resp)

        ctx_get = MagicMock()
        ctx_get.__aenter__ = AsyncMock(return_value=mock_client_get)
        ctx_get.__aexit__ = AsyncMock(return_value=None)

        ctx_patch = MagicMock()
        ctx_patch.__aenter__ = AsyncMock(return_value=mock_client_patch)
        ctx_patch.__aexit__ = AsyncMock(return_value=None)

        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            return ctx_get if call_count == 1 else ctx_patch

        with patch("httpx.AsyncClient", side_effect=side_effect):
            await ensure_database_schema("tok", "db-id")

        patch_call = mock_client_patch.patch.call_args
        added_props = patch_call.kwargs["json"]["properties"]
        assert "Platform" in added_props
        assert "Day" in added_props
        assert "Caption" in added_props
        assert "Name" not in added_props

    async def test_skips_patch_when_all_properties_exist(self):
        all_desired = {
            "Platform": {},
            "Day": {},
            "Status": {},
            "Caption": {},
            "Hashtags": {},
            "Image URL": {},
            "Posting Time": {},
            "Content Type": {},
        }
        get_resp = MagicMock()
        get_resp.json.return_value = {"properties": all_desired}
        get_resp.raise_for_status = MagicMock()
        get_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.patch = AsyncMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_client)
        ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=ctx):
            await ensure_database_schema("tok", "db-id")

        mock_client.patch.assert_not_called()

    async def test_raises_on_get_http_error(self):
        get_resp = MagicMock()
        get_resp.status_code = 404
        get_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=get_resp
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=get_resp)

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_client)
        ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=ctx):
            with pytest.raises(httpx.HTTPStatusError):
                await ensure_database_schema("tok", "bad-db-id")
