"""Tests for backend.routers.voice — WebSocket voice-coaching endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.server import app
from backend.tests.conftest import TEST_BRAND_ID, TEST_UID

_VOICE_FC = "backend.routers.voice.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"


def _ws_headers(token: str = "valid-firebase-token") -> dict:
    return {"sec-websocket-protocol": f"auth.{token}"}


def _mock_genai_client_no_responses():
    """Return a mocked genai client whose Live session yields nothing."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    async def _recv_nothing():
        return
        yield

    mock_session.receive = _recv_nothing

    mock_live = MagicMock()
    mock_live.connect = MagicMock(return_value=mock_session)

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.live = mock_live
    return mock_client


class TestVoiceCoachingWebSocket:
    def test_connection_rejected_without_auth_token(self, sample_brand):
        with (
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
        ):
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.side_effect = Exception("no token")
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with pytest.raises(BaseException):  # noqa: B017
                    with tc.websocket_connect(f"/api/brands/{TEST_BRAND_ID}/voice-coaching") as ws:
                        ws.receive_json()

    def test_connection_rejected_with_malformed_protocol_header(self, sample_brand):
        with (
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
        ):
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with pytest.raises(BaseException):  # noqa: B017
                    with tc.websocket_connect(
                        f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                        headers={"sec-websocket-protocol": "not-an-auth-token"},
                    ) as ws:
                        ws.receive_json()

    def test_connection_accepted_with_valid_auth_and_sends_connected(self, sample_brand):
        mock_client = _mock_genai_client_no_responses()

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

    def test_disconnect_without_error_after_connected(self, sample_brand):
        mock_client = _mock_genai_client_no_responses()
        raised = None

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            try:
                with TestClient(app) as tc:
                    with tc.websocket_connect(
                        f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                        headers=_ws_headers(),
                    ) as ws:
                        ws.receive_json()
            except Exception as exc:
                raised = exc

        assert raised is None

    def test_connection_rejected_when_brand_not_found(self, sample_brand):
        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
        ):
            vc_fc.get_brand = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=None)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with pytest.raises(BaseException):  # noqa: B017
                    with tc.websocket_connect(
                        f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                        headers=_ws_headers(),
                    ) as ws:
                        ws.receive_json()

    def test_connection_rejected_when_brand_belongs_to_different_user(self, sample_brand):
        other_owner_brand = {**sample_brand, "owner_uid": "other-user-uid"}

        with (
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
        ):
            mw_fc.get_brand = AsyncMock(return_value=other_owner_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with pytest.raises(BaseException):  # noqa: B017
                    with tc.websocket_connect(
                        f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                        headers=_ws_headers(),
                    ) as ws:
                        ws.receive_json()

    def test_plan_id_query_param_triggers_plan_fetch(self, sample_brand, sample_plan):
        mock_client = _mock_genai_client_no_responses()

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=sample_plan)
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching?plan_id={sample_plan['plan_id']}",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

            vc_fc.get_plan.assert_called_once_with(sample_plan["plan_id"], TEST_BRAND_ID)

    def test_context_query_param_is_accepted(self, sample_brand):
        mock_client = _mock_genai_client_no_responses()

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching?context=Previous+session+data",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

    def test_context_over_4000_chars_is_truncated(self, sample_brand):
        mock_client = _mock_genai_client_no_responses()
        long_context = "X" * 5000

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching?context={long_context}",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

    def test_plan_with_posts_is_fetched_when_plan_exists(self, sample_brand, sample_plan):
        mock_client = _mock_genai_client_no_responses()
        sample_plan_with_id = {**sample_plan, "plan_id": "plan-abc"}

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.list_plans = AsyncMock(return_value=[sample_plan_with_id])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

            vc_fc.list_posts.assert_called_once()

    def test_data_load_error_is_handled_gracefully(self, sample_brand):
        mock_client = _mock_genai_client_no_responses()

        async def _fail_plans(*args, **kwargs):
            raise RuntimeError("Firestore unavailable")

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.list_plans = _fail_plans
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

    def test_session_ended_message_sent_when_gemini_finishes_first(self, sample_brand):
        """recv_from_gemini task completes immediately; session_ended should be sent."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async def _recv_nothing():
            return
            yield

        mock_session.receive = _recv_nothing
        mock_session.send = AsyncMock()

        mock_live = MagicMock()
        mock_live.connect = MagicMock(return_value=mock_session)

        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.live = mock_live

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    msg = ws.receive_json()
                    assert msg["type"] == "connected"

    def test_gemini_session_sends_audio_bytes_to_frontend(self, sample_brand):
        """recv_from_gemini: audio inline_data is forwarded as bytes to the client."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.send = AsyncMock()

        audio_bytes = b"\x00\x01\x02\x03"

        async def _recv_with_audio():
            part = MagicMock()
            part.inline_data = MagicMock()
            part.inline_data.data = audio_bytes
            part.text = None

            model_turn = MagicMock()
            model_turn.parts = [part]

            sc = MagicMock()
            sc.turn_complete = False
            sc.model_turn = model_turn

            response = MagicMock()
            response.server_content = sc

            yield response

        mock_session.receive = _recv_with_audio

        mock_live = MagicMock()
        mock_live.connect = MagicMock(return_value=mock_session)

        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.live = mock_live

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    ws.receive_json()  # "connected"
                    raw = ws.receive_bytes()
                    assert raw == audio_bytes

    def test_gemini_session_sends_transcript_text_to_frontend(self, sample_brand):
        """recv_from_gemini: text parts are forwarded as transcript JSON messages."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.send = AsyncMock()

        async def _recv_with_text():
            part = MagicMock()
            part.inline_data = None
            part.text = "Hello from Gemini!"

            model_turn = MagicMock()
            model_turn.parts = [part]

            sc = MagicMock()
            sc.turn_complete = False
            sc.model_turn = model_turn

            response = MagicMock()
            response.server_content = sc

            yield response

        mock_session.receive = _recv_with_text

        mock_live = MagicMock()
        mock_live.connect = MagicMock(return_value=mock_session)

        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.live = mock_live

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    ws.receive_json()  # "connected"
                    msg = ws.receive_json()
                    assert msg["type"] == "transcript"
                    assert msg["text"] == "Hello from Gemini!"

    def test_end_session_signal_sends_session_complete_and_closes(self, sample_brand):
        """recv_from_gemini: [END_SESSION] in text triggers session_complete message."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.send = AsyncMock()

        async def _recv_with_end_session():
            part = MagicMock()
            part.inline_data = None
            part.text = "Goodbye! [END_SESSION]"

            model_turn = MagicMock()
            model_turn.parts = [part]

            sc = MagicMock()
            sc.turn_complete = False
            sc.model_turn = model_turn

            response = MagicMock()
            response.server_content = sc

            yield response

        mock_session.receive = _recv_with_end_session

        mock_live = MagicMock()
        mock_live.connect = MagicMock(return_value=mock_session)

        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.live = mock_live

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    ws.receive_json()  # "connected"
                    transcript_msg = ws.receive_json()
                    assert transcript_msg["type"] == "transcript"
                    assert "Goodbye" in transcript_msg["text"]
                    complete_msg = ws.receive_json()
                    assert complete_msg["type"] == "session_complete"

    def test_turn_complete_message_is_sent_to_frontend(self, sample_brand):
        """recv_from_gemini: turn_complete flag triggers turn_complete JSON message."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.send = AsyncMock()

        async def _recv_turn_complete():
            sc = MagicMock()
            sc.turn_complete = True
            sc.model_turn = None

            response = MagicMock()
            response.server_content = sc

            yield response

        mock_session.receive = _recv_turn_complete

        mock_live = MagicMock()
        mock_live.connect = MagicMock(return_value=mock_session)

        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.live = mock_live

        with (
            patch(_VOICE_FC) as vc_fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.middleware.firebase_auth") as mock_auth,
            patch("backend.routers.voice.get_genai_client", return_value=mock_client),
            patch(
                "backend.agents.voice_coach.build_coaching_prompt", return_value="System prompt."
            ),
        ):
            vc_fc.get_plan = AsyncMock(return_value=None)
            vc_fc.list_plans = AsyncMock(return_value=[])
            vc_fc.list_posts = AsyncMock(return_value=[])
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            mock_auth.verify_id_token.return_value = {"uid": TEST_UID}
            mock_auth.ExpiredIdTokenError = type("ExpiredIdTokenError", (Exception,), {})
            mock_auth.InvalidIdTokenError = type("InvalidIdTokenError", (Exception,), {})

            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/brands/{TEST_BRAND_ID}/voice-coaching",
                    headers=_ws_headers(),
                ) as ws:
                    ws.receive_json()  # "connected"
                    msg = ws.receive_json()
                    assert msg["type"] == "turn_complete"
