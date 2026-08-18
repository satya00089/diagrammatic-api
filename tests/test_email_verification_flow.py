from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import auth
from app.services.auth_service import auth_service
from app.services.email_service import EmailDeliveryError


def test_google_email_authority_only_allows_google_managed_addresses():
    assert auth_service.is_google_email_authoritative(
        {"email": "person@gmail.com", "email_verified": False}
    )
    assert auth_service.is_google_email_authoritative(
        {"email": "person@company.com", "email_verified": True, "hosted_domain": "company.com"}
    )
    assert not auth_service.is_google_email_authoritative(
        {"email": "person@example.com", "email_verified": True}
    )


@pytest.mark.asyncio
async def test_delivery_failure_restores_the_previous_verification_state(monkeypatch):
    user = SimpleNamespace(
        id="user-1",
        email="person@example.com",
        updatedAt="2026-08-18T00:00:00+00:00",
        verificationVersion=3,
        verificationTokenHash="old-token-hash",
        verificationExpiresAt="2026-08-18T01:00:00+00:00",
        verificationSentAt="2026-08-18T00:00:00+00:00",
    )
    restored = []

    monkeypatch.setattr(auth.dynamodb_service, "save_email_verification_token", lambda *args: user)

    async def fail_delivery(*args):
        raise EmailDeliveryError("provider unavailable")

    monkeypatch.setattr(auth.email_service, "send_verification_email", fail_delivery)
    monkeypatch.setattr(
        auth.dynamodb_service,
        "restore_email_verification_state",
        lambda original, token_hash: restored.append((original, token_hash)),
    )

    with pytest.raises(HTTPException) as error:
        await auth._issue_verification_email(user)

    assert error.value.status_code == 503
    assert restored and restored[0][0] is user
