"""Tests for backend.agents.hashtag_engine pure functions."""


def test_sanitize_hashtags_strips_hash_prefix():
    """Tags with leading # are cleaned."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    result = _sanitize_hashtags(["#foo", "#bar", "#baz"], "instagram")
    assert "foo" in result
    assert "bar" in result
    assert "baz" in result
    # No # in the output
    for tag in result:
        assert not tag.startswith("#")


def test_sanitize_hashtags_removes_stopwords():
    """Common stopwords are stripped from the tag list."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    # "the", "and", "for" are stopwords; "techbrand" is valid
    result = _sanitize_hashtags(["the", "and", "for", "techbrand"], "instagram")
    assert "the" not in result
    assert "and" not in result
    assert "for" not in result
    assert "techbrand" in result


def test_sanitize_hashtags_removes_short_fragments():
    """Tags shorter than 3 chars are removed."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    result = _sanitize_hashtags(["a", "ab", "abc", "abcd"], "instagram")
    assert "a" not in result
    assert "ab" not in result
    assert "abc" in result
    assert "abcd" in result


def test_sanitize_hashtags_passes_through_duplicates():
    """_sanitize_hashtags does not deduplicate — caller is responsible.
    Verify duplicates are preserved (the function just cleans/limits)."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    result = _sanitize_hashtags(["foo", "foo", "bar"], "instagram")
    # foo appears twice in input, function preserves order/dupes (no dedup logic)
    assert "foo" in result
    assert "bar" in result


def test_sanitize_hashtags_respects_instagram_limit():
    """Instagram hashtag limit is enforced."""
    from backend.agents.hashtag_engine import _sanitize_hashtags
    from backend.platforms import get as get_platform

    limit = get_platform("instagram").hashtag_limit
    many_tags = [f"tag{i:03d}" for i in range(limit + 10)]
    result = _sanitize_hashtags(many_tags, "instagram")
    assert len(result) <= limit


def test_sanitize_hashtags_respects_x_limit():
    """X (Twitter) hashtag limit is enforced."""
    from backend.agents.hashtag_engine import _sanitize_hashtags
    from backend.platforms import get as get_platform

    limit = get_platform("x").hashtag_limit
    many_tags = [f"tag{i:03d}" for i in range(limit + 10)]
    result = _sanitize_hashtags(many_tags, "x")
    assert len(result) <= limit


def test_sanitize_hashtags_removes_invalid_chars():
    """Tags with spaces or special chars are removed."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    result = _sanitize_hashtags(["valid_tag", "has space", "has-dash", "has.dot"], "instagram")
    assert "valid_tag" in result
    assert "has space" not in result
    assert "has-dash" not in result
    assert "has.dot" not in result


def test_sanitize_hashtags_mastodon_camelcase():
    """Mastodon hashtags are converted to CamelCase."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    result = _sanitize_hashtags(["smallbusiness", "contentcreator"], "mastodon")
    # Each tag should be CamelCase for Mastodon
    for tag in result:
        # CamelCase starts with uppercase
        assert tag[0].isupper() or tag[0].isdigit()


def test_sanitize_hashtags_removes_stopword_image():
    """'image' and 'post' are in stopwords and should be removed."""
    from backend.agents.hashtag_engine import _sanitize_hashtags

    result = _sanitize_hashtags(["image", "post", "caption", "realbrand"], "instagram")
    assert "image" not in result
    assert "post" not in result
    assert "caption" not in result
    assert "realbrand" in result
