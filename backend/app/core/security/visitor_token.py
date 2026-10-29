"""Visitor token cho khách website: JWT HS256 tối giản, ký bằng stdlib.

Chỉ xác minh token do chính server cấp (một secret, một thuật toán), nên không
cần thư viện JWT đầy đủ. Header `alg` được kiểm cố định HS256 để chặn `alg=none`.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

ALGORITHM = "HS256"
TOKEN_TYPE = "visitor"
_HEADER = {"alg": ALGORITHM, "typ": "JWT"}
_MIN_SECRET_BYTES = 32


class InvalidVisitorToken(Exception):
    """Token sai định dạng, sai chữ ký, sai issuer hoặc hết hạn."""


@dataclass(frozen=True)
class VisitorClaims:
    guest_id: str
    issued_at: datetime
    expires_at: datetime


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def _check_secret(secret: str) -> None:
    if len(secret.encode()) < _MIN_SECRET_BYTES:
        raise ValueError(f"visitor token secret must be at least {_MIN_SECRET_BYTES} bytes")


def issue_visitor_token(
    guest_id: str,
    *,
    secret: str,
    issuer: str,
    ttl: timedelta,
    now: datetime | None = None,
) -> tuple[str, VisitorClaims]:
    _check_secret(secret)
    issued_at = (now or datetime.now(UTC)).replace(microsecond=0)
    expires_at = issued_at + ttl
    payload = {
        "sub": guest_id,
        "iss": issuer,
        "typ": TOKEN_TYPE,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    signing_input = ".".join(
        _b64encode(json.dumps(part, separators=(",", ":")).encode())
        for part in (_HEADER, payload)
    )
    token = f"{signing_input}.{_sign(signing_input, secret)}"
    return token, VisitorClaims(guest_id=guest_id, issued_at=issued_at, expires_at=expires_at)


def verify_visitor_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    now: datetime | None = None,
) -> VisitorClaims:
    _check_secret(secret)
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidVisitorToken("malformed")
    header_b64, payload_b64, signature = parts
    # So chữ ký trước khi parse payload: dữ liệu chưa xác thực không được dùng.
    if not hmac.compare_digest(_sign(f"{header_b64}.{payload_b64}", secret), signature):
        raise InvalidVisitorToken("bad_signature")
    try:
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
        guest_id = payload["sub"]
        issued_at = datetime.fromtimestamp(payload["iat"], UTC)
        expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidVisitorToken("malformed") from error
    if header != _HEADER:
        raise InvalidVisitorToken("unsupported_header")
    if payload.get("iss") != issuer or payload.get("typ") != TOKEN_TYPE:
        raise InvalidVisitorToken("wrong_issuer")
    if not isinstance(guest_id, str) or not guest_id:
        raise InvalidVisitorToken("malformed")
    if expires_at <= (now or datetime.now(UTC)):
        raise InvalidVisitorToken("expired")
    return VisitorClaims(guest_id=guest_id, issued_at=issued_at, expires_at=expires_at)
