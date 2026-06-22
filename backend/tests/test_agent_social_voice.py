"""Unit tests for backend/agents/social_voice_agent.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_text_response(text: str) -> MagicMock:
    part = MagicMock()
    part.text = text
    part.inline_data = None
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.candidates = [candidate]
    response.text = text
    return response


def _make_empty_response() -> MagicMock:
    response = MagicMock()
    response.candidates = []
    response.text = ""
    return response


VALID_VOICE_JSON = json.dumps(
    {
        "voice_characteristics": ["direct", "conversational", "data-driven"],
        "common_phrases": ["the truth is", "here's what I've found"],
        "emoji_usage": "minimal",
        "average_post_length": "medium",
        "successful_patterns": ["storytelling", "numbered lists"],
        "tone_adjectives": ["warm", "authoritative", "practical"],
    }
)


@pytest.mark.asyncio
async def test_fetch_linkedin_posts_returns_texts():
    """_fetch_linkedin_posts extracts text content from UGC posts."""
    from backend.agents.social_voice_agent import _fetch_linkedin_posts

    me_json = {"id": "user-123"}
    posts_json = {
        "elements": [
            {
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": "Great post about leadership"},
                    }
                }
            },
            {
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": "Another insightful post"},
                    }
                }
            },
            # Element without text should be skipped
            {"specificContent": {}},
        ]
    }

    mock_me_response = MagicMock()
    mock_me_response.json.return_value = me_json
    mock_me_response.raise_for_status = MagicMock()

    mock_posts_response = MagicMock()
    mock_posts_response.json.return_value = posts_json
    mock_posts_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.side_effect = [mock_me_response, mock_posts_response]

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _fetch_linkedin_posts("fake-token", limit=50)

    assert len(result) == 2
    assert result[0]["text"] == "Great post about leadership"
    assert result[1]["text"] == "Another insightful post"


@pytest.mark.asyncio
async def test_fetch_linkedin_posts_raises_when_no_person_id():
    """_fetch_linkedin_posts raises ValueError when person ID not returned."""
    from backend.agents.social_voice_agent import _fetch_linkedin_posts

    mock_me_response = MagicMock()
    mock_me_response.json.return_value = {}  # no 'id' field
    mock_me_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_me_response

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="LinkedIn person ID"):
            await _fetch_linkedin_posts("fake-token")


@pytest.mark.asyncio
async def test_fetch_instagram_posts_returns_captions():
    """_fetch_instagram_posts returns captions from media items."""
    from backend.agents.social_voice_agent import _fetch_instagram_posts

    me_json = {"id": "ig-user-123", "username": "testuser"}
    media_json = {
        "data": [
            {"id": "post1", "caption": "Loving the new launch!", "media_type": "IMAGE"},
            {"id": "post2", "caption": "Behind the scenes today", "media_type": "VIDEO"},
            {"id": "post3", "media_type": "IMAGE"},  # no caption, should be skipped
        ]
    }

    mock_me_response = MagicMock()
    mock_me_response.json.return_value = me_json
    mock_me_response.raise_for_status = MagicMock()

    mock_media_response = MagicMock()
    mock_media_response.json.return_value = media_json
    mock_media_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.side_effect = [mock_me_response, mock_media_response]

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _fetch_instagram_posts("fake-token")

    assert len(result) == 2
    assert result[0]["text"] == "Loving the new launch!"


@pytest.mark.asyncio
async def test_fetch_instagram_posts_raises_when_no_user_id():
    """_fetch_instagram_posts raises ValueError when user ID not returned."""
    from backend.agents.social_voice_agent import _fetch_instagram_posts

    mock_me_response = MagicMock()
    mock_me_response.json.return_value = {}
    mock_me_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_me_response

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="Instagram user ID"):
            await _fetch_instagram_posts("fake-token")


@pytest.mark.asyncio
async def test_fetch_x_posts_returns_tweets():
    """_fetch_x_posts returns tweet texts from timeline."""
    from backend.agents.social_voice_agent import _fetch_x_posts

    me_json = {"data": {"id": "x-user-123"}}
    tweets_json = {
        "data": [
            {"text": "First tweet about tech", "created_at": "2024-01-01"},
            {"text": "Second tweet about AI", "created_at": "2024-01-02"},
            {"created_at": "2024-01-03"},  # no text, should be skipped
        ]
    }

    mock_me_response = MagicMock()
    mock_me_response.json.return_value = me_json
    mock_me_response.raise_for_status = MagicMock()

    mock_tweets_response = MagicMock()
    mock_tweets_response.json.return_value = tweets_json
    mock_tweets_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.side_effect = [mock_me_response, mock_tweets_response]

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _fetch_x_posts("fake-token")

    assert len(result) == 2
    assert result[0]["text"] == "First tweet about tech"


@pytest.mark.asyncio
async def test_fetch_x_posts_raises_when_no_user_id():
    """_fetch_x_posts raises ValueError when user ID not in response."""
    from backend.agents.social_voice_agent import _fetch_x_posts

    mock_me_response = MagicMock()
    mock_me_response.json.return_value = {"data": {}}
    mock_me_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_me_response

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="X user ID"):
            await _fetch_x_posts("fake-token")


@pytest.mark.asyncio
async def test_analyze_social_voice_returns_profile():
    """_analyze_social_voice returns parsed profile dict when Gemini returns valid JSON."""
    from backend.agents.social_voice_agent import _analyze_social_voice

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(
        return_value=_make_text_response(VALID_VOICE_JSON)
    )

    with patch("backend.agents.social_voice_agent.get_genai_client", return_value=mock_client):
        posts = [{"text": "Post one content."}, {"text": "Post two content."}]
        result = await _analyze_social_voice(posts)

    assert isinstance(result, dict)
    assert "voice_characteristics" in result
    assert "tone_adjectives" in result
    assert result["emoji_usage"] == "minimal"


@pytest.mark.asyncio
async def test_analyze_social_voice_handles_malformed_json():
    """_analyze_social_voice raises ValueError when Gemini returns malformed JSON."""
    from backend.agents.social_voice_agent import _analyze_social_voice

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(
        return_value=_make_text_response("not valid json at all {{")
    )

    with patch("backend.agents.social_voice_agent.get_genai_client", return_value=mock_client):
        posts = [{"text": "Some post text."}]
        with pytest.raises(ValueError, match="Voice analysis returned an unexpected response"):
            await _analyze_social_voice(posts)


@pytest.mark.asyncio
async def test_analyze_social_voice_strips_markdown_fences():
    """_analyze_social_voice correctly strips markdown code fences from response."""
    from backend.agents.social_voice_agent import _analyze_social_voice

    fenced = f"```json\n{VALID_VOICE_JSON}\n```"
    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=_make_text_response(fenced))

    with patch("backend.agents.social_voice_agent.get_genai_client", return_value=mock_client):
        posts = [{"text": "Some post content."}]
        result = await _analyze_social_voice(posts)

    assert isinstance(result, dict)
    assert "voice_characteristics" in result


@pytest.mark.asyncio
async def test_analyze_social_voice_empty_text_response():
    """_analyze_social_voice raises ValueError when response.text is empty string."""
    from backend.agents.social_voice_agent import _analyze_social_voice

    mock_response = MagicMock()
    mock_response.text = ""
    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)

    with patch("backend.agents.social_voice_agent.get_genai_client", return_value=mock_client):
        posts = [{"text": "Hello world."}]
        with pytest.raises(ValueError):
            await _analyze_social_voice(posts)


@pytest.mark.asyncio
async def test_connect_platform_unsupported_platform():
    """connect_platform raises ValueError for unsupported platform names."""
    from backend.agents.social_voice_agent import connect_platform

    with pytest.raises(ValueError, match="Unsupported platform"):
        await connect_platform("tiktok", "some-token")


@pytest.mark.asyncio
async def test_connect_platform_no_posts_raises():
    """connect_platform raises ValueError when no posts are found."""
    from backend.agents.social_voice_agent import connect_platform

    async def mock_fetch(token, limit=50):
        return []

    with patch("backend.agents.social_voice_agent._FETCH_FNS", {"instagram": mock_fetch}):
        with pytest.raises(ValueError, match="No posts found"):
            await connect_platform("instagram", "valid-token")


# ---------------------------------------------------------------------------
# connect_platform — HTTP error handling (lines 22-125)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_platform_timeout_raises_value_error():
    """connect_platform wraps TimeoutException in ValueError."""
    import httpx

    from backend.agents.social_voice_agent import connect_platform

    async def mock_fetch_timeout(token, limit=50):
        raise httpx.TimeoutException("timed out")

    with patch("backend.agents.social_voice_agent._FETCH_FNS", {"linkedin": mock_fetch_timeout}):
        with pytest.raises(ValueError, match="timed out"):
            await connect_platform("linkedin", "some-token")


@pytest.mark.asyncio
async def test_connect_platform_401_raises_value_error():
    """connect_platform raises ValueError for 401 Unauthorized."""
    import httpx

    from backend.agents.social_voice_agent import connect_platform

    def _make_401():
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 401
        return resp

    async def mock_fetch_401(token, limit=50):
        raise httpx.HTTPStatusError("unauthorized", request=MagicMock(), response=_make_401())

    with patch("backend.agents.social_voice_agent._FETCH_FNS", {"x": mock_fetch_401}):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await connect_platform("x", "bad-token")


@pytest.mark.asyncio
async def test_connect_platform_403_raises_value_error():
    """connect_platform raises ValueError for 403 Forbidden."""
    import httpx

    from backend.agents.social_voice_agent import connect_platform

    def _make_403():
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 403
        return resp

    async def mock_fetch_403(token, limit=50):
        raise httpx.HTTPStatusError("forbidden", request=MagicMock(), response=_make_403())

    with patch("backend.agents.social_voice_agent._FETCH_FNS", {"instagram": mock_fetch_403}):
        with pytest.raises(ValueError, match="Insufficient permissions"):
            await connect_platform("instagram", "limited-token")


@pytest.mark.asyncio
async def test_connect_platform_429_raises_value_error():
    """connect_platform raises ValueError for 429 rate limit."""
    import httpx

    from backend.agents.social_voice_agent import connect_platform

    def _make_429():
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 429
        return resp

    async def mock_fetch_429(token, limit=50):
        raise httpx.HTTPStatusError("rate limited", request=MagicMock(), response=_make_429())

    with patch("backend.agents.social_voice_agent._FETCH_FNS", {"linkedin": mock_fetch_429}):
        with pytest.raises(ValueError, match="rate limit"):
            await connect_platform("linkedin", "some-token")


@pytest.mark.asyncio
async def test_connect_platform_500_re_raises_http_error():
    """connect_platform re-raises unexpected HTTPStatusError (e.g., 500)."""
    import httpx

    from backend.agents.social_voice_agent import connect_platform

    def _make_500():
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 500
        return resp

    async def mock_fetch_500(token, limit=50):
        raise httpx.HTTPStatusError("server error", request=MagicMock(), response=_make_500())

    with patch("backend.agents.social_voice_agent._FETCH_FNS", {"x": mock_fetch_500}):
        with pytest.raises(httpx.HTTPStatusError):
            await connect_platform("x", "some-token")


@pytest.mark.asyncio
async def test_connect_platform_success_returns_voice_analysis():
    """connect_platform with valid posts + valid Gemini response returns analysis dict."""
    from backend.agents.social_voice_agent import connect_platform

    async def mock_fetch_ok(token, limit=50):
        return [{"text": "Post one content."}, {"text": "Post two content."}]

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(
        return_value=_make_text_response(VALID_VOICE_JSON)
    )

    with (
        patch("backend.agents.social_voice_agent._FETCH_FNS", {"instagram": mock_fetch_ok}),
        patch("backend.agents.social_voice_agent.get_genai_client", return_value=mock_client),
    ):
        result = await connect_platform("instagram", "valid-token")

    assert isinstance(result, dict)
    assert "voice_characteristics" in result
