from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
import pytest

def test_password_hashing():
    pw = "secret123"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong", hashed) is False

def test_jwt_flow():
    data = {"sub": "testuser", "role": "admin"}
    token = create_access_token(data)
    payload = decode_access_token(token)
    assert payload["sub"] == "testuser"
    assert payload["role"] == "admin"