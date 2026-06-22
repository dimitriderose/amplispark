"""Unit tests for backend/agents/video_repurpose_agent.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _validate_clip_spec tests (pure function)
# ---------------------------------------------------------------------------


def test_validate_clip_spec_valid():
    """Valid spec returns (start, end, platform) tuple."""
    from backend.agents.video_repurpose_agent import _validate_clip_spec

    spec = {"start_time": 5.0, "end_time": 25.0, "platform": "reels"}
    start, end, platform = _validate_clip_spec(spec, 0)
    assert start == 5.0
    assert end == 25.0
    assert platform == "reels"


def test_validate_clip_spec_negative_start_raises():
    """Negative start_time raises ValueError."""
    from backend.agents.video_repurpose_agent import _validate_clip_spec

    spec = {"start_time": -1.0, "end_time": 30.0, "platform": "reels"}
    with pytest.raises(ValueError, match="start_time must be >= 0"):
        _validate_clip_spec(spec, 0)


def test_validate_clip_spec_end_before_start_raises():
    """end_time <= start_time raises ValueError."""
    from backend.agents.video_repurpose_agent import _validate_clip_spec

    spec = {"start_time": 30.0, "end_time": 10.0, "platform": "reels"}
    with pytest.raises(ValueError, match="end_time must be > start_time"):
        _validate_clip_spec(spec, 0)


def test_validate_clip_spec_unknown_platform_defaults_to_reels():
    """Unknown platform is logged and defaults to 'reels'."""
    from backend.agents.video_repurpose_agent import _validate_clip_spec

    spec = {"start_time": 0.0, "end_time": 30.0, "platform": "snapchat"}
    _, _, platform = _validate_clip_spec(spec, 0)
    assert platform == "reels"


def test_validate_clip_spec_trims_overlength_clips():
    """Clips exceeding platform max duration are trimmed."""
    from backend.agents.video_repurpose_agent import _validate_clip_spec

    spec = {"start_time": 0.0, "end_time": 120.0, "platform": "reels"}  # max is 60
    start, end, platform = _validate_clip_spec(spec, 0)
    assert end - start <= 60


# ---------------------------------------------------------------------------
# _analyze_video tests (mocked Gemini)
# ---------------------------------------------------------------------------

VALID_CLIPS_JSON = json.dumps(
    [
        {
            "start_time": 0.0,
            "end_time": 30.0,
            "platform": "reels",
            "hook": "Opening hook moment",
            "suggested_caption": "Caption for clip 1",
            "reason": "High energy opening",
            "content_theme": "brand awareness",
        }
    ]
)


@pytest.mark.asyncio
async def test_analyze_video_returns_clip_list():
    """_analyze_video returns a list of clip dicts when Gemini responds with valid JSON."""
    from backend.agents.video_repurpose_agent import _analyze_video

    mock_response = MagicMock()
    mock_response.text = VALID_CLIPS_JSON

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)

    mock_video_file = MagicMock()
    brand = {"business_name": "Test Brand", "tone": "friendly", "industry": "tech"}

    result = await _analyze_video(mock_video_file, mock_client, brand)

    assert isinstance(result, list)
    assert len(result) >= 1
    assert "start_time" in result[0]
    assert "platform" in result[0]


@pytest.mark.asyncio
async def test_analyze_video_raises_on_malformed_json():
    """_analyze_video raises ValueError when Gemini returns malformed JSON."""
    from backend.agents.video_repurpose_agent import _analyze_video

    mock_response = MagicMock()
    mock_response.text = "this is not json"

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)

    mock_video_file = MagicMock()
    brand = {"business_name": "Test Brand"}

    with pytest.raises(ValueError, match="Could not parse Gemini clip analysis"):
        await _analyze_video(mock_video_file, mock_client, brand)


@pytest.mark.asyncio
async def test_analyze_video_raises_on_empty_list():
    """_analyze_video raises ValueError when Gemini returns an empty list."""
    from backend.agents.video_repurpose_agent import _analyze_video

    mock_response = MagicMock()
    mock_response.text = "[]"

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)

    brand = {"business_name": "Test Brand"}

    with pytest.raises(ValueError, match="no clip-worthy moments"):
        await _analyze_video(MagicMock(), mock_client, brand)


# ---------------------------------------------------------------------------
# analyze_and_repurpose integration test (fully mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_and_repurpose_returns_clips():
    """analyze_and_repurpose returns a list of clip dicts when all I/O is mocked."""
    from backend.agents.video_repurpose_agent import analyze_and_repurpose

    clip_specs = json.loads(VALID_CLIPS_JSON)

    mock_video_file = MagicMock()
    mock_video_file.name = "files/test-file-id"
    mock_video_file.state = MagicMock()
    mock_video_file.state.name = "ACTIVE"

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=MagicMock(text=VALID_CLIPS_JSON))
    mock_client.files.upload = MagicMock(return_value=mock_video_file)
    mock_client.files.get = MagicMock(return_value=mock_video_file)
    mock_client.files.delete = MagicMock()

    fake_clip_bytes = b"fake-mp4-bytes-content-here"

    with (
        patch(
            "backend.agents.video_repurpose_agent._upload_to_gemini_files",
            new_callable=AsyncMock,
            return_value=(mock_video_file, mock_client),
        ),
        patch(
            "backend.agents.video_repurpose_agent._analyze_video",
            new_callable=AsyncMock,
            return_value=clip_specs,
        ),
        patch(
            "backend.agents.video_repurpose_agent._extract_and_format_clip",
            return_value=None,
        ),
        patch(
            "builtins.open",
            create=True,
        ) as mock_open,
    ):
        # Make the file read return non-empty bytes
        mock_file_handle = MagicMock()
        mock_file_handle.__enter__ = MagicMock(return_value=mock_file_handle)
        mock_file_handle.__exit__ = MagicMock(return_value=False)
        mock_file_handle.read = MagicMock(return_value=fake_clip_bytes)
        mock_file_handle.write = MagicMock()
        mock_open.return_value = mock_file_handle

        brand = {"business_name": "Test Brand", "tone": "friendly", "industry": "tech"}
        result = await analyze_and_repurpose(b"fake-video-bytes", brand)

    assert isinstance(result, list)
    assert len(result) >= 1
    first = result[0]
    assert "platform" in first
    assert "clip_bytes" in first
    assert "filename" in first
