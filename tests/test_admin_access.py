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
