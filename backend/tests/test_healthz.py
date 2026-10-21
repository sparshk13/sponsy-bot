"""Tests for liveness endpoint and security headers."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.config import settings
from app.main import app
from app.security import CSP_POLICY, SecurityHeadersMiddleware


def test_healthz_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers_present_on_api_response() -> None:
    client = TestClient(app)
    response = client.get("/api/healthz")
    assert response.headers["content-security-policy"] == CSP_POLICY
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["permissions-policy"] == ""
    assert response.headers["cache-control"] == "no-store"


def test_spa_serves_html_with_security_headers() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "content-security-policy" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "Sponsy" in response.text


def test_docs_disabled_when_not_dev(monkeypatch: MonkeyPatch) -> None:
    # SEC-38
    monkeypatch.setattr(settings, "app_env", "prod")

    prod_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    prod_app.add_middleware(SecurityHeadersMiddleware)
    client = TestClient(prod_app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
