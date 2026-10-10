from types import SimpleNamespace

from botocore.exceptions import ClientError

from app.routers import admin as admin_router
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


def test_admin_feedback_item_includes_and_caches_submitter_profile(monkeypatch) -> None:
    author = SimpleNamespace(
        name="Diagramwise Member",
        email="member@example.com",
        picture="https://lh3.googleusercontent.com/profile-photo",
    )
    lookups = []

    def get_user_by_id(user_id):
        lookups.append(user_id)
        return author

    monkeypatch.setattr(admin_router.dynamodb_service, "get_user_by_id", get_user_by_id)
    cache = {}
    feedback = {
        "id": "feedback-id",
        "createdAt": "2026-10-10T00:00:00+00:00",
        "source": "global",
        "category": "other",
        "userId": "user-id",
    }

    item = admin_router._feedback_item(feedback, cache)
    cached_item = admin_router._feedback_item(feedback, cache)

    assert item.authorName == "Diagramwise Member"
    assert item.authorEmail == "member@example.com"
    assert item.authorPicture == "https://lh3.googleusercontent.com/profile-photo"
    assert cached_item.authorEmail == item.authorEmail
    assert lookups == ["user-id"]


def test_admin_feedback_item_does_not_look_up_anonymous_submitter(monkeypatch) -> None:
    def unexpected_lookup(_user_id):
        raise AssertionError("anonymous feedback must not trigger a user lookup")

    monkeypatch.setattr(admin_router.dynamodb_service, "get_user_by_id", unexpected_lookup)
    item = admin_router._feedback_item(
        {
            "id": "anonymous-feedback",
            "createdAt": "2026-10-10T00:00:00+00:00",
            "source": "global",
            "category": "other",
        }
    )

    assert item.authorName is None
    assert item.authorEmail is None
    assert item.authorPicture is None
