"""Transactional email delivery through Resend."""

from urllib.parse import urlencode

import httpx

from app.utils.config import get_settings


class EmailDeliveryError(Exception):
    """Raised when an activation email cannot be accepted by Resend."""


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def send_verification_email(self, email: str, user_id: str, token: str) -> None:
        if not self.settings.resend_api_key:
            raise EmailDeliveryError("Email delivery has not been configured")

        # Keep the secret in the fragment. Browsers do not send fragments to
        # static hosting/CDN access logs or HTTP referrers.
        query = urlencode({"uid": user_id})
        activation_url = f"{self.settings.frontend_url.rstrip('/')}/verify-email?{query}#token={token}"
        subject = "Activate your Diagrammatic account"
        text = (
            "Welcome to Diagrammatic!\n\n"
            f"Activate your account by opening this link within "
            f"{self.settings.email_verification_expire_minutes} minutes:\n{activation_url}\n\n"
            "If you did not create this account, you can safely ignore this email."
        )
        html = (
            "<p>Welcome to <strong>Diagrammatic</strong>!</p>"
            "<p>Activate your account by clicking the button below. "
            f"This link expires in {self.settings.email_verification_expire_minutes} minutes.</p>"
            f'<p><a href="{activation_url}">Activate account</a></p>'
            "<p>If you did not create this account, you can safely ignore this email.</p>"
        )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                    json={"from": self.settings.resend_from_email, "to": [email], "subject": subject, "text": text, "html": html},
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Unable to send activation email") from exc


email_service = EmailService()
