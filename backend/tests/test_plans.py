"""Tests for backend.routers.plans."""

from unittest.mock import AsyncMock, patch

TEST_BRAND_ID = "test-brand-id-456"
TEST_PLAN_ID = "test-plan-id"
TEST_UID = "test-user-uid-123"

_PLANS_FC = "backend.routers.plans.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"


class TestListPlans:
    def test_returns_plans_for_brand(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_plans = AsyncMock(return_value=[sample_plan])
            response = client.get(f"/api/brands/{TEST_BRAND_ID}/plans", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert len(data["plans"]) == 1
        assert data["plans"][0]["plan_id"] == TEST_PLAN_ID

    def test_returns_empty_list_when_no_plans(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_plans = AsyncMock(return_value=[])
            response = client.get(f"/api/brands/{TEST_BRAND_ID}/plans", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["plans"] == []

    def test_calls_firestore_with_correct_brand_id(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_plans = AsyncMock(return_value=[])
            client.get(f"/api/brands/{TEST_BRAND_ID}/plans", headers=auth_headers)
            fc.list_plans.assert_called_once_with(TEST_BRAND_ID)

    def test_returns_403_when_brand_belongs_to_different_user(
        self, client, auth_headers, sample_brand
    ):
        other_brand = {**sample_brand, "owner_uid": "different-user-uid"}
        with patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=other_brand)
            response = client.get(f"/api/brands/{TEST_BRAND_ID}/plans", headers=auth_headers)
        assert response.status_code == 403

    def test_returns_404_when_brand_not_found(self, client, auth_headers):
        with patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=None)
            response = client.get("/api/brands/nonexistent-brand/plans", headers=auth_headers)
        assert response.status_code == 404


class TestGetPlan:
    def test_returns_plan_when_found(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}", headers=auth_headers
            )
        assert response.status_code == 200
        data = response.json()
        assert "plan_profile" in data
        assert data["plan_profile"]["plan_id"] == TEST_PLAN_ID

    def test_returns_404_when_plan_not_found(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/nonexistent-plan", headers=auth_headers
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_calls_firestore_with_plan_id_and_brand_id(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            client.get(f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}", headers=auth_headers)
            fc.get_plan.assert_called_once_with(TEST_PLAN_ID, TEST_BRAND_ID)


class TestCreatePlan:
    def test_creates_plan_with_defaults(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {"highlights": ["trend1"]})),
            ):
                response = client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={},
                )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == "new-plan-id"
        assert data["status"] == "complete"
        assert "days" in data
        assert "trend_summary" in data

    def test_creates_plan_with_custom_num_days(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={"num_days": 14},
                )
                assert mock_run.call_args.args[2] == 14

    def test_clamps_num_days_to_maximum_of_30(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={"num_days": 999},
                )
                assert mock_run.call_args.args[2] == 30

    def test_clamps_num_days_to_minimum_of_1(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={"num_days": 0},
                )
                assert mock_run.call_args.args[2] == 1

    def test_returns_404_when_brand_not_found_in_middleware(self, client, auth_headers):
        with patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                "/api/brands/nonexistent-brand/plans",
                headers=auth_headers,
                json={},
            )
        assert response.status_code == 404

    def test_returns_404_when_brand_not_found_in_router(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans",
                headers=auth_headers,
                json={},
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Brand not found"

    def test_returns_500_when_strategy_agent_raises(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(side_effect=RuntimeError("Agent exploded")),
            ):
                response = client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={},
                )
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_returns_500_when_firestore_create_raises(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(side_effect=Exception("Firestore down"))
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ):
                response = client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={},
                )
        assert response.status_code == 500

    def test_passes_business_events_to_strategy(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={"business_events": "Black Friday sale"},
                )
                assert mock_run.call_args.kwargs["business_events"] == "Black Friday sale"

    def test_passes_explicit_platforms_to_strategy(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={"platforms": ["instagram", "tiktok"]},
                )
                assert mock_run.call_args.kwargs["platforms"] == ["instagram", "tiktok"]

    def test_uses_stored_manual_platforms_when_no_explicit_platforms(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        brand_with_platforms = {
            **sample_brand,
            "platform_mode": "manual",
            "selected_platforms": ["linkedin", "twitter"],
        }
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_with_platforms)
            fc.get_brand = AsyncMock(return_value=brand_with_platforms)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={},
                )
                assert mock_run.call_args.kwargs["platforms"] == ["linkedin", "twitter"]

    def test_passes_none_platforms_in_ai_mode(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        brand_with_ai_mode = {
            **sample_brand,
            "platform_mode": "ai",
            "selected_platforms": ["instagram"],
        }
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand_with_ai_mode)
            fc.get_brand = AsyncMock(return_value=brand_with_ai_mode)
            fc.create_plan = AsyncMock(return_value="new-plan-id")
            with patch(
                "backend.routers.plans.run_strategy",
                new=AsyncMock(return_value=(sample_plan["days"], {})),
            ) as mock_run:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans",
                    headers=auth_headers,
                    json={},
                )
                assert mock_run.call_args.kwargs["platforms"] is None


class TestUpdatePlanDay:
    def test_updates_day_and_returns_updated_plan(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0",
                headers=auth_headers,
                json={"content_theme": "New Theme"},
            )
        assert response.status_code == 200
        assert "plan_profile" in response.json()

    def test_calls_update_plan_day_with_correct_args(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/2",
                headers=auth_headers,
                json={"content_theme": "Health", "platform": "tiktok"},
            )
            fc.update_plan_day.assert_called_once_with(
                TEST_BRAND_ID,
                TEST_PLAN_ID,
                2,
                {"content_theme": "Health", "platform": "tiktok"},
            )

    def test_returns_404_when_plan_not_found(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/nonexistent-plan/days/0",
                headers=auth_headers,
                json={"content_theme": "x"},
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_returns_400_when_day_index_out_of_range(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/99",
                headers=auth_headers,
                json={"content_theme": "x"},
            )
        assert response.status_code == 400
        assert "out of range" in response.json()["detail"]

    def test_returns_400_when_day_index_is_negative(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/-1",
                headers=auth_headers,
                json={"content_theme": "x"},
            )
        assert response.status_code == 400

    def test_excludes_protected_fields_from_update(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0",
                headers=auth_headers,
                json={
                    "content_theme": "Safe",
                    "day_index": 999,
                    "brand_id": "hacker",
                    "plan_id": "fake",
                },
            )
            call_args = fc.update_plan_day.call_args
            passed_data = call_args.args[3]
            assert "day_index" not in passed_data
            assert "brand_id" not in passed_data
            assert "plan_id" not in passed_data
            assert passed_data.get("content_theme") == "Safe"

    def test_returns_500_when_update_raises(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock(side_effect=Exception("DB error"))
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0",
                headers=auth_headers,
                json={"content_theme": "x"},
            )
        assert response.status_code == 500

    def test_omits_none_values_from_update_payload(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            client.put(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0",
                headers=auth_headers,
                json={"content_theme": "Theme", "platform": None},
            )
            call_args = fc.update_plan_day.call_args
            passed_data = call_args.args[3]
            assert "platform" not in passed_data
            assert passed_data["content_theme"] == "Theme"


class TestRefreshPlanResearch:
    def test_returns_updated_trend_summary(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan = AsyncMock()
            with patch(
                "backend.routers.plans.refresh_research",
                new=AsyncMock(return_value={"highlights": ["new trend"]}),
            ):
                response = client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/refresh-research",
                    headers=auth_headers,
                )
        assert response.status_code == 200
        assert response.json()["trend_summary"] == {"highlights": ["new trend"]}

    def test_returns_404_when_brand_not_found_in_middleware(self, client, auth_headers):
        with patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/nonexistent-brand/plans/{TEST_PLAN_ID}/refresh-research",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_404_when_brand_not_found_in_router(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/refresh-research",
                headers=auth_headers,
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Brand not found"

    def test_returns_404_when_plan_not_found(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/nonexistent-plan/refresh-research",
                headers=auth_headers,
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_saves_new_trend_summary_to_firestore(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        new_summary = {"highlights": ["trend A", "trend B"]}
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan = AsyncMock()
            with patch(
                "backend.routers.plans.refresh_research",
                new=AsyncMock(return_value=new_summary),
            ):
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/refresh-research",
                    headers=auth_headers,
                )
            fc.update_plan.assert_called_once_with(
                TEST_BRAND_ID, TEST_PLAN_ID, {"trend_summary": new_summary}
            )

    def test_uses_first_stored_platform_as_primary(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        brand = {
            **sample_brand,
            "selected_platforms": ["tiktok", "instagram"],
            "industry": "fitness",
        }
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan = AsyncMock()
            with patch(
                "backend.routers.plans.refresh_research",
                new=AsyncMock(return_value={}),
            ) as mock_refresh:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/refresh-research",
                    headers=auth_headers,
                )
                assert mock_refresh.call_args.args[0] == ["tiktok", "instagram"]
                assert mock_refresh.call_args.args[2] == "tiktok"

    def test_defaults_to_instagram_when_no_platforms_stored(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        brand = {**sample_brand, "selected_platforms": []}
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=brand)
            fc.get_brand = AsyncMock(return_value=brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan = AsyncMock()
            with patch(
                "backend.routers.plans.refresh_research",
                new=AsyncMock(return_value={}),
            ) as mock_refresh:
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/refresh-research",
                    headers=auth_headers,
                )
                assert "instagram" in mock_refresh.call_args.args[0]
                assert mock_refresh.call_args.args[2] == "instagram"


# ---------------------------------------------------------------------------
# BYOP upload/delete photo endpoints (lines 171-247)
# ---------------------------------------------------------------------------


class TestUploadDayPhoto:
    def test_returns_200_and_photo_url_on_success(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            with patch(
                "backend.routers.plans.upload_byop_photo",
                new=AsyncMock(
                    return_value=("https://signed.url/photo.jpg", "gs://bucket/photo.jpg")
                ),
            ):
                response = client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0/photo",
                    headers=auth_headers,
                    files={"file": ("test.jpg", b"x" * 100, "image/jpeg")},
                )
        assert response.status_code == 200
        data = response.json()
        assert data["custom_photo_url"] == "https://signed.url/photo.jpg"
        assert data["day_index"] == 0

    def test_returns_404_when_plan_not_found(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/nonexistent-plan/days/0/photo",
                headers=auth_headers,
                files={"file": ("test.jpg", b"x" * 100, "image/jpeg")},
            )
        assert response.status_code == 404
        assert "Plan not found" in response.json()["detail"]

    def test_returns_400_when_day_index_out_of_range(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/99/photo",
                headers=auth_headers,
                files={"file": ("test.jpg", b"x" * 100, "image/jpeg")},
            )
        assert response.status_code == 400
        assert "out of range" in response.json()["detail"]

    def test_returns_400_for_unsupported_mime_type(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0/photo",
                headers=auth_headers,
                files={"file": ("test.gif", b"x" * 100, "image/gif")},
            )
        assert response.status_code == 400
        assert "JPEG, PNG, or WebP" in response.json()["detail"]

    def test_returns_500_when_upload_raises(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            with patch(
                "backend.routers.plans.upload_byop_photo",
                new=AsyncMock(side_effect=Exception("GCS error")),
            ):
                response = client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0/photo",
                    headers=auth_headers,
                    files={"file": ("test.png", b"x" * 100, "image/png")},
                )
        assert response.status_code == 500

    def test_saves_signed_url_and_gcs_uri_to_firestore(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        signed_url = "https://signed.url/photo.jpg"
        gcs_uri = "gs://bucket/brands/brand/photo.jpg"

        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            with patch(
                "backend.routers.plans.upload_byop_photo",
                new=AsyncMock(return_value=(signed_url, gcs_uri)),
            ):
                client.post(
                    f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0/photo",
                    headers=auth_headers,
                    files={"file": ("test.jpg", b"x" * 100, "image/jpeg")},
                )
            call_args = fc.update_plan_day.call_args
            update_data = call_args.args[3]
            assert update_data["custom_photo_url"] == signed_url
            assert update_data["custom_photo_gcs_uri"] == gcs_uri


class TestDeleteDayPhoto:
    def test_returns_200_on_success(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            response = client.delete(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/0/photo",
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "removed"
        assert data["day_index"] == 0

    def test_returns_404_when_plan_not_found(self, client, auth_headers, sample_brand):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.delete(
                f"/api/brands/{TEST_BRAND_ID}/plans/nonexistent-plan/days/0/photo",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_400_when_day_index_out_of_range(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            response = client.delete(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/99/photo",
                headers=auth_headers,
            )
        assert response.status_code == 400

    def test_clears_all_photo_fields_in_firestore(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with patch(_PLANS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.update_plan_day = AsyncMock()
            client.delete(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/days/2/photo",
                headers=auth_headers,
            )
            call_args = fc.update_plan_day.call_args
            update_data = call_args.args[3]
            assert update_data["custom_photo_url"] is None
            assert update_data["custom_photo_gcs_uri"] is None
            assert update_data["custom_photo_mime"] is None
