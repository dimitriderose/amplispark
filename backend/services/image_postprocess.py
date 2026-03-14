"""Image post-processing: resize, text overlay, platform-specific treatments.

Uses Pillow for all pixel-level operations. No AI calls — pure transforms.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

# ── Pixel dimensions for each aspect ratio ────────────────────────────────────

ASPECT_TO_PIXELS: dict[str, tuple[int, int]] = {
    "1:1":    (1080, 1080),
    "4:5":    (1080, 1350),
    "1.91:1": (1200, 628),
    "9:16":   (1080, 1920),
    "16:9":   (1920, 1080),
    "2:3":    (1000, 1500),
}

# ── Font loading ──────────────────────────────────────────────────────────────

_FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _get_font(bold: bool = False, size: int = 72) -> ImageFont.FreeTypeFont:
    """Load Inter font, cached. Falls back to default if file missing."""
    key = ("bold" if bold else "regular", size)
    if key not in _FONT_CACHE:
        fname = "Inter-Bold.ttf" if bold else "Inter-Regular.ttf"
        font_path = _FONT_DIR / fname
        try:
            _FONT_CACHE[key] = ImageFont.truetype(str(font_path), size)
        except (OSError, IOError):
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def _scale_font_size(base_size: int, canvas_width: int) -> int:
    """Scale font size relative to 1080px reference width."""
    return max(16, int(base_size * canvas_width / 1080))


# ── Color utilities ───────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#RRGGBB' to (R, G, B). Returns white on parse failure."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    try:
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def _srgb_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.1 relative luminance with sRGB linearization."""
    def _lin(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])


def _contrast_ratio(l1: float, l2: float) -> float:
    """WCAG contrast ratio between two relative luminance values."""
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _text_color_for_bg(brand_colors: list[str]) -> tuple[int, int, int]:
    """Auto-select white or dark text for WCAG 4.5:1 contrast ratio."""
    if brand_colors:
        bg_lum = _srgb_luminance(_hex_to_rgb(brand_colors[0]))
        white_contrast = _contrast_ratio(1.0, bg_lum)
        dark_contrast = _contrast_ratio(bg_lum, _srgb_luminance((30, 30, 30)))
        if dark_contrast > white_contrast:
            return (30, 30, 30)
    return (255, 255, 255)


def _gradient_color(brand_colors: list[str]) -> tuple[int, int, int]:
    """Get gradient base color from brand colors, default to dark."""
    if brand_colors:
        rgb = _hex_to_rgb(brand_colors[0])
        # Subtle brand tint instead of pure dark
        return (max(0, rgb[0] // 4), max(0, rgb[1] // 4), max(0, rgb[2] // 4))
    return (20, 20, 20)


# ── Core functions ────────────────────────────────────────────────────────────

def resize_to_aspect(image_bytes: bytes, aspect_ratio: str) -> bytes:
    """Resize image to exact pixel dimensions for the given aspect ratio.

    Uses center-crop + LANCZOS resampling for best quality.
    """
    dims = ASPECT_TO_PIXELS.get(aspect_ratio)
    if not dims:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.fit(img, dims, method=Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    shadow_offset: int = 2,
) -> None:
    """Draw text with a drop shadow for readability."""
    x, y = position
    # Shadow renders as solid black on RGB canvas (alpha ignored) — standard text shadow
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def _add_gradient_overlay(
    img: Image.Image,
    color: tuple[int, int, int],
    opacity: int = 160,
    region: str = "full",
) -> Image.Image:
    """Add a semi-transparent gradient overlay to the image.

    region: "full" = entire image, "bottom" = bottom 40%, "center" = middle 60%
    """
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size

    if region == "bottom":
        start_y = int(h * 0.6)
        for y in range(start_y, h):
            progress = (y - start_y) / (h - start_y)
            alpha = int(opacity * progress)
            draw.line([(0, y), (w, y)], fill=(*color, alpha))
    elif region == "center":
        center_y = h // 2
        band = int(h * 0.3)
        for y in range(center_y - band, center_y + band):
            dist = abs(y - center_y) / band
            alpha = int(opacity * (1 - dist * 0.5))
            draw.line([(0, y), (w, y)], fill=(*color, alpha))
    else:  # full
        for y in range(h):
            alpha = int(opacity * 0.7)
            draw.line([(0, y), (w, y)], fill=(*color, alpha))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)
    return lines or [text]


# ── Platform-specific overlay functions ───────────────────────────────────────

def create_carousel_cover(
    image_bytes: bytes,
    title: str,
    brand_colors: list[str],
    aspect_ratio: str = "4:5",
) -> bytes:
    """Add title overlay to carousel cover image."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    grad_color = _gradient_color(brand_colors)
    img = _add_gradient_overlay(img, grad_color, opacity=180, region="bottom")

    draw = ImageDraw.Draw(img)
    text_fill = _text_color_for_bg(brand_colors)
    font_size = _scale_font_size(64, w)
    font = _get_font(bold=True, size=font_size)
    max_text_w = int(w * 0.85)

    lines = _wrap_text(title[:120], font, max_text_w)
    line_height = font_size + 8
    total_text_h = len(lines) * line_height
    # Position text in bottom 35%
    start_y = int(h * 0.65) + (int(h * 0.3) - total_text_h) // 2

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = start_y + i * line_height
        _draw_text_with_shadow(draw, (x, y), line, font, text_fill)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_carousel_slide(
    image_bytes: bytes,
    title: str,
    brand_colors: list[str],
    aspect_ratio: str = "4:5",
) -> bytes:
    """Add title overlay to carousel slide (no badge — Instagram shows native counter)."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    grad_color = _gradient_color(brand_colors)
    img = _add_gradient_overlay(img, grad_color, opacity=160, region="bottom")

    draw = ImageDraw.Draw(img)
    text_fill = _text_color_for_bg(brand_colors)

    # Title at bottom — max 2 lines to keep overlay clean
    font_size = _scale_font_size(48, w)
    font = _get_font(bold=True, size=font_size)
    max_text_w = int(w * 0.85)
    lines = _wrap_text(title[:80], font, max_text_w)
    if len(lines) > 2:
        # Re-wrap with a shorter title to fit in 2 lines
        shorter = title[:50]
        last_space = shorter.rfind(' ')
        if last_space > 0:
            shorter = shorter[:last_space] + '…'
        lines = _wrap_text(shorter, font, max_text_w)[:2]
    line_height = int(font_size * 1.3)  # 130% leading for readability
    total_h = len(lines) * line_height
    start_y = h - int(h * 0.18) - total_h

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = start_y + i * line_height
        _draw_text_with_shadow(draw, (x, y), line, font, text_fill, shadow_offset=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_pinterest_pin(
    image_bytes: bytes,
    title: str,
    subtitle: str,
    brand_colors: list[str],
) -> bytes:
    """Pinterest-specific: full-image gradient + large centered title + subtitle."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    grad_color = _gradient_color(brand_colors)
    # Full-image overlay for Pinterest (not just bottom)
    img = _add_gradient_overlay(img, grad_color, opacity=140, region="full")

    draw = ImageDraw.Draw(img)
    text_fill = _text_color_for_bg(brand_colors)
    max_text_w = int(w * 0.85)

    # Large title — centered vertically in bottom 50%
    title_size = _scale_font_size(72, w)
    title_font = _get_font(bold=True, size=title_size)
    title_lines = _wrap_text(title[:100], title_font, max_text_w)
    title_line_h = title_size + 10

    # Subtitle below title
    sub_size = _scale_font_size(36, w)
    sub_font = _get_font(bold=False, size=sub_size)
    sub_lines = _wrap_text(subtitle[:80], sub_font, max_text_w) if subtitle else []
    sub_line_h = sub_size + 6

    total_h = len(title_lines) * title_line_h + len(sub_lines) * sub_line_h + 20
    start_y = int(h * 0.5) + (int(h * 0.4) - total_h) // 2

    for i, line in enumerate(title_lines):
        bbox = title_font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = start_y + i * title_line_h
        _draw_text_with_shadow(draw, (x, y), line, title_font, text_fill, shadow_offset=3)

    sub_start_y = start_y + len(title_lines) * title_line_h + 20
    for i, line in enumerate(sub_lines):
        bbox = sub_font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = sub_start_y + i * sub_line_h
        _draw_text_with_shadow(draw, (x, y), line, sub_font, text_fill)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_tiktok_cover(
    image_bytes: bytes,
    hook_text: str,
    brand_colors: list[str],
) -> bytes:
    """TikTok/YouTube Shorts: bold hook text in center safe zone (avoid top/bottom 20%)."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    grad_color = _gradient_color(brand_colors)
    img = _add_gradient_overlay(img, grad_color, opacity=140, region="center")

    draw = ImageDraw.Draw(img)
    text_fill = _text_color_for_bg(brand_colors)
    max_text_w = int(w * 0.8)

    font_size = _scale_font_size(64, w)
    font = _get_font(bold=True, size=font_size)
    lines = _wrap_text(hook_text[:100], font, max_text_w)
    line_height = font_size + 10
    total_h = len(lines) * line_height

    # Center in safe zone (20%-80% of height)
    safe_top = int(h * 0.2)
    safe_bottom = int(h * 0.8)
    safe_center = (safe_top + safe_bottom) // 2
    start_y = safe_center - total_h // 2

    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = start_y + i * line_height
        _draw_text_with_shadow(draw, (x, y), line, font, text_fill, shadow_offset=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
