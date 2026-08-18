from pydantic import ValidationError
import pytest

from app.models.auth_models import ResendVerificationRequest, User, VerifyEmailRequest


def test_email_verification_fields_are_backward_compatible():
    """Existing DynamoDB users without new fields remain readable."""
    user = User(
        id="user-1",
        email="person@example.com",
        createdAt="2026-01-01T00:00:00+00:00",
        updatedAt="2026-01-01T00:00:00+00:00",
    )

    assert user.emailVerified is False
    assert user.verificationTokenHash is None
    assert user.verificationVersion == 0


def test_activation_request_requires_a_substantial_token():
    with pytest.raises(ValidationError):
        VerifyEmailRequest(userId="user-1", token="too-short")

    request = VerifyEmailRequest(userId="user-1", token="x" * 32)
    assert request.userId == "user-1"


def test_resend_request_validates_email_address():
    with pytest.raises(ValidationError):
        ResendVerificationRequest(email="not-an-email")

    assert ResendVerificationRequest(email="person@example.com").email == "person@example.com"
