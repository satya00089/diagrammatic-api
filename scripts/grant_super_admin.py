"""Grant the first super-admin role to an existing verified account.

Run once from diagrammatic-api after the user's account exists:
    python scripts/grant_super_admin.py --email owner@example.com
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.admin_access import SUPER_ADMIN_ROLE
from app.services.dynamodb_service import dynamodb_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing verified account")
    args = parser.parse_args()

    user = dynamodb_service.get_user_by_email(args.email.strip().lower())
    if not user:
        parser.error("No account was found for that email")
    if not user.emailVerified and not user.googleId:
        parser.error("The account must have a verified email address")

    roles = sorted(set(user.roles + [SUPER_ADMIN_ROLE]))
    updated = dynamodb_service.update_user_roles(user.id, roles)
    if not updated:
        print("Could not save the super-admin role", file=sys.stderr)
        return 1

    print(f"Granted super-admin access to {updated.email} ({updated.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
