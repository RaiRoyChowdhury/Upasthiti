import pytest

from auth.security import (
    JWTError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify_round_trip():
    plain = "SuperSecret123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_access_token_round_trip():
    token = create_access_token(subject="user-123", extra_claims={"role": "teacher"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "teacher"
    assert "exp" in payload


def test_tampered_token_is_rejected():
    token = create_access_token(subject="user-123")
    tampered = token[:-2] + "xx"
    with pytest.raises(JWTError):
        decode_access_token(tampered)
