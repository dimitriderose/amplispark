import io

from PIL import Image


def _make_png(width: int = 100, height: int = 100, color: tuple = (255, 0, 0)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_100x100 = _make_png()
PNG_1080x1080 = _make_png(1080, 1080)


class TestResizeToAspect:
    def test_resize_1x1_produces_1080x1080(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "1:1")
        img = Image.open(io.BytesIO(result))
        assert img.size == (1080, 1080)

    def test_resize_9x16_produces_1080x1920(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "9:16")
        img = Image.open(io.BytesIO(result))
        assert img.size == (1080, 1920)

    def test_resize_16x9_produces_1920x1080(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "16:9")
        img = Image.open(io.BytesIO(result))
        assert img.size == (1920, 1080)

    def test_resize_2x3_produces_1000x1500(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "2:3")
        img = Image.open(io.BytesIO(result))
        assert img.size == (1000, 1500)

    def test_resize_unknown_ratio_returns_original_bytes(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "99:1")
        assert result == PNG_100x100

    def test_resize_4x5_produces_1080x1350(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "4:5")
        img = Image.open(io.BytesIO(result))
        assert img.size == (1080, 1350)

    def test_resize_output_is_png(self):
        from backend.services.image_postprocess import resize_to_aspect

        result = resize_to_aspect(PNG_100x100, "1:1")
        assert result[:4] == b"\x89PNG"


class TestHexToRgb:
    def test_valid_hex_with_hash_converts(self):
        from backend.services.image_postprocess import _hex_to_rgb

        assert _hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_valid_hex_without_hash_converts(self):
        from backend.services.image_postprocess import _hex_to_rgb

        assert _hex_to_rgb("00FF00") == (0, 255, 0)

    def test_invalid_chars_return_white(self):
        from backend.services.image_postprocess import _hex_to_rgb

        assert _hex_to_rgb("#GGGGGG") == (255, 255, 255)

    def test_wrong_length_returns_white(self):
        from backend.services.image_postprocess import _hex_to_rgb

        assert _hex_to_rgb("#FFF") == (255, 255, 255)

    def test_black_converts(self):
        from backend.services.image_postprocess import _hex_to_rgb

        assert _hex_to_rgb("#000000") == (0, 0, 0)

    def test_empty_string_returns_white(self):
        from backend.services.image_postprocess import _hex_to_rgb

        assert _hex_to_rgb("") == (255, 255, 255)


class TestSrgbLuminance:
    def test_white_luminance_is_approximately_one(self):
        from backend.services.image_postprocess import _srgb_luminance

        assert abs(_srgb_luminance((255, 255, 255)) - 1.0) < 0.001

    def test_black_luminance_is_zero(self):
        from backend.services.image_postprocess import _srgb_luminance

        assert _srgb_luminance((0, 0, 0)) == 0.0

    def test_red_luminance_matches_wcag_formula(self):
        from backend.services.image_postprocess import _srgb_luminance

        lum = _srgb_luminance((255, 0, 0))
        assert 0.2 < lum < 0.22


class TestContrastRatio:
    def test_white_on_black_contrast_is_21(self):
        from backend.services.image_postprocess import _contrast_ratio

        assert abs(_contrast_ratio(1.0, 0.0) - 21.0) < 0.01

    def test_same_luminance_contrast_is_one(self):
        from backend.services.image_postprocess import _contrast_ratio

        assert abs(_contrast_ratio(0.5, 0.5) - 1.0) < 0.001

    def test_order_independent(self):
        from backend.services.image_postprocess import _contrast_ratio

        assert _contrast_ratio(0.8, 0.2) == _contrast_ratio(0.2, 0.8)


class TestTextColorForBg:
    def test_dark_bg_returns_white_text(self):
        from backend.services.image_postprocess import _text_color_for_bg

        assert _text_color_for_bg(["#000000"]) == (255, 255, 255)

    def test_light_bg_returns_dark_text(self):
        from backend.services.image_postprocess import _text_color_for_bg

        assert _text_color_for_bg(["#FFFFFF"]) == (30, 30, 30)

    def test_empty_colors_returns_white(self):
        from backend.services.image_postprocess import _text_color_for_bg

        assert _text_color_for_bg([]) == (255, 255, 255)


class TestScaleFontSize:
    def test_scales_proportionally_at_reference_width(self):
        from backend.services.image_postprocess import _scale_font_size

        assert _scale_font_size(64, 1080) == 64

    def test_minimum_size_is_16(self):
        from backend.services.image_postprocess import _scale_font_size

        assert _scale_font_size(64, 10) >= 16

    def test_larger_canvas_scales_up(self):
        from backend.services.image_postprocess import _scale_font_size

        result = _scale_font_size(64, 2160)
        assert result == 128


class TestWrapText:
    def test_short_text_stays_on_one_line(self):
        from backend.services.image_postprocess import _get_font, _wrap_text

        font = _get_font(bold=False, size=24)
        lines = _wrap_text("Hello", font, 500)
        assert len(lines) == 1

    def test_long_text_wraps_into_multiple_lines(self):
        from backend.services.image_postprocess import _get_font, _wrap_text

        font = _get_font(bold=False, size=48)
        long_text = "word " * 30
        lines = _wrap_text(long_text, font, 400)
        assert len(lines) > 1

    def test_empty_text_returns_list_with_empty_string(self):
        from backend.services.image_postprocess import _get_font, _wrap_text

        font = _get_font(bold=False, size=24)
        lines = _wrap_text("", font, 500)
        assert lines == [""]


class TestCreateCarouselCover:
    def test_returns_png_bytes(self):
        from backend.services.image_postprocess import create_carousel_cover

        result = create_carousel_cover(PNG_100x100, "Test Title", ["#FF0000"])
        assert result[:4] == b"\x89PNG"

    def test_200_char_title_does_not_raise(self):
        from backend.services.image_postprocess import create_carousel_cover

        long_title = "A" * 200
        result = create_carousel_cover(PNG_100x100, long_title, ["#000000"])
        assert len(result) > 0

    def test_empty_brand_colors_does_not_raise(self):
        from backend.services.image_postprocess import create_carousel_cover

        result = create_carousel_cover(PNG_100x100, "Title", [])
        assert result[:4] == b"\x89PNG"


class TestCreateCarouselSlide:
    def test_returns_png_bytes(self):
        from backend.services.image_postprocess import create_carousel_slide

        result = create_carousel_slide(PNG_100x100, "Slide Title", ["#FF0000"])
        assert result[:4] == b"\x89PNG"

    def test_long_title_gets_truncated_gracefully(self):
        from backend.services.image_postprocess import create_carousel_slide

        result = create_carousel_slide(PNG_100x100, "T" * 200, ["#000000"])
        assert result[:4] == b"\x89PNG"


class TestCreatePinterestPin:
    def test_returns_png_bytes(self):
        from backend.services.image_postprocess import create_pinterest_pin

        result = create_pinterest_pin(PNG_100x100, "Pin Title", "Subtitle", ["#FF0000"])
        assert result[:4] == b"\x89PNG"

    def test_empty_subtitle_does_not_raise(self):
        from backend.services.image_postprocess import create_pinterest_pin

        result = create_pinterest_pin(PNG_100x100, "Title", "", ["#000000"])
        assert result[:4] == b"\x89PNG"


class TestCreateTiktokCover:
    def test_returns_png_bytes(self):
        from backend.services.image_postprocess import create_tiktok_cover

        result = create_tiktok_cover(PNG_100x100, "Hook text here", ["#FF0000"])
        assert result[:4] == b"\x89PNG"

    def test_empty_brand_colors_does_not_raise(self):
        from backend.services.image_postprocess import create_tiktok_cover

        result = create_tiktok_cover(PNG_100x100, "Hook", [])
        assert result[:4] == b"\x89PNG"


class TestAddGradientOverlay:
    def _make_rgb_image(self) -> Image.Image:
        return Image.new("RGB", (200, 200), (100, 150, 200))

    def test_full_overlay_returns_rgb_image(self):
        from backend.services.image_postprocess import _add_gradient_overlay

        img = self._make_rgb_image()
        result = _add_gradient_overlay(img, (20, 20, 20), opacity=160, region="full")
        assert result.mode == "RGB"

    def test_bottom_overlay_returns_rgb_image(self):
        from backend.services.image_postprocess import _add_gradient_overlay

        img = self._make_rgb_image()
        result = _add_gradient_overlay(img, (20, 20, 20), opacity=160, region="bottom")
        assert result.mode == "RGB"

    def test_center_overlay_returns_rgb_image(self):
        from backend.services.image_postprocess import _add_gradient_overlay

        img = self._make_rgb_image()
        result = _add_gradient_overlay(img, (20, 20, 20), opacity=160, region="center")
        assert result.mode == "RGB"

    def test_overlay_preserves_image_size(self):
        from backend.services.image_postprocess import _add_gradient_overlay

        img = self._make_rgb_image()
        result = _add_gradient_overlay(img, (20, 20, 20))
        assert result.size == img.size
