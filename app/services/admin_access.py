"""Shared helpers for protected super-admin access."""

from __future__ import annotations

from typing import Any

SUPER_ADMIN_ROLE = "super_admin"


def is_super_admin_user(user: Any) -> bool:
    """Return whether the persisted user record grants admin access."""
    roles = getattr(user, "roles", None) or []
    return SUPER_ADMIN_ROLE in roles
