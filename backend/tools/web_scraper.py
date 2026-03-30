import httpx
from bs4 import BeautifulSoup
import re
from typing import Optional
from urllib.parse import urljoin

async def fetch_website(url: str) -> dict:
    """Fetch and parse a website for brand analysis.

    Returns title, description, text content, colors found, images, nav items,
    and logo_url (best-effort logo detection).
    """
    if not url.startswith(("http://", "https://")):
        return {
            "title": "", "description": "", "text_content": "Invalid URL scheme — only http/https allowed.",
            "colors_found": [], "images": [], "nav_items": [], "logo_url": None, "error": "Invalid URL scheme",
        }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; AmplisparkBot/1.0)"
            })
            response.raise_for_status()
    except Exception as e:
        return {
            "title": "", "description": "", "text_content": f"Could not fetch website: {e}",
            "colors_found": [], "images": [], "nav_items": [], "logo_url": None, "error": str(e)
        }

    # Parse with full HTML (before decomposing header/nav) for logo detection
    full_soup = BeautifulSoup(response.text, "html.parser")
    logo_url = _extract_logo_url(full_soup, url)

    # Now remove noise for text extraction
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)[:5000]

    # Extract CSS colors
    colors = extract_css_colors(response.text)

    # Extract image alt texts
    images = [img.get("alt", "") for img in soup.find_all("img") if img.get("alt")]

    # Extract navigation links
    nav_items = [a.get_text(strip=True) for a in soup.find_all("a") if a.get_text(strip=True)][:20]

    meta_desc = soup.find("meta", {"name": "description"})
    description = meta_desc.get("content", "") if meta_desc else ""

    return {
        "title": soup.title.string.strip() if soup.title else "",
        "description": description,
        "text_content": text,
        "colors_found": colors[:15],
        "images": images[:20],
        "nav_items": nav_items,
        "logo_url": logo_url,
    }


def _extract_logo_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Best-effort logo detection from HTML.

    Checks (in priority order):
    1. <img> with class/id/alt containing 'logo'
    2. <link rel="icon"> or <link rel="apple-touch-icon"> (high-res favicon)
    3. Open Graph image (<meta property="og:image">)
    """
    # 1. <img> tags with logo in class, id, or alt
    for img in soup.find_all("img", src=True):
        attrs_text = " ".join([
            " ".join(img.get("class", [])),
            img.get("id", ""),
            img.get("alt", ""),
            img.get("src", ""),
        ]).lower()
        if "logo" in attrs_text:
            src = img["src"]
            if src and not src.startswith("data:"):
                return urljoin(base_url, src)

    # 2. Apple touch icon (usually high-res, good logo stand-in)
    for link in soup.find_all("link", rel=True):
        rels = [r.lower() for r in link.get("rel", [])]
        if "apple-touch-icon" in rels and link.get("href"):
            return urljoin(base_url, link["href"])

    # 3. Open Graph image
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        return urljoin(base_url, og_img["content"])

    return None


def extract_css_colors(html: str) -> list[str]:
    """Extract hex colors and rgb values from HTML/CSS."""
    hex_pattern = r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b"
    rgb_pattern = r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)"

    hex_colors = re.findall(hex_pattern, html)
    hex_colors = [f"#{c}" if len(c) == 6 else f"#{c[0]*2}{c[1]*2}{c[2]*2}" for c in hex_colors]

    rgb_colors = re.findall(rgb_pattern, html)
    rgb_hex = [f"#{int(r):02x}{int(g):02x}{int(b):02x}" for r, g, b in rgb_colors]

    # Combine, deduplicate, filter out very common colors
    common = {"#ffffff", "#000000", "#fff", "#000", "#ffffffff"}
    all_colors = list(dict.fromkeys(hex_colors + rgb_hex))
    return [c for c in all_colors if c.lower() not in common][:15]
