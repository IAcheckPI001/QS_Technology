"""Service key cho hệ thống tích hợp (CRM backend) gọi Chatbot server-to-server.

Định dạng `qsk_<key_id>_<secret>`: `key_id` công khai dùng để tra bản ghi, chỉ
hash của `secret` được lưu. Secret có entropy cao (256 bit) nên SHA-256 là đủ,
không cần hàm băm chậm kiểu bcrypt.
"""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Literal

KEY_PREFIX = "qsk_"
_KEY_PATTERN = re.compile(r"^qsk_(?P<key_id>[0-9a-f]{16})_(?P<secret>[A-Za-z0-9_-]{43})$")

InvalidServiceKeyReason = Literal[
    "missing",
    "malformed",
    "unknown_key",
    "secret_mismatch",
    "revoked",
    "expired",
    "integration_disabled",
]


class InvalidServiceKey(Exception):
    """Key không dùng được. `reason` chỉ để log, không trả cho client."""

    def __init__(self, reason: InvalidServiceKeyReason, key_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.key_id = key_id


class ServiceKeyChannelMismatch(Exception):
    """Key hợp lệ nhưng cấp cho kênh khác với endpoint được gọi."""

    def __init__(self, key_id: str, key_channel: str, expected: str) -> None:
        super().__init__(f"{key_channel} != {expected}")
        self.key_id = key_id
        self.key_channel = key_channel
        self.expected = expected


@dataclass(frozen=True)
class ParsedServiceKey:
    key_id: str
    secret: str


@dataclass(frozen=True)
class GeneratedServiceKey:
    key_id: str
    secret_hash: str
    token: str  # chỉ hiển thị một lần khi cấp


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("ascii")).hexdigest()


def generate_service_key() -> GeneratedServiceKey:
    key_id = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    return GeneratedServiceKey(
        key_id=key_id,
        secret_hash=hash_secret(secret),
        token=f"{KEY_PREFIX}{key_id}_{secret}",
    )


def parse_service_key(token: str | None) -> ParsedServiceKey:
    if not token:
        raise InvalidServiceKey("missing")
    match = _KEY_PATTERN.match(token)
    if match is None:
        raise InvalidServiceKey("malformed")
    return ParsedServiceKey(key_id=match["key_id"], secret=match["secret"])


def secret_matches(secret: str, secret_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), secret_hash)
