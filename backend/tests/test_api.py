from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


TEST_SECRET = "test-secret-for-automated-tests-only-32chars"


def make_client():
    settings = Settings(
        app_env="development",
        auth_mode="mock",
        enable_test_auth=True,
        dev_test_secret=TEST_SECRET,
        database_url="sqlite+pysqlite:///:memory:",
        cors_origins=[],
    )
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return TestClient(create_app(settings=settings, engine=engine))


def login(client, user_id="test-agent-001"):
    response = client.post(
        "/v1/dev/session",
        headers={"X-Dev-Test-Secret": TEST_SECRET},
        json={"user_id": user_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_mock_login_is_secret_protected():
    with make_client() as client:
        response = client.post(
            "/v1/dev/session", json={"user_id": "test-agent-001"}
        )
        assert response.status_code == 401


def test_progress_is_saved_and_isolated_by_test_user():
    with make_client() as client:
        token = login(client)
        headers = {"Authorization": "Bearer " + token}
        payload = {
            "course_id": "modelo-tres-lineas",
            "course_version": "pilot-1",
            "status": "in_progress",
            "modules": [
                {
                    "module_id": "m1",
                    "status": "completed",
                    "score": 90,
                    "attempts": 2,
                    "required_resources_opened": True,
                    "resource_types": ["presentation"],
                }
            ],
        }
        saved = client.put("/v1/me/progress", headers=headers, json=payload)
        assert saved.status_code == 200
        assert saved.json()["status"] == "in_progress"
        assert saved.json()["modules"][0]["score"] == 90
        assert saved.json()["modules"][0]["required_resources_opened"] is True

        loaded = client.get(
            "/v1/me/progress",
            headers=headers,
            params={"course_id": "modelo-tres-lineas", "course_version": "pilot-1"},
        )
        assert loaded.status_code == 200
        assert loaded.json()["modules"][0]["attempts"] == 2
        assert loaded.json()["completed_at"] is None

        other_token = login(client, "test-agent-002")
        isolated = client.get(
            "/v1/me/progress",
            headers={"Authorization": "Bearer " + other_token},
            params={"course_id": "modelo-tres-lineas", "course_version": "pilot-1"},
        )
        assert isolated.status_code == 404


def test_entry_records_first_login_without_resetting_it():
    with make_client() as client:
        token = login(client)
        headers = {"Authorization": "Bearer " + token}
        request_body = {
            "course_id": "modelo-tres-lineas",
            "course_version": "pilot-1",
        }
        first = client.post("/v1/me/entry", headers=headers, json=request_body)
        assert first.status_code == 200
        first_entry_at = first.json()["first_entry_at"]

        second = client.post("/v1/me/entry", headers=headers, json=request_body)
        assert second.status_code == 200
        assert second.json()["first_entry_at"] == first_entry_at
        assert second.json()["last_activity_at"] is not None


def test_mock_auth_cannot_be_enabled_in_production():
    settings = Settings(
        app_env="production",
        auth_mode="mock",
        enable_test_auth=False,
        dev_test_secret="",
        database_url="sqlite+pysqlite:///:memory:",
        cors_origins=[],
    )
    try:
        create_app(settings=settings)
    except RuntimeError as error:
        assert "no se permite en producción" in str(error)
    else:
        raise AssertionError("El modo mock se aceptó en producción")


def test_completion_timestamp_is_created_by_server():
    with make_client() as client:
        token = login(client)
        response = client.put(
            "/v1/me/progress",
            headers={"Authorization": "Bearer " + token},
            json={
                "course_id": "modelo-tres-lineas",
                "course_version": "pilot-1",
                "status": "completed",
                "modules": [],
            },
        )
        assert response.status_code == 200
        assert response.json()["completed_at"] is not None


def test_invalid_score_is_rejected():
    with make_client() as client:
        token = login(client)
        response = client.put(
            "/v1/me/progress",
            headers={"Authorization": "Bearer " + token},
            json={
                "course_id": "modelo-tres-lineas",
                "course_version": "pilot-1",
                "status": "in_progress",
                "modules": [
                    {"module_id": "m1", "status": "completed", "score": 150}
                ],
            },
        )
        assert response.status_code == 422


def test_attempt_count_can_be_unknown_when_client_does_not_track_attempts():
    with make_client() as client:
        token = login(client)
        response = client.put(
            "/v1/me/progress",
            headers={"Authorization": "Bearer " + token},
            json={
                "course_id": "modelo-tres-lineas",
                "course_version": "pilot-1",
                "status": "in_progress",
                "modules": [
                    {"module_id": "m1", "status": "not_started", "attempts": None}
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["modules"][0]["attempts"] is None
