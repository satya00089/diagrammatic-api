from types import SimpleNamespace

from botocore.exceptions import ClientError

from app.services import admin_access
from app.services.dynamodb_service import DynamoDBService


def test_persisted_super_admin_role_grants_access() -> None:
    user = SimpleNamespace(email="person@example.com", roles=["super_admin"])

    assert admin_access.is_super_admin_user(user)


def test_email_alone_does_not_grant_access() -> None:
    owner = SimpleNamespace(email="owner@example.com", roles=[])
    regular_user = SimpleNamespace(email="person@example.com", roles=[])

    assert not admin_access.is_super_admin_user(owner)
    assert not admin_access.is_super_admin_user(regular_user)


def test_updating_user_roles_aliases_reserved_roles_attribute() -> None:
    class ExistingUserTable:
        def update_item(self, **kwargs):
            assert (
                kwargs["UpdateExpression"]
                == "SET #roles = :roles, updatedAt = :updated"
            )
            assert kwargs["ExpressionAttributeNames"] == {"#roles": "roles"}
            assert kwargs["ExpressionAttributeValues"][":roles"] == [
                "member",
                "super_admin",
            ]
            return {
                "Attributes": {
                    "id": "user-id",
                    "email": "owner@example.com",
                    "roles": ["member", "super_admin"],
                    "createdAt": "2026-01-01T00:00:00+00:00",
                    "updatedAt": "2026-01-01T00:00:00+00:00",
                }
            }

    service = object.__new__(DynamoDBService)
    service.users_table = ExistingUserTable()

    updated = service.update_user_roles("user-id", ["member", "super_admin"])

    assert updated is not None
    assert updated.roles == ["member", "super_admin"]


def test_updating_missing_feedback_does_not_create_item() -> None:
    class MissingFeedbackTable:
        def update_item(self, **kwargs):
            assert kwargs["ConditionExpression"] == "attribute_exists(id)"
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "missing"}},
                "UpdateItem",
            )

    service = object.__new__(DynamoDBService)
    service.feedback_table = MissingFeedbackTable()

    assert service.update_feedback_status("missing-id", "resolved") is None
