"""Tests for auth security utilities."""
import pytest
from app.auth.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hash_and_verify():
    pw = "my-secret-password"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip():
    subject = "42"
    token = create_access_token(subject)
    decoded = decode_access_token(token)
    assert decoded == subject


def test_invalid_token_returns_none():
    result = decode_access_token("not-a-token")
    assert result is None
