"""Optional API-token auth — pure checks, no server needed."""

from __future__ import annotations

from app.api.deps import _token_ok


def test_auth_disabled_when_no_token():
    assert _token_ok("", None, None) is True
    assert _token_ok("", "Bearer anything", None) is True


def test_bearer_token_accepted():
    assert _token_ok("secret", "Bearer secret", None) is True
    assert _token_ok("secret", "bearer secret", None) is True  # case-insensitive scheme


def test_x_api_key_accepted():
    assert _token_ok("secret", None, "secret") is True


def test_wrong_or_missing_token_rejected():
    assert _token_ok("secret", None, None) is False
    assert _token_ok("secret", "Bearer nope", None) is False
    assert _token_ok("secret", None, "nope") is False
