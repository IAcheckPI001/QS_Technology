import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security.visitor_token import (
    InvalidVisitorToken,
    issue_visitor_token,
    verify_visitor_token,
)
from app.modules.chatbot.services import VisitorIdentityService

SECRET = "s" * 48
ISSUER = "qs-chatbot"
NOW = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)


def _issue(guest_id="guest-1", *, secret=SECRET, issuer=ISSUER, ttl=timedelta(hours=1)):
    token, _ = issue_visitor_token(guest_id, secret=secret, issuer=issuer, ttl=ttl, now=NOW)
    return token


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_issued_token_verifies_to_same_guest():
    claims = verify_visitor_token(_issue(), secret=SECRET, issuer=ISSUER, now=NOW)

    assert claims.guest_id == "guest-1"
    assert claims.expires_at == NOW + timedelta(hours=1)


@pytest.mark.parametrize("token", [
    "not-a-token",
    "a.b",
    "",
])
def test_malformed_token_is_rejected(token):
    with pytest.raises(InvalidVisitorToken):
        verify_visitor_token(token, secret=SECRET, issuer=ISSUER, now=NOW)


def test_tampered_payload_is_rejected():
    header, _, signature = _issue().split(".")
    forged = _b64({"sub": "someone-else", "iss": ISSUER, "typ": "visitor",
                   "iat": int(NOW.timestamp()), "exp": int(NOW.timestamp()) + 3600})

    with pytest.raises(InvalidVisitorToken):
        verify_visitor_token(f"{header}.{forged}.{signature}", secret=SECRET, issuer=ISSUER, now=NOW)


def test_alg_none_is_rejected():
    _, payload, _ = _issue().split(".")
    unsigned = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{payload}."

    with pytest.raises(InvalidVisitorToken):
        verify_visitor_token(unsigned, secret=SECRET, issuer=ISSUER, now=NOW)


def test_other_secret_or_issuer_is_rejected():
    with pytest.raises(InvalidVisitorToken):
        verify_visitor_token(_issue(), secret="x" * 48, issuer=ISSUER, now=NOW)
    with pytest.raises(InvalidVisitorToken):
        verify_visitor_token(_issue(), secret=SECRET, issuer="other", now=NOW)


def test_expired_token_is_rejected():
    with pytest.raises(InvalidVisitorToken):
        verify_visitor_token(_issue(), secret=SECRET, issuer=ISSUER, now=NOW + timedelta(hours=1))


def test_short_secret_is_refused():
    with pytest.raises(ValueError):
        _issue(secret="short")


def test_identity_service_refreshes_valid_token_and_replaces_invalid_one():
    identity = VisitorIdentityService(secret=SECRET, issuer=ISSUER, ttl=timedelta(days=7))
    first = identity.issue(None)

    refreshed = identity.issue(first.token)
    replaced = identity.issue("garbage")

    assert refreshed.guest_id == first.guest_id
    assert replaced.guest_id != first.guest_id
    principal = identity.authenticate(refreshed.token)
    assert principal.subject_id == first.guest_id
    assert principal.principal_type == "guest"
    assert principal.authn_method == "guest_token"
