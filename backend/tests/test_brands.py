"""Tests for brand-related logic and validation."""

from unittest.mock import AsyncMock, patch

_BRANDS_FC = "backend.routers.brands.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"


class TestBrandAllowedKeys:
    """Test that brand analysis sanitizes LLM output to allowed keys."""

    ALLOWED_KEYS = {
        "brand_voice",
        "target_audience",
        "key_messages",
        "colors",
        "competitors",
        "content_pillars",
        "visual_style",
        "industry",
    }

    def test_sanitize_filters_unknown_keys(self):
        """Only allowed keys should pass through from LLM output."""
        raw_profile = {
            "brand_voice": "professional",
            "target_audience": "small business owners",
            "malicious_key": "should be removed",
            "colors": ["#FF0000"],
            "__private": "also removed",
        }
        safe = {k: v for k, v in raw_profile.items() if k in self.ALLOWED_KEYS}
        assert "brand_voice" in safe
        assert "target_audience" in safe
        assert "colors" in safe
        assert "malicious_key" not in safe
        assert "__private" not in safe

    def test_empty_profile_returns_empty(self):
        """Empty LLM output should produce empty dict."""
        safe = {k: v for k, v in {}.items() if k in self.ALLOWED_KEYS}
        assert safe == {}


TEST_BRAND_ID = "test-brand-id-456"
TEST_UID = "test-user-uid-123"


class TestListBrandsEndpoint:
    """HTTP tests for GET /api/brands."""

    def test_list_brands_returns_brands(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc:
            fc.list_brands_by_owner = AsyncMock(return_value=[sample_brand])
            response = client.get(
                "/api/brands", params={"owner_uid": TEST_UID}, headers=auth_headers
            )
        assert response.status_code == 200
        assert len(response.json()["brands"]) == 1
        assert response.json()["brands"][0]["brand_id"] == sample_brand["brand_id"]

    def test_list_brands_returns_empty_list(self, client, auth_headers):
        with patch(_BRANDS_FC) as fc:
            fc.list_brands_by_owner = AsyncMock(return_value=[])
            response = client.get(
                "/api/brands", params={"owner_uid": TEST_UID}, headers=auth_headers
            )
        assert response.status_code == 200
        assert response.json()["brands"] == []

    def test_list_brands_requires_owner_uid(self, client, auth_headers):
        response = client.get("/api/brands", headers=auth_headers)
        assert response.status_code == 422


class TestCreateBrandEndpoint:
    """HTTP tests for POST /api/brands."""

    def test_create_brand_returns_brand_id(self, client, auth_headers):
        with patch(_BRANDS_FC) as fc:
            fc.create_brand = AsyncMock(return_value=TEST_BRAND_ID)
            response = client.post(
                "/api/brands",
                json={
                    "website_url": "https://example.com",
                    "description": "A test brand description here",
                },
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["brand_id"] == TEST_BRAND_ID
        assert response.json()["status"] == "created"

    def test_create_brand_with_owner_uid(self, client, auth_headers):
        with patch(_BRANDS_FC) as fc:
            fc.create_brand = AsyncMock(return_value="new-brand-id")
            response = client.post(
                "/api/brands",
                json={
                    "website_url": "https://example.com",
                    "description": "Brand with owner description text",
                    "owner_uid": TEST_UID,
                },
                headers=auth_headers,
            )
        assert response.status_code == 200
        call_kwargs = fc.create_brand.call_args[0][0]
        assert call_kwargs["owner_uid"] == TEST_UID


class TestGetBrandEndpoint:
    """HTTP tests for GET /api/brands/{brand_id}."""

    def test_get_brand_returns_brand_profile(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.get(f"/api/brands/{TEST_BRAND_ID}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["brand_profile"]["brand_id"] == sample_brand["brand_id"]
        assert response.json()["brand_profile"]["business_name"] == sample_brand["business_name"]

    def test_get_brand_returns_404_when_missing(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.get(f"/api/brands/{TEST_BRAND_ID}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Brand not found"


class TestUpdateBrandEndpoint:
    """HTTP tests for PUT /api/brands/{brand_id}."""

    def test_update_brand_returns_updated_profile(self, client, auth_headers, sample_brand):
        updated_brand = {**sample_brand, "business_name": "Updated Brand Name"}
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(side_effect=[sample_brand, updated_brand])
            fc.update_brand = AsyncMock()
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}",
                json={"business_name": "Updated Brand Name"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "updated"
        assert response.json()["brand_profile"]["business_name"] == "Updated Brand Name"

    def test_update_brand_returns_404_when_missing(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.put(
                f"/api/brands/{TEST_BRAND_ID}",
                json={"business_name": "x"},
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestAnalyzeBrandEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/analyze."""

    def test_analyze_brand_returns_profile_on_success(self, client, auth_headers, sample_brand):
        profile = {"business_name": "Analyzed Brand", "tone": "professional", "industry": "tech"}
        analyzed_brand = {**sample_brand, **profile, "analysis_status": "complete"}
        with (
            patch(_BRANDS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.routers.brands.run_brand_analysis", new=AsyncMock(return_value=profile)),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            fc.get_brand = AsyncMock(side_effect=[sample_brand, analyzed_brand])
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/analyze",
                json={
                    "website_url": "https://example.com",
                    "description": "Tech startup creating innovative software solutions",
                },
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "analyzed"
        assert "brand_profile" in data

    def test_analyze_brand_marks_failed_on_exception(self, client, auth_headers, sample_brand):
        async def _fail(*args, **kwargs):
            raise RuntimeError("Agent crashed")

        with (
            patch(_BRANDS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.routers.brands.run_brand_analysis", new=_fail),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/analyze",
                json={
                    "website_url": "https://example.com",
                    "description": "A brand with great products and services",
                },
                headers=auth_headers,
            )
        assert response.status_code == 500
        update_calls = [str(c) for c in fc.update_brand.call_args_list]
        assert any("failed" in c for c in update_calls)

    def test_analyze_brand_filters_disallowed_keys(self, client, auth_headers, sample_brand):
        profile = {
            "business_name": "Clean Brand",
            "tone": "friendly",
            "__private": "should not save",
            "malicious": "drop this",
        }
        analyzed_brand = {
            **sample_brand,
            "business_name": "Clean Brand",
            "analysis_status": "complete",
        }
        with (
            patch(_BRANDS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.routers.brands.run_brand_analysis", new=AsyncMock(return_value=profile)),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            fc.get_brand = AsyncMock(side_effect=[sample_brand, analyzed_brand])
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/analyze",
                json={
                    "website_url": "https://example.com",
                    "description": "A brand with great products and services",
                },
                headers=auth_headers,
            )
        assert response.status_code == 200
        update_args = fc.update_brand.call_args_list[-1][0][1]
        assert "__private" not in update_args
        assert "malicious" not in update_args


class TestUploadBrandAssetEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/upload."""

    def test_upload_image_returns_uploaded_list(self, client, auth_headers, sample_brand):
        import io

        with (
            patch(_BRANDS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.routers.brands.upload_brand_asset",
                new=AsyncMock(return_value="gs://bucket/brands/test/img.png"),
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/upload",
                headers=auth_headers,
                files={
                    "files": ("logo.png", io.BytesIO(b"\x89PNG\r\n" + b"\x00" * 50), "image/png")
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "uploaded" in data
        assert len(data["uploaded"]) == 1
        assert data["uploaded"][0]["filename"] == "logo.png"
        assert data["uploaded"][0]["type"] == "image"

    def test_upload_pdf_sets_type_document(self, client, auth_headers, sample_brand):
        import io

        with (
            patch(_BRANDS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.routers.brands.upload_brand_asset",
                new=AsyncMock(return_value="gs://bucket/brands/test/doc.pdf"),
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/upload",
                headers=auth_headers,
                files={
                    "files": (
                        "guide.pdf",
                        io.BytesIO(b"%PDF-1.4" + b"\x00" * 50),
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == 200
        assert response.json()["uploaded"][0]["type"] == "document"

    def test_upload_rejects_more_than_3_files(self, client, auth_headers, sample_brand):
        import io

        file_data = [
            ("files", (f"img{i}.png", io.BytesIO(b"\x00" * 50), "image/png")) for i in range(4)
        ]
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/upload",
                headers=auth_headers,
                files=file_data,
            )
        assert response.status_code == 400
        assert "3" in response.json()["detail"]

    def test_upload_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        import io

        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/upload",
                headers=auth_headers,
                files={"files": ("img.png", io.BytesIO(b"\x00" * 50), "image/png")},
            )
        assert response.status_code == 404


class TestDeleteBrandAssetEndpoint:
    """HTTP tests for DELETE /api/brands/{brand_id}/assets/{asset_index}."""

    def test_delete_asset_returns_deleted(self, client, auth_headers, sample_brand):
        removed = {
            "filename": "logo.png",
            "url": "gs://bucket/brands/test/logo.png",
            "type": "image",
        }
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.remove_brand_asset = AsyncMock(return_value=removed)
            response = client.delete(
                f"/api/brands/{TEST_BRAND_ID}/assets/0",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        assert response.json()["removed"]["filename"] == "logo.png"

    def test_delete_asset_returns_404_when_not_found(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.remove_brand_asset = AsyncMock(return_value=None)
            response = client.delete(
                f"/api/brands/{TEST_BRAND_ID}/assets/99",
                headers=auth_headers,
            )
        assert response.status_code == 404
        assert "Asset not found" in response.json()["detail"]


class TestSetBrandLogoEndpoint:
    """HTTP tests for PATCH /api/brands/{brand_id}/logo."""

    def test_set_logo_url(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/logo",
                json={"logo_url": "https://cdn.example.com/logo.png"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "updated"
        assert response.json()["logo_url"] == "https://cdn.example.com/logo.png"

    def test_clear_logo_url_with_null(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_brand = AsyncMock()
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/logo",
                json={"logo_url": None},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["logo_url"] is None

    def test_set_logo_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/logo",
                json={"logo_url": "https://cdn.example.com/logo.png"},
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestClaimBrandEndpoint:
    """HTTP tests for PATCH /api/brands/{brand_id}/claim."""

    def test_claim_brand_returns_claimed(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.claim_brand = AsyncMock(return_value=True)
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/claim",
                json={"owner_uid": TEST_UID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "claimed"
        assert response.json()["brand_id"] == TEST_BRAND_ID

    def test_claim_brand_returns_404_when_not_found(self, client, auth_headers, sample_brand):
        with patch(_BRANDS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.claim_brand = AsyncMock(return_value=False)
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/claim",
                json={"owner_uid": TEST_UID},
                headers=auth_headers,
            )
        assert response.status_code == 404
