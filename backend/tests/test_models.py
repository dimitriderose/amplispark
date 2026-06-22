"""Tests for Pydantic models in backend/models/."""

from datetime import datetime

from backend.models.api import APIResponse, HealthResponse
from backend.models.plan import ContentPlan, ContentPlanCreate, DayBrief, Pillar
from backend.models.post import Post, ReviewCheck, ReviewResult, VideoJob

# ---------------------------------------------------------------------------
# backend/models/api.py
# ---------------------------------------------------------------------------


class TestAPIResponse:
    def test_default_success(self):
        r = APIResponse()
        assert r.success is True
        assert r.data is None
        assert r.error is None

    def test_success_with_data(self):
        r = APIResponse(success=True, data={"key": "value"})
        assert r.data == {"key": "value"}

    def test_error_response(self):
        r = APIResponse(success=False, error="Something went wrong")
        assert r.success is False
        assert r.error == "Something went wrong"

    def test_data_can_be_list(self):
        r = APIResponse(data=[1, 2, 3])
        assert r.data == [1, 2, 3]

    def test_data_can_be_string(self):
        r = APIResponse(data="hello")
        assert r.data == "hello"


class TestHealthResponse:
    def test_defaults(self):
        r = HealthResponse()
        assert r.status == "ok"
        assert r.service == "amplifi-backend"
        assert r.version == "1.0.0"

    def test_custom_values(self):
        r = HealthResponse(status="degraded", service="my-svc", version="2.0.0")
        assert r.status == "degraded"
        assert r.service == "my-svc"
        assert r.version == "2.0.0"


# ---------------------------------------------------------------------------
# backend/models/post.py
# ---------------------------------------------------------------------------


class TestReviewCheck:
    def test_instantiation(self):
        rc = ReviewCheck(score=8.5, feedback="Great post!")
        assert rc.score == 8.5
        assert rc.feedback == "Great post!"


class TestReviewResult:
    def test_minimal_instantiation(self):
        rr = ReviewResult(
            overall_score=7.0,
            approved=True,
            checks={"tone": {"score": 8, "feedback": "Good"}},
        )
        assert rr.overall_score == 7.0
        assert rr.approved is True
        assert rr.suggestions == []
        assert rr.reviewed_at is None

    def test_with_suggestions_and_timestamp(self):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        rr = ReviewResult(
            overall_score=5.0,
            approved=False,
            checks={},
            suggestions=["Add a stronger hook", "Shorten body"],
            reviewed_at=ts,
        )
        assert len(rr.suggestions) == 2
        assert rr.reviewed_at == ts


class TestPost:
    def test_minimal_instantiation(self):
        p = Post(
            post_id="post-001",
            plan_id="plan-001",
            brand_id="brand-001",
            day_index=0,
            platform="instagram",
        )
        assert p.post_id == "post-001"
        assert p.caption == ""
        assert p.image_urls == []
        assert p.hashtags == []
        assert p.status == "draft"
        assert p.image_source == "generated"
        assert p.review is None
        assert p.video_url is None
        assert p.publish_status is None
        assert p.created_at is None
        assert p.updated_at is None
        assert p.original_image_url is None
        assert p.edit_count == 0
        assert p.thumbnail_url is None

    def test_full_instantiation(self):
        ts = datetime(2024, 3, 15)
        p = Post(
            post_id="post-002",
            plan_id="plan-002",
            brand_id="brand-002",
            day_index=2,
            platform="linkedin",
            caption="A great caption",
            image_urls=["https://example.com/img.jpg"],
            hashtags=["marketing", "growth"],
            posting_time="9:00 AM",
            status="approved",
            image_source="user_upload",
            video_url="https://example.com/video.mp4",
            publish_status={"notion": {"status": "published"}},
            created_at=ts,
            updated_at=ts,
            original_image_url="https://example.com/orig.jpg",
            edit_count=3,
            thumbnail_url="https://example.com/thumb.jpg",
        )
        assert p.platform == "linkedin"
        assert p.caption == "A great caption"
        assert p.status == "approved"
        assert p.edit_count == 3
        assert p.thumbnail_url == "https://example.com/thumb.jpg"

    def test_post_with_review(self):
        review = ReviewResult(
            overall_score=8.0,
            approved=True,
            checks={"tone": {"score": 8, "feedback": "Great"}},
        )
        p = Post(
            post_id="post-003",
            plan_id="plan-003",
            brand_id="brand-003",
            day_index=1,
            platform="x",
            review=review,
        )
        assert p.review is not None
        assert p.review.overall_score == 8.0


class TestVideoJob:
    def test_minimal_instantiation(self):
        vj = VideoJob(job_id="job-001", post_id="post-001")
        assert vj.job_id == "job-001"
        assert vj.post_id == "post-001"
        assert vj.status == "queued"
        assert vj.tier == "fast"
        assert vj.result is None
        assert vj.error is None
        assert vj.created_at is None
        assert vj.updated_at is None

    def test_full_instantiation(self):
        ts = datetime(2024, 6, 1)
        vj = VideoJob(
            job_id="job-002",
            post_id="post-002",
            status="complete",
            tier="standard",
            result={"video_url": "https://example.com/v.mp4"},
            error=None,
            created_at=ts,
            updated_at=ts,
        )
        assert vj.status == "complete"
        assert vj.tier == "standard"
        assert vj.result["video_url"] == "https://example.com/v.mp4"

    def test_failed_job(self):
        vj = VideoJob(job_id="job-003", post_id="post-003", status="failed", error="Timeout")
        assert vj.status == "failed"
        assert vj.error == "Timeout"


# ---------------------------------------------------------------------------
# backend/models/plan.py
# ---------------------------------------------------------------------------


class TestPillar:
    def test_minimal_instantiation(self):
        p = Pillar(id="p1", theme="Education", key_message="Teach value")
        assert p.id == "p1"
        assert p.theme == "Education"
        assert p.key_message == "Teach value"
        assert p.source == "generated"
        assert p.derivative_count == 0

    def test_event_source(self):
        p = Pillar(id="p2", theme="Product Launch", key_message="New feature live", source="event")
        assert p.source == "event"

    def test_derivative_count(self):
        p = Pillar(id="p3", theme="Tips", key_message="Key tips", derivative_count=5)
        assert p.derivative_count == 5


class TestDayBrief:
    def test_minimal_instantiation(self):
        db = DayBrief(
            day_index=0,
            day_name="Monday",
            platform="instagram",
            theme="Growth tips",
            content_type="carousel",
            caption_direction="Show three actionable steps",
            image_direction="Flat lay desk setup",
            posting_time="6:00 PM",
        )
        assert db.day_index == 0
        assert db.platform == "instagram"
        assert db.generated is False
        assert db.status == "planned"
        assert db.pillar_id is None
        assert db.derivative_type is None
        assert db.image_source == "generated"

    def test_full_instantiation(self):
        db = DayBrief(
            day_index=3,
            day_name="Thursday",
            platform="linkedin",
            theme="B2B success",
            content_type="video",
            caption_direction="Tell the origin story",
            image_direction="Office environment",
            posting_time="9:00 AM",
            pillar_id="series_0",
            derivative_type="carousel",
            pillar_context="Education pillar",
            user_photo_url="https://example.com/photo.jpg",
            image_source="user_upload",
            generated=True,
            post_id="post-999",
            status="generated",
        )
        assert db.status == "generated"
        assert db.generated is True
        assert db.post_id == "post-999"
        assert db.image_source == "user_upload"


class TestContentPlanCreate:
    def test_minimal(self):
        cpc = ContentPlanCreate(brand_id="brand-001")
        assert cpc.brand_id == "brand-001"
        assert cpc.goals is None
        assert cpc.platforms == ["instagram"]
        assert cpc.business_events is None

    def test_full(self):
        cpc = ContentPlanCreate(
            brand_id="brand-002",
            goals="Drive leads",
            platforms=["instagram", "linkedin"],
            business_events="Product launch next week",
        )
        assert cpc.goals == "Drive leads"
        assert "linkedin" in cpc.platforms
        assert cpc.business_events == "Product launch next week"


class TestContentPlan:
    def test_minimal_instantiation(self):
        cp = ContentPlan(
            plan_id="plan-001",
            brand_id="brand-001",
            week_of="2024-W01",
        )
        assert cp.plan_id == "plan-001"
        assert cp.platforms == []
        assert cp.pillars == []
        assert cp.days == []
        assert cp.status == "draft"
        assert cp.created_at is None

    def test_with_days_and_pillars(self):
        pillar = Pillar(id="p1", theme="Education", key_message="Teach something")
        day = DayBrief(
            day_index=0,
            day_name="Monday",
            platform="instagram",
            theme="Tips",
            content_type="carousel",
            caption_direction="Top 3 tips",
            image_direction="Clean desk setup",
            posting_time="6:00 PM",
        )
        cp = ContentPlan(
            plan_id="plan-002",
            brand_id="brand-002",
            week_of="2024-W10",
            platforms=["instagram"],
            pillars=[pillar],
            days=[day],
            status="complete",
        )
        assert len(cp.pillars) == 1
        assert len(cp.days) == 1
        assert cp.status == "complete"
