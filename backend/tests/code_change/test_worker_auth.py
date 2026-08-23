from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.gateway.auth_middleware import AuthMiddleware
from app.gateway.code_change_worker_auth import CODE_CHANGE_WORKER_PATH, is_code_change_worker_request
from app.gateway.csrf_middleware import should_check_csrf
from app.gateway.internal_auth import get_trusted_internal_owner_user_id


def _request(path: str, token: str = "") -> Request:
    headers = [(b"x-code-change-worker-token", token.encode())] if token else []
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def test_worker_token_is_exact_path_scoped_and_bypasses_browser_csrf(monkeypatch):
    monkeypatch.setenv("DEER_FLOW_CODE_CHANGE_WORKER_TOKEN", "worker-secret")
    worker = _request(CODE_CHANGE_WORKER_PATH, "worker-secret")
    other_path = _request("/api/code-change/projects", "worker-secret")

    assert is_code_change_worker_request(worker) is True
    assert should_check_csrf(worker) is False
    assert is_code_change_worker_request(other_path) is False


def test_worker_token_authenticates_internal_owner_for_worker_route(monkeypatch):
    monkeypatch.setenv("DEER_FLOW_CODE_CHANGE_WORKER_TOKEN", "worker-secret")
    monkeypatch.setattr("app.gateway.auth_middleware.is_auth_disabled", lambda: False)
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post(CODE_CHANGE_WORKER_PATH)
    def probe(request: Request) -> dict:
        return {
            "role": request.state.user.system_role,
            "owner": get_trusted_internal_owner_user_id(request),
        }

    client = TestClient(app)
    response = client.post(
        CODE_CHANGE_WORKER_PATH,
        headers={
            "X-Code-Change-Worker-Token": "worker-secret",
            "X-DeerFlow-Owner-User-Id": "owner-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"role": "internal", "owner": "owner-123"}
    assert client.post(CODE_CHANGE_WORKER_PATH, headers={"X-Code-Change-Worker-Token": "wrong"}).status_code == 401
