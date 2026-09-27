import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException


TEST_USERS = {
    "test-agent-{0:03d}".format(number): "Agente de prueba {0}".format(number)
    for number in range(1, 21)
}
TOKEN_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class AuthenticatedUser:
    subject_id: str


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(subject_id, secret, now=None):
    payload = json.dumps(
        {"sub": subject_id, "exp": int(now if now is not None else time.time()) + TOKEN_TTL_SECONDS},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = _b64encode(payload)
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return encoded_payload + "." + _b64encode(signature)


def verify_token(token, secret, now=None):
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        supplied_signature = _b64decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return None
        payload = json.loads(_b64decode(encoded_payload))
        current_time = int(now if now is not None else time.time())
        subject_id = payload.get("sub")
        if payload.get("exp", 0) <= current_time or subject_id not in TEST_USERS:
            return None
        return AuthenticatedUser(subject_id=subject_id)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def build_auth_dependency(settings):
    def current_user(authorization: str | None = Header(default=None)):
        if settings.auth_mode != "mock" or not settings.enable_test_auth:
            raise HTTPException(status_code=503, detail="La autenticación institucional está pendiente")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Se requiere autenticación")
        token = authorization[7:].strip()
        user = verify_token(token, settings.dev_test_secret)
        if user is None:
            raise HTTPException(status_code=401, detail="Token de prueba inválido o vencido")
        return user

    return current_user
