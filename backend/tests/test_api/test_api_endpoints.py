"""
test_api_endpoints.py — Integration tests for Phase 09 REST API.

Uses FastAPI's TestClient with mocked database dependencies.
All DB operations are mocked to isolate API layer testing.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

# ─── Test settings ────────────────────────────────────────────────────────

TEST_API_KEY = "dev_key_change_in_production"  # matches Settings default


# ─── Fixtures ─────────────────────────────────────────────────────────────

def _make_pattern(
    pattern_id: uuid.UUID | None = None,
    lifecycle_state: str = "active",
    dump_type: str = "TP_DUMP",
    origin: str = "JFK",
    destination: str = "BKK",
    carrier: str = "LH",
    confidence: float = 0.85,
    savings: float = 580.0,
    manual_input_bundle: dict | None = None,
) -> MagicMock:
    """Create a mock DumpPattern object."""
    pattern = MagicMock()
    pattern.id = pattern_id or uuid.uuid4()
    pattern.dump_type = dump_type
    pattern.lifecycle_state = lifecycle_state
    pattern.origin_iata = origin
    pattern.destination_iata = destination
    pattern.ticketing_carrier_iata = carrier
    pattern.operating_carriers = [carrier]
    pattern.routing_points = ["FRA"]
    pattern.fare_basis_hint = "YLOWUS"
    pattern.ita_routing_code = f"{origin}/{carrier}X/FRA/{carrier}X/{destination}"
    pattern.manual_input_bundle = manual_input_bundle
    pattern.expected_yq_savings_usd = savings
    pattern.confidence_score = confidence
    pattern.freshness_tier = 1
    pattern.source = "FLYERTALK"
    pattern.source_url = "https://flyertalk.com/test"
    pattern.source_post_weight = 0.7
    pattern.backup_pattern_id = None
    pattern.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pattern.updated_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
    return pattern


def _make_carrier(
    iata_code: str = "LH",
    name: str = "Lufthansa",
    alliance: str = "STAR",
    charges_yq: bool = True,
    typical_yq_usd: float = 500.0,
) -> MagicMock:
    """Create a mock Carrier object."""
    carrier = MagicMock()
    carrier.iata_code = iata_code
    carrier.name = name
    carrier.alliance = alliance
    carrier.charges_yq = charges_yq
    carrier.typical_yq_usd = typical_yq_usd
    carrier.last_yq_updated = datetime(2026, 3, 1, tzinfo=timezone.utc)
    carrier.yq_scrape_url = None
    carrier.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    carrier.updated_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    return carrier


def _make_validation_run(
    pattern_id: uuid.UUID,
    success: bool = True,
    yq_charged: float = 0.0,
) -> MagicMock:
    """Create a mock ValidationRun object."""
    run = MagicMock()
    run.id = uuid.uuid4()
    run.pattern_id = pattern_id
    run.ran_at = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)
    run.success = success
    run.yq_charged_usd = yq_charged
    run.yq_expected_usd = 500.0
    run.base_fare_usd = 350.0
    run.raw_ita_response = {"test": True}
    run.manual_input_snapshot = None
    run.error_message = None if success else "ITA query timeout"
    run.proxy_used = None
    return run


# ─── Client fixture ──────────────────────────────────────────────────────

@pytest.fixture
def client():
    """FastAPI TestClient with mocked DB session."""
    from app.dependencies import get_db_session

    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": TEST_API_KEY}


# ═══════════════════════════════════════════════════════════════════════════
# Health endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """GET /health — no auth required."""

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_no_auth_required(self, client):
        """Health should work without API key."""
        resp = client.get("/health")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Auth tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthentication:
    """All endpoints except /health require X-API-Key."""

    def test_missing_api_key_returns_403(self, client):
        resp = client.get("/api/v1/patterns")
        assert resp.status_code == 403

    def test_invalid_api_key_returns_403(self, client):
        resp = client.get(
            "/api/v1/patterns",
            headers={"X-API-Key": "wrong_key"},
        )
        assert resp.status_code == 403

    def test_valid_api_key_passes(self, client, auth_headers):
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.get("/api/v1/patterns", headers=auth_headers)
            assert resp.status_code == 200

    def test_carriers_requires_auth(self, client):
        resp = client.get("/api/v1/carriers")
        assert resp.status_code == 403

    def test_validations_requires_auth(self, client):
        pid = uuid.uuid4()
        resp = client.get(f"/api/v1/validations/{pid}/history")
        assert resp.status_code == 403

    def test_ingestion_requires_auth(self, client):
        resp = client.post("/api/v1/ingestion/submit", json={"url": "https://test.com"})
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Patterns endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestListPatterns:
    """GET /api/v1/patterns"""

    def test_empty_list(self, client, auth_headers):
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.get("/api/v1/patterns", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert data["total"] == 0
            assert data["page"] == 1

    def test_returns_patterns(self, client, auth_headers):
        patterns = [_make_pattern(), _make_pattern(destination="SIN")]
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=patterns,
        ):
            resp = client.get("/api/v1/patterns", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 2

    def test_filter_by_origin(self, client, auth_headers):
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = client.get(
                "/api/v1/patterns?origin=LAX",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs.get("origin") == "LAX" or call_kwargs[1].get("origin") == "LAX"

    def test_filter_by_dump_type(self, client, auth_headers):
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = client.get(
                "/api/v1/patterns?dump_type=TP_DUMP",
                headers=auth_headers,
            )
            assert resp.status_code == 200

    def test_min_confidence_filter(self, client, auth_headers):
        low_conf = _make_pattern(confidence=0.3)
        high_conf = _make_pattern(confidence=0.9)
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[low_conf, high_conf],
        ):
            resp = client.get(
                "/api/v1/patterns?min_confidence=0.5",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 1

    def test_min_savings_filter(self, client, auth_headers):
        low_savings = _make_pattern(savings=30.0)
        high_savings = _make_pattern(savings=600.0)
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[low_savings, high_savings],
        ):
            resp = client.get(
                "/api/v1/patterns?min_savings_usd=200",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 1

    def test_pagination(self, client, auth_headers):
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            resp = client.get(
                "/api/v1/patterns?page=3&page_size=10",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["page"] == 3
            assert data["page_size"] == 10


class TestGetPattern:
    """GET /api/v1/patterns/{id}"""

    def test_returns_pattern_detail(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid)
        with patch(
            "app.api.patterns.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.get(f"/api/v1/patterns/{pid}", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(pid)
            assert data["dump_type"] == "TP_DUMP"
            assert data["origin_iata"] == "JFK"

    def test_not_found(self, client, auth_headers):
        pid = uuid.uuid4()
        with patch(
            "app.api.patterns.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(f"/api/v1/patterns/{pid}", headers=auth_headers)
            assert resp.status_code == 404


class TestGetManualInput:
    """GET /api/v1/patterns/{id}/manual-input"""

    def test_returns_manual_input(self, client, auth_headers):
        pid = uuid.uuid4()
        bundle = {
            "routing_code_string": "JFK/LHX/FRA/LHX/BKK",
            "human_description": "JFK to BKK via FRA on LH",
            "ita_matrix_steps": ["1. Go to ITA Matrix", "2. Enter routing"],
            "expected_yq_savings_usd": 580.0,
            "expected_yq_carrier": "LH",
            "validation_timestamp": "2026-03-20T10:00:00Z",
            "confidence_score": 0.85,
            "backup_routing_code": None,
            "notes": None,
        }
        pattern = _make_pattern(pattern_id=pid, manual_input_bundle=bundle)
        with patch(
            "app.api.patterns.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.get(f"/api/v1/patterns/{pid}/manual-input", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["routing_code_string"] == "JFK/LHX/FRA/LHX/BKK"

    def test_no_bundle_returns_404(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid, manual_input_bundle=None)
        with patch(
            "app.api.patterns.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.get(f"/api/v1/patterns/{pid}/manual-input", headers=auth_headers)
            assert resp.status_code == 404

    def test_pattern_not_found(self, client, auth_headers):
        pid = uuid.uuid4()
        with patch(
            "app.api.patterns.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(f"/api/v1/patterns/{pid}/manual-input", headers=auth_headers)
            assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Carriers endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestListCarriers:
    """GET /api/v1/carriers"""

    def test_empty_list(self, client, auth_headers):
        with patch(
            "app.api.carriers.get_all_carriers",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.api.carriers.count_carriers",
            new_callable=AsyncMock,
            return_value=0,
        ):
            resp = client.get("/api/v1/carriers", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["items"] == []
            assert data["total"] == 0

    def test_returns_carriers(self, client, auth_headers):
        carriers = [
            _make_carrier("LH", "Lufthansa", typical_yq_usd=500.0),
            _make_carrier("BA", "British Airways", typical_yq_usd=450.0),
        ]
        with patch(
            "app.api.carriers.get_all_carriers",
            new_callable=AsyncMock,
            return_value=carriers,
        ), patch(
            "app.api.carriers.count_carriers",
            new_callable=AsyncMock,
            return_value=2,
        ):
            resp = client.get("/api/v1/carriers", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 2
            assert data["total"] == 2

    def test_filter_charges_yq(self, client, auth_headers):
        with patch(
            "app.api.carriers.get_all_carriers",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get, patch(
            "app.api.carriers.count_carriers",
            new_callable=AsyncMock,
            return_value=0,
        ):
            resp = client.get(
                "/api/v1/carriers?charges_yq=true",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_get.assert_called_once()


class TestGetCarrier:
    """GET /api/v1/carriers/{iata_code}"""

    def test_returns_carrier(self, client, auth_headers):
        carrier = _make_carrier()
        with patch(
            "app.api.carriers.get_carrier_by_iata",
            new_callable=AsyncMock,
            return_value=carrier,
        ):
            resp = client.get("/api/v1/carriers/LH", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["iata_code"] == "LH"
            assert data["name"] == "Lufthansa"

    def test_not_found(self, client, auth_headers):
        with patch(
            "app.api.carriers.get_carrier_by_iata",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get("/api/v1/carriers/XX", headers=auth_headers)
            assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Validations endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestTriggerValidation:
    """POST /api/v1/validations/trigger/{pattern_id}"""

    def test_queues_task(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid)
        mock_task = MagicMock()
        mock_task.id = "celery-task-id-123"

        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ), patch(
            "app.tasks.validation_tasks.validate_single_pattern"
        ) as mock_validate:
            mock_validate.delay.return_value = mock_task
            resp = client.post(
                f"/api/v1/validations/trigger/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "queued"
            assert data["task_id"] == "celery-task-id-123"

    def test_pattern_not_found(self, client, auth_headers):
        pid = uuid.uuid4()
        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.post(
                f"/api/v1/validations/trigger/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 404

    def test_archived_pattern_rejected(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid, lifecycle_state="archived")
        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.post(
                f"/api/v1/validations/trigger/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 400

    def test_deprecated_pattern_rejected(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid, lifecycle_state="deprecated")
        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.post(
                f"/api/v1/validations/trigger/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 400


class TestValidationHistory:
    """GET /api/v1/validations/{pattern_id}/history"""

    def test_returns_history(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid)
        runs = [
            _make_validation_run(pid, success=True),
            _make_validation_run(pid, success=False),
        ]
        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ), patch(
            "app.api.validations.validation_repository.get_run_history",
            new_callable=AsyncMock,
            return_value=runs,
        ):
            resp = client.get(
                f"/api/v1/validations/{pid}/history",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) == 2

    def test_pattern_not_found(self, client, auth_headers):
        pid = uuid.uuid4()
        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(
                f"/api/v1/validations/{pid}/history",
                headers=auth_headers,
            )
            assert resp.status_code == 404

    def test_pagination(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid)
        with patch(
            "app.api.validations.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ), patch(
            "app.api.validations.validation_repository.get_run_history",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_hist:
            resp = client.get(
                f"/api/v1/validations/{pid}/history?page=2&page_size=5",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["page"] == 2
            assert data["page_size"] == 5


# ═══════════════════════════════════════════════════════════════════════════
# Ingestion endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestIngestionSubmit:
    """POST /api/v1/ingestion/submit"""

    def test_submits_url(self, client, auth_headers):
        mock_task = MagicMock()
        mock_task.id = "celery-ingestion-123"

        with patch(
            "app.tasks.ingestion_tasks.scan_all_forums"
        ) as mock_scan:
            mock_scan.delay.return_value = mock_task
            resp = client.post(
                "/api/v1/ingestion/submit",
                headers=auth_headers,
                json={"url": "https://flyertalk.com/forum/thread/12345"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "queued"
            assert data["task_id"] == "celery-ingestion-123"

    def test_empty_url_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/v1/ingestion/submit",
            headers=auth_headers,
            json={"url": ""},
        )
        assert resp.status_code == 422

    def test_missing_url_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/v1/ingestion/submit",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Manual inputs endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestManualInputsEndpoint:
    """GET /api/v1/manual-inputs/{pattern_id}"""

    def test_returns_bundle(self, client, auth_headers):
        pid = uuid.uuid4()
        bundle = {"routing_code_string": "JFK/LHX/FRA", "test": True}
        pattern = _make_pattern(pattern_id=pid, manual_input_bundle=bundle)
        with patch(
            "app.api.manual_inputs.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.get(
                f"/api/v1/manual-inputs/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["routing_code_string"] == "JFK/LHX/FRA"

    def test_no_bundle_404(self, client, auth_headers):
        pid = uuid.uuid4()
        pattern = _make_pattern(pattern_id=pid, manual_input_bundle=None)
        with patch(
            "app.api.manual_inputs.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=pattern,
        ):
            resp = client.get(
                f"/api/v1/manual-inputs/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 404

    def test_pattern_not_found_404(self, client, auth_headers):
        pid = uuid.uuid4()
        with patch(
            "app.api.manual_inputs.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(
                f"/api/v1/manual-inputs/{pid}",
                headers=auth_headers,
            )
            assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Exception handler tests
# ═══════════════════════════════════════════════════════════════════════════

class TestExceptionHandlers:
    """Verify custom exception handlers return correct shapes."""

    def test_not_found_error_shape(self, client, auth_headers):
        pid = uuid.uuid4()
        with patch(
            "app.api.patterns.pattern_repository.get_pattern_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.get(f"/api/v1/patterns/{pid}", headers=auth_headers)
            assert resp.status_code == 404
            data = resp.json()
            assert "detail" in data  # FastAPI HTTPException format


# ═══════════════════════════════════════════════════════════════════════════
# OpenAPI docs
# ═══════════════════════════════════════════════════════════════════════════

class TestOpenAPIDocs:
    """Verify OpenAPI docs are served."""

    def test_docs_endpoint(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_json(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["info"]["title"] == "Fare Construction Engine"
        # Verify all expected paths exist
        paths = data["paths"]
        assert "/health" in paths
        assert "/api/v1/patterns" in paths
        assert "/api/v1/carriers" in paths


# ═══════════════════════════════════════════════════════════════════════════
# Dependencies tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDependencies:
    """Test dependency injection functions."""

    def test_require_api_key_missing(self, client):
        """Missing key returns 403."""
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.get("/api/v1/patterns")
            assert resp.status_code == 403

    def test_require_api_key_wrong(self, client):
        """Wrong key returns 403."""
        with patch(
            "app.api.patterns.pattern_repository.get_active_patterns",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = client.get(
                "/api/v1/patterns",
                headers={"X-API-Key": "invalid"},
            )
            assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Exceptions module tests
# ═══════════════════════════════════════════════════════════════════════════

class TestExceptionsModule:
    """Test custom exception classes."""

    def test_not_found_error(self):
        from app.exceptions import NotFoundError
        err = NotFoundError("Pattern", "abc-123")
        assert "Pattern" in str(err)
        assert "abc-123" in str(err)

    def test_duplicate_error(self):
        from app.exceptions import DuplicateError
        err = DuplicateError("Pattern", "ita_routing_code", "JFK/LH/FRA")
        assert "already exists" in str(err)

    def test_authentication_error(self):
        from app.exceptions import AuthenticationError
        err = AuthenticationError()
        assert "API key" in str(err)

    def test_lifecycle_error(self):
        from app.exceptions import LifecycleError
        err = LifecycleError("active", "archived")
        assert "active" in str(err)
        assert "archived" in str(err)

    def test_validation_error(self):
        from app.exceptions import ValidationError
        err = ValidationError("bad input")
        assert "bad input" in str(err)

    def test_base_error(self):
        from app.exceptions import FareEngineError
        err = FareEngineError()
        assert "error" in str(err).lower()
