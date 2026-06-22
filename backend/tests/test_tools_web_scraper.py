"""Unit tests for backend/tools/web_scraper.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# fetch_website tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_website_returns_text():
    """fetch_website returns text_content containing HTML body text."""
    from backend.tools.web_scraper import fetch_website

    mock_response = MagicMock()
    mock_response.text = "<html><body><p>Hello World</p></body></html>"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://example.com")

    assert "Hello World" in result["text_content"]


@pytest.mark.asyncio
async def test_fetch_website_strips_scripts():
    """fetch_website removes <script> tags from text_content."""
    from backend.tools.web_scraper import fetch_website

    mock_response = MagicMock()
    mock_response.text = (
        "<html><body><p>Good content</p><script>evil(); var x = 1;</script></body></html>"
    )
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://example.com")

    assert "evil()" not in result["text_content"]
    assert "Good content" in result["text_content"]


@pytest.mark.asyncio
async def test_fetch_website_strips_styles():
    """fetch_website removes <style> tags from text_content."""
    from backend.tools.web_scraper import fetch_website

    mock_response = MagicMock()
    mock_response.text = (
        "<html><head><style>body { color: red; }</style></head>"
        "<body><p>Useful text</p></body></html>"
    )
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://example.com")

    assert "color: red" not in result["text_content"]
    assert "Useful text" in result["text_content"]


@pytest.mark.asyncio
async def test_fetch_website_handles_http_error():
    """fetch_website returns error dict when httpx raises an exception."""
    import httpx

    from backend.tools.web_scraper import fetch_website

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://unreachable.example.com")

    assert "error" in result
    assert result["text_content"].startswith("Could not fetch website")


@pytest.mark.asyncio
async def test_fetch_website_handles_timeout():
    """fetch_website returns error dict when httpx raises TimeoutException."""
    import httpx

    from backend.tools.web_scraper import fetch_website

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://slow.example.com")

    assert "error" in result


@pytest.mark.asyncio
async def test_fetch_website_truncates_long_content():
    """fetch_website truncates very long text content to 5000 chars."""
    from backend.tools.web_scraper import fetch_website

    long_paragraph = "word " * 2000  # ~10,000 chars
    mock_response = MagicMock()
    mock_response.text = f"<html><body><p>{long_paragraph}</p></body></html>"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://example.com")

    assert len(result["text_content"]) <= 5000


@pytest.mark.asyncio
async def test_fetch_website_invalid_scheme_returns_error():
    """fetch_website rejects non-http/https URLs without making a network call."""
    from backend.tools.web_scraper import fetch_website

    result = await fetch_website("ftp://example.com/resource")

    assert result["error"] == "Invalid URL scheme"
    assert "Invalid URL scheme" in result["text_content"]


@pytest.mark.asyncio
async def test_fetch_website_returns_colors_found():
    """fetch_website extracts CSS hex colors from the page."""
    from backend.tools.web_scraper import fetch_website

    html_with_colors = (
        "<html><head><style>body { color: #3a86ff; background: #ffffff; }</style></head>"
        "<body><p>Colorful</p></body></html>"
    )
    mock_response = MagicMock()
    mock_response.text = html_with_colors
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("backend.tools.web_scraper.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await fetch_website("https://example.com")

    # #3a86ff is not near-white or near-black, should appear
    assert "#3a86ff" in result["colors_found"]


# ---------------------------------------------------------------------------
# extract_css_colors unit tests (pure function)
# ---------------------------------------------------------------------------


def test_extract_css_colors_returns_hex_colors():
    """extract_css_colors returns a list of hex colors from HTML."""
    from backend.tools.web_scraper import extract_css_colors

    html = "color: #3a86ff; background: #ff6b6b;"
    result = extract_css_colors(html)
    assert "#3a86ff" in result
    assert "#ff6b6b" in result


def test_extract_css_colors_filters_white_and_black():
    """extract_css_colors removes near-white and near-black colors."""
    from backend.tools.web_scraper import extract_css_colors

    html = "color: #ffffff; color: #000000; color: #3a86ff;"
    result = extract_css_colors(html)
    assert "#ffffff" not in result
    assert "#000000" not in result
    assert "#3a86ff" in result


def test_extract_css_colors_handles_rgb():
    """extract_css_colors converts rgb() values to hex."""
    from backend.tools.web_scraper import extract_css_colors

    html = "color: rgb(58, 134, 255);"
    result = extract_css_colors(html)
    # rgb(58, 134, 255) → #3a86ff
    assert "#3a86ff" in result


def test_extract_css_colors_empty_html():
    """extract_css_colors returns empty list for HTML with no colors."""
    from backend.tools.web_scraper import extract_css_colors

    result = extract_css_colors("<html><body>No colors here</body></html>")
    assert result == []


# ---------------------------------------------------------------------------
# _extract_logo_url tests (pure function using BeautifulSoup)
# ---------------------------------------------------------------------------


def test_extract_logo_url_finds_img_with_logo_in_alt():
    """Returns URL for <img alt='company logo'> tag."""
    from bs4 import BeautifulSoup

    from backend.tools.web_scraper import _extract_logo_url

    html = '<html><body><img src="/img/logo.png" alt="Company Logo"></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_logo_url(soup, "https://example.com")
    assert result == "https://example.com/img/logo.png"


def test_extract_logo_url_finds_img_with_logo_in_class():
    """Returns URL for <img class='site-logo'>."""
    from bs4 import BeautifulSoup

    from backend.tools.web_scraper import _extract_logo_url

    html = '<html><body><img src="/img/brand.png" class="site-logo"></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_logo_url(soup, "https://example.com")
    assert result == "https://example.com/img/brand.png"


def test_extract_logo_url_skips_data_uri():
    """Skips data: URIs even if they have logo in class."""
    from bs4 import BeautifulSoup

    from backend.tools.web_scraper import _extract_logo_url

    html = '<html><body><img src="data:image/png;base64,abc" class="logo"></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_logo_url(soup, "https://example.com")
    assert result is None


def test_extract_logo_url_falls_back_to_apple_touch_icon():
    """Falls back to apple-touch-icon link when no logo img found."""
    from bs4 import BeautifulSoup

    from backend.tools.web_scraper import _extract_logo_url

    html = '<html><head><link rel="apple-touch-icon" href="/apple-icon.png"></head><body></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_logo_url(soup, "https://example.com")
    assert result == "https://example.com/apple-icon.png"


def test_extract_logo_url_falls_back_to_og_image():
    """Falls back to og:image when no logo img or apple-touch-icon."""
    from bs4 import BeautifulSoup

    from backend.tools.web_scraper import _extract_logo_url

    html = '<html><head><meta property="og:image" content="https://example.com/og.jpg"></head><body></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_logo_url(soup, "https://example.com")
    assert result == "https://example.com/og.jpg"


def test_extract_logo_url_returns_none_when_nothing_found():
    """Returns None when no logo indicators are present."""
    from bs4 import BeautifulSoup

    from backend.tools.web_scraper import _extract_logo_url

    html = "<html><body><p>No logo here.</p></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    result = _extract_logo_url(soup, "https://example.com")
    assert result is None
