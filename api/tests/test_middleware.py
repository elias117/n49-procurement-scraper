"""Tests for API middleware behavior."""
import logging
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware import Middleware

from api.main import app as main_app
from api.middleware import (
    APICORSMiddleware,
    GlobalExceptionMiddleware,
    RequestLoggingMiddleware,
)


def _build_test_app() -> FastAPI:
    app = FastAPI(
        middleware=[
            Middleware(APICORSMiddleware),
            Middleware(RequestLoggingMiddleware),
            Middleware(GlobalExceptionMiddleware),
        ]
    )

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    return app


def test_main_registers_middleware_in_expected_order():
    """Main app should register middleware as CORS -> logging -> exceptions."""
    middleware_classes = [item.cls for item in main_app.user_middleware]
    assert middleware_classes[:3] == [
        APICORSMiddleware,
        RequestLoggingMiddleware,
        GlobalExceptionMiddleware,
    ]


def test_cors_headers_on_normal_response(monkeypatch):
    """Allowed origin should receive CORS headers on regular responses."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.example.com")
    client = TestClient(_build_test_app())

    response = client.get("/ok", headers={"Origin": "https://frontend.example.com"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_preflight_options(monkeypatch):
    """Preflight OPTIONS should return expected CORS headers."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.example.com")
    client = TestClient(_build_test_app())

    response = client.options(
        "/ok",
        headers={
            "Origin": "https://frontend.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_request_logging_format_and_levels(monkeypatch, caplog):
    """Request logs should use expected message format and severity levels."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.example.com")
    client = TestClient(_build_test_app())
    caplog.set_level(logging.INFO, logger="api")

    # 2xx -> INFO
    caplog.clear()
    ok_response = client.get("/ok")
    assert ok_response.status_code == 200
    ok_record = next(
        record for record in caplog.records if record.message.startswith("GET /ok ->")
    )
    assert ok_record.levelno == logging.INFO
    assert re.fullmatch(r"GET /ok -> 200 \(\d+ms\)", ok_record.message)

    # 4xx -> WARNING
    caplog.clear()
    not_found_response = client.get("/missing")
    assert not_found_response.status_code == 404
    warning_record = next(
        record
        for record in caplog.records
        if record.message.startswith("GET /missing ->")
    )
    assert warning_record.levelno == logging.WARNING
    assert re.fullmatch(r"GET /missing -> 404 \(\d+ms\)", warning_record.message)

    # 5xx -> ERROR
    caplog.clear()
    error_response = client.get("/boom")
    assert error_response.status_code == 500
    error_record = next(
        record for record in caplog.records if record.message.startswith("GET /boom ->")
    )
    assert error_record.levelno == logging.ERROR
    assert re.fullmatch(r"GET /boom -> 500 \(\d+ms\)", error_record.message)


def test_unhandled_exception_returns_safe_500_json(monkeypatch):
    """Unhandled exceptions should return standardized 500 JSON without trace details."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.example.com")
    client = TestClient(_build_test_app())

    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error", "status": 500}
    assert "Traceback" not in response.text
    assert "kaboom" not in response.text


def test_unhandled_exception_logs_traceback(monkeypatch, caplog):
    """Server should log the original exception with traceback details."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.example.com")
    client = TestClient(_build_test_app())
    caplog.set_level(logging.ERROR, logger="api")

    response = client.get("/boom")

    assert response.status_code == 500
    assert any(
        record.levelno == logging.ERROR
        and record.message == "Unhandled exception while processing request"
        for record in caplog.records
    )
    assert "kaboom" in caplog.text
    assert "Traceback" in caplog.text
