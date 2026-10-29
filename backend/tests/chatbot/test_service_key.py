import asyncio

import pytest

from app.core.security.service_key import (
    InvalidServiceKey,
    ServiceKeyChannelMismatch,
    generate_service_key,
    hash_secret,
    parse_service_key,
    secret_matches,
)
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import ServiceAuthService
from tests.chatbot.test_chat_routes import FakeServiceKeyStore


def test_generated_key_round_trips_and_only_hash_is_kept():
    generated = generate_service_key()

    parsed = parse_service_key(generated.token)

    assert generated.token.startswith(f"qsk_{generated.key_id}_")
    assert parsed.key_id == generated.key_id
    assert generated.secret_hash == hash_secret(parsed.secret) != parsed.secret
    assert secret_matches(parsed.secret, generated.secret_hash)
    assert not secret_matches(parsed.secret + "x", generated.secret_hash)


@pytest.mark.parametrize("token, reason", [
    (None, "missing"),
    ("", "missing"),
    ("sk-openai-style", "malformed"),
    ("qsk_0123456789abcdef_short", "malformed"),
    ("qsk_XYZ_" + "a" * 43, "malformed"),
])
def test_parse_rejects_bad_tokens(token, reason):
    with pytest.raises(InvalidServiceKey) as error:
        parse_service_key(token)
    assert error.value.reason == reason


def test_service_auth_builds_service_principal_from_key_record():
    store = FakeServiceKeyStore()
    token = store.issue()

    principal = asyncio.run(ServiceAuthService(store).authenticate(token, ChannelType.CRM))

    assert principal.principal_type == "service"
    assert principal.authn_method == "service_key"
    assert principal.subject_id == "crm_sales"
    assert principal.tenant_id == "qs_technology"
    assert principal.credential_id == parse_service_key(token).key_id
    assert principal.acting_user_id is None and not principal.scopes and not principal.roles


def test_service_auth_rejects_key_issued_for_other_channel():
    store = FakeServiceKeyStore()
    token = store.issue(channel="website")

    with pytest.raises(ServiceKeyChannelMismatch) as error:
        asyncio.run(ServiceAuthService(store).authenticate(token, ChannelType.CRM))

    assert (error.value.key_channel, error.value.expected) == ("website", "crm")
    assert error.value.key_id == parse_service_key(token).key_id
