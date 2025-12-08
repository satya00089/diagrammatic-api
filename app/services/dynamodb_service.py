"""DynamoDB service for managing users and diagrams."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from mypy_boto3_dynamodb.service_resource import Table

from app.utils.config import get_settings
from app.models.auth_models import User
from app.models.diagram_models import Diagram, Collaborator, Permission
from app.models.attempt_models import AttemptResponse

settings = get_settings()


def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility.
    DynamoDB doesn't support Python float type - requires Decimal instead.
    """
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]  # type: ignore[misc]
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}  # type: ignore[misc]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def convert_decimal_to_float(obj: Any) -> Any:
    """
    Recursively convert all Decimal values back to float for JSON serialization.
    This is needed when retrieving data from DynamoDB.
    """
    if isinstance(obj, list):
        return [convert_decimal_to_float(item) for item in obj]  # type: ignore[misc]
    elif isinstance(obj, dict):
        return {key: convert_decimal_to_float(value) for key, value in obj.items()}  # type: ignore[misc]
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


class DynamoDBService:
    """Service for DynamoDB operations."""

    def __init__(self):
        """Initialize DynamoDB service."""
        dynamodb = boto3.resource(  # type: ignore[misc]
            "dynamodb",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.users_table: Table = dynamodb.Table(settings.dynamodb_users_table)
        self.diagrams_table: Table = dynamodb.Table(settings.dynamodb_diagrams_table)
        self.problems_table: Table = dynamodb.Table(settings.dynamodb_problems_table)
        self.attempts_table: Table = dynamodb.Table(settings.dynamodb_attempts_table)

    # User operations
    def create_user(
        self,
        email: str,
        password_hash: Optional[str] = None,
        name: Optional[str] = None,
        picture: Optional[str] = None,
        google_id: Optional[str] = None,
    ) -> User:
        """Create a new user in DynamoDB."""
        # First check if user already exists to prevent duplicates
        existing_user = self.get_user_by_email(email)
        if existing_user:
            # If creating with Google ID and existing user doesn't have it, update
            if google_id and not existing_user.googleId:
                updated_user = self.update_user_google_id(
                    existing_user.id, google_id, picture
                )
                if updated_user:
                    return updated_user
            # Otherwise return existing user
            return existing_user

        user_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        item: Dict[str, Any] = {
            "id": user_id,
            "email": email,
            "name": name,
            "createdAt": now,
            "updatedAt": now,
        }

        if password_hash:
            item["passwordHash"] = password_hash
        if picture:
            item["picture"] = picture
        if google_id:
            item["googleId"] = google_id

        try:
            # Use ConditionExpression to prevent creating if ID already exists
            self.users_table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(id)"
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")  # type: ignore[union-attr]
            if error_code == "ConditionalCheckFailedException":
                # User was created by another request, fetch and return it
                existing_user = self.get_user_by_email(email)
                if existing_user:
                    return existing_user
            raise

        return User(**item)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email using GSI."""
        try:
            response = self.users_table.query(
                IndexName="email-index", KeyConditionExpression=Key("email").eq(email)
            )
            items = response.get("Items", [])
            if items:
                user_data: Dict[str, Any] = items[0]
                return User(**user_data)
            return None
        except ClientError:
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            response = self.users_table.get_item(Key={"id": user_id})
            item = response.get("Item")
            if item:
                user_data: Dict[str, Any] = item
                return User(**user_data)
            return None
        except ClientError:
            return None

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID using GSI."""
        try:
            response = self.users_table.query(
                IndexName="googleId-index",
                KeyConditionExpression=Key("googleId").eq(google_id),
            )
            items = response.get("Items", [])
            if items:
                user_data: Dict[str, Any] = items[0]
                return User(**user_data)
            return None
        except ClientError:
            return None

    def update_user_google_id(
        self, user_id: str, google_id: str, picture: Optional[str] = None
    ) -> Optional[User]:
        """Update user's Google ID and picture (for linking Google account to existing user)."""
        try:
            now = datetime.now(timezone.utc).isoformat()

            update_expression = "SET googleId = :google_id, updatedAt = :updated"
            expression_values: Dict[str, Any] = {
                ":google_id": google_id,
                ":updated": now,
            }

            # Add picture to update if provided
            if picture:
                update_expression += ", picture = :picture"
                expression_values[":picture"] = picture

            response = self.users_table.update_item(
                Key={"id": user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ReturnValues="ALL_NEW",
            )
            item = response.get("Attributes")
            if item:
                user_data: Dict[str, Any] = item
                return User(**user_data)
            return None
        except ClientError as e:
            print(f"Error updating user Google ID: {e}")
            return None

    # Diagram operations
    def create_diagram(
        self,
        user_id: str,
        title: str,
        description: Optional[str],
        nodes: List[Any],
        edges: List[Any],
    ) -> Diagram:
        """Create a new diagram in DynamoDB."""
        diagram_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Convert floats to Decimal for DynamoDB
        nodes_decimal = convert_floats_to_decimal(nodes)
        edges_decimal = convert_floats_to_decimal(edges)

        item: Dict[str, Any] = {
            "id": diagram_id,
            "userId": user_id,
            "title": title,
            "description": description,
            "nodes": nodes_decimal,
            "edges": edges_decimal,
            "createdAt": now,
            "updatedAt": now,
        }

        self.diagrams_table.put_item(Item=item)

        # Return with original float values for response
        return Diagram(
            id=diagram_id,
            userId=user_id,
            title=title,
            description=description,
            nodes=nodes,
            edges=edges,
            createdAt=now,
            updatedAt=now,
        )

    def get_diagrams_by_user(self, user_id: str) -> List[Diagram]:
        """Get all diagrams for a user."""
        try:
            items: List[Dict[str, Any]] = []
            # Handle pagination to get all diagrams
            response = self.diagrams_table.query(
                KeyConditionExpression=Key("userId").eq(user_id)
            )
            response_items = response.get("Items", [])
            items.extend(response_items)

            # Continue fetching if there are more pages
            while "LastEvaluatedKey" in response:
                response = self.diagrams_table.query(
                    KeyConditionExpression=Key("userId").eq(user_id),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                response_items = response.get("Items", [])
                items.extend(response_items)

            # Convert Decimal back to float for JSON serialization
            items_float = [convert_decimal_to_float(item) for item in items]
            return [Diagram(**item) for item in items_float]
        except ClientError as e:
            print(f"Error querying diagrams: {e}")
            return []

    def get_diagram(self, user_id: str, diagram_id: str) -> Optional[Diagram]:
        """Get a specific diagram."""
        try:
            response = self.diagrams_table.get_item(
                Key={"userId": user_id, "id": diagram_id}
            )
            item = response.get("Item")
            if item:
                # Convert Decimal back to float for JSON serialization
                item_float: Dict[str, Any] = convert_decimal_to_float(item)
                return Diagram(**item_float)
            return None
        except ClientError:
            return None

    def update_diagram(
        self,
        user_id: str,
        diagram_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        nodes: Optional[List[Any]] = None,
        edges: Optional[List[Any]] = None,
    ) -> Optional[Diagram]:
        """Update a diagram."""
        try:
            now = datetime.now(timezone.utc).isoformat()

            update_expression = "SET updatedAt = :updated"
            expression_values: Dict[str, Any] = {":updated": now}
            expression_names: Dict[str, str] = {}

            if title is not None:
                update_expression += ", title = :title"
                expression_values[":title"] = title

            if description is not None:
                update_expression += ", description = :description"
                expression_values[":description"] = description

            if nodes is not None:
                update_expression += ", #nodes = :nodes"
                # Convert floats to Decimal for DynamoDB
                expression_values[":nodes"] = convert_floats_to_decimal(nodes)
                expression_names["#nodes"] = "nodes"

            if edges is not None:
                update_expression += ", #edges = :edges"
                # Convert floats to Decimal for DynamoDB
                expression_values[":edges"] = convert_floats_to_decimal(edges)
                expression_names["#edges"] = "edges"

            update_kwargs: Dict[str, Any] = {
                "Key": {"userId": user_id, "id": diagram_id},
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_values,
                "ReturnValues": "ALL_NEW",
            }

            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            response = self.diagrams_table.update_item(**update_kwargs)

            item = response.get("Attributes")
            if item:
                # Convert Decimal back to float for JSON serialization
                item_float: Dict[str, Any] = convert_decimal_to_float(item)
                return Diagram(**item_float)
            return None
        except ClientError:
            return None

    def delete_diagram(self, user_id: str, diagram_id: str) -> bool:
        """Delete a diagram."""
        try:
            self.diagrams_table.delete_item(Key={"userId": user_id, "id": diagram_id})
            return True
        except ClientError:
            return False

    # Sharing operations
    def share_diagram(
        self, diagram_id: str, owner_id: str, collaborator: Collaborator
    ) -> bool:
        """Share a diagram with a collaborator."""
        try:
            # Get the current diagram
            diagram = self.get_diagram(owner_id, diagram_id)
            if not diagram:
                return False

            # Check if collaborator already exists
            existing_collaborator = next(
                (c for c in diagram.collaborators if c.userId == collaborator.userId),
                None,
            )

            if existing_collaborator:
                # Update existing collaborator's permission
                existing_collaborator.permission = collaborator.permission
                existing_collaborator.addedAt = collaborator.addedAt
            else:
                # Add new collaborator
                diagram.collaborators.append(collaborator)

            # Update the diagram in DynamoDB
            self.diagrams_table.update_item(
                Key={"userId": owner_id, "id": diagram_id},
                UpdateExpression="SET collaborators = :collaborators, updatedAt = :updated",
                ExpressionAttributeValues={
                    ":collaborators": [
                        convert_floats_to_decimal(c.dict())
                        for c in diagram.collaborators
                    ],
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
            )
            return True
        except ClientError:
            return False

    def remove_collaborator(
        self, diagram_id: str, owner_id: str, collaborator_user_id: str
    ) -> bool:
        """Remove a collaborator from a diagram."""
        try:
            # Get the current diagram
            diagram = self.get_diagram(owner_id, diagram_id)
            if not diagram:
                return False

            # Remove the collaborator
            diagram.collaborators = [
                c for c in diagram.collaborators if c.userId != collaborator_user_id
            ]

            # Update the diagram in DynamoDB
            self.diagrams_table.update_item(
                Key={"userId": owner_id, "id": diagram_id},
                UpdateExpression="SET collaborators = :collaborators, updatedAt = :updated",
                ExpressionAttributeValues={
                    ":collaborators": [
                        convert_floats_to_decimal(c.dict())
                        for c in diagram.collaborators
                    ],
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
            )
            return True
        except ClientError:
            return False

    def update_collaborator_permission(
        self,
        diagram_id: str,
        owner_id: str,
        collaborator_user_id: str,
        permission: Permission,
    ) -> bool:
        """Update a collaborator's permission level."""
        try:
            # Get the current diagram
            diagram = self.get_diagram(owner_id, diagram_id)
            if not diagram:
                return False

            # Find and update the collaborator
            for collaborator in diagram.collaborators:
                if collaborator.userId == collaborator_user_id:
                    collaborator.permission = permission
                    break
            else:
                return False  # Collaborator not found

            # Update the diagram in DynamoDB
            self.diagrams_table.update_item(
                Key={"userId": owner_id, "id": diagram_id},
                UpdateExpression="SET collaborators = :collaborators, updatedAt = :updated",
                ExpressionAttributeValues={
                    ":collaborators": [
                        convert_floats_to_decimal(c.dict())
                        for c in diagram.collaborators
                    ],
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
            )
            return True
        except ClientError:
            return False

    def get_diagram_collaborators(
        self, diagram_id: str, owner_id: str
    ) -> List[Collaborator]:
        """Get all collaborators for a diagram."""
        try:
            diagram = self.get_diagram(owner_id, diagram_id)
            return diagram.collaborators if diagram else []
        except ClientError:
            return []

    def check_collaborator_permission(
        self, diagram_id: str, user_id: str
    ) -> Optional[Permission]:
        """Check if a user has access to a diagram and return their permission level."""
        try:
            # First check if user is the owner
            diagram = self.get_diagram(user_id, diagram_id)
            if diagram:
                return Permission.EDIT  # Owner has edit permission

            # Check if user is a collaborator
            # We need to find the diagram by scanning or using a GSI
            # For now, we'll scan the table (not efficient for production)
            response = self.diagrams_table.scan()
            items = response.get("Items", [])

            for item in items:
                item_float = convert_decimal_to_float(item)
                if item_float.get("id") == diagram_id:
                    collaborators = item_float.get("collaborators", [])
                    for collab_data in collaborators:
                        if collab_data.get("userId") == user_id:
                            return Permission(collab_data.get("permission"))

            return None
        except ClientError:
            return None

    def get_shared_diagrams_for_user(self, user_id: str) -> List[Diagram]:
        """Get all diagrams shared with a user."""
        try:
            shared_diagrams = []

            # Scan all diagrams to find those where user is a collaborator
            response = self.diagrams_table.scan()
            items = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.diagrams_table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

            for item in items:
                item_float = convert_decimal_to_float(item)
                collaborators = item_float.get("collaborators", [])

                # Check if user is a collaborator
                for collab_data in collaborators:
                    if collab_data.get("userId") == user_id:
                        diagram = Diagram(**item_float)
                        shared_diagrams.append(diagram)
                        break

            return shared_diagrams
        except ClientError:
            return []

    # Problem operations
    def get_all_problems(self) -> List[Dict[str, Any]]:
        """Get all problems from DynamoDB."""
        try:
            items: List[Dict[str, Any]] = []
            response = self.problems_table.scan()
            items.extend(response.get("Items", []))

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.problems_table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

            return items
        except ClientError:
            return []

    def get_problem_by_id(self, problem_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific problem by ID."""
        try:
            response = self.problems_table.get_item(Key={"id": problem_id})
            return response.get("Item")
        except ClientError:
            return None

    def get_problems_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get problems by category using GSI."""
        try:
            items: List[Dict[str, Any]] = []
            response = self.problems_table.query(
                IndexName="category-index",
                KeyConditionExpression=Key("category").eq(category),
            )
            items.extend(response.get("Items", []))

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.problems_table.query(
                    IndexName="category-index",
                    KeyConditionExpression=Key("category").eq(category),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

            return items
        except ClientError:
            return []

    def get_problems_by_difficulty(self, difficulty: str) -> List[Dict[str, Any]]:
        """Get problems by difficulty using GSI."""
        try:
            items: List[Dict[str, Any]] = []
            response = self.problems_table.query(
                IndexName="difficulty-index",
                KeyConditionExpression=Key("difficulty").eq(difficulty),
            )
            items.extend(response.get("Items", []))

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.problems_table.query(
                    IndexName="difficulty-index",
                    KeyConditionExpression=Key("difficulty").eq(difficulty),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

            return items
        except ClientError:
            return []

    # Problem attempt operations
    def create_or_update_attempt(
        self,
        user_id: str,
        problem_id: str,
        title: str,
        difficulty: Optional[str],
        category: Optional[str],
        nodes: List[Any],
        edges: List[Any],
        elapsed_time: int = 0,
        last_assessment: Optional[dict] = None,
    ) -> AttemptResponse:
        """Create or update a problem attempt (upsert operation)."""
        try:
            # Get existing attempt to preserve assessment count
            existing_attempt = self.get_attempt_by_problem(user_id, problem_id)

            now = datetime.now(timezone.utc).isoformat()

            # Convert floats to Decimal for DynamoDB
            nodes_decimal = convert_floats_to_decimal(nodes)
            edges_decimal = convert_floats_to_decimal(edges)
            assessment_decimal = (
                convert_floats_to_decimal(last_assessment) if last_assessment else None
            )

            # Increment assessment count if new assessment provided
            assessment_count = 0
            preserved_assessment = None
            if existing_attempt:
                assessment_count = existing_attempt.assessmentCount
                preserved_assessment = existing_attempt.lastAssessment
            if last_assessment:
                assessment_count += 1
                preserved_assessment = assessment_decimal

            item: Dict[str, Any] = {
                "userId": user_id,
                "problemId": problem_id,
                "title": title,
                "difficulty": difficulty or "Medium",
                "category": category or "General",
                "nodes": nodes_decimal,
                "edges": edges_decimal,
                "elapsedTime": elapsed_time,
                "lastAssessment": preserved_assessment,  # Preserve existing assessment if not updating
                "assessmentCount": assessment_count,
                "updatedAt": now,
                "lastAttemptedAt": now,
            }

            # Only set createdAt for new attempts
            if not existing_attempt:
                item["createdAt"] = now
            else:
                item["createdAt"] = existing_attempt.createdAt

            self.attempts_table.put_item(Item=item)

            return AttemptResponse(
                id=f"{user_id}#{problem_id}",  # Composite ID for frontend
                userId=user_id,
                problemId=problem_id,
                title=title,
                difficulty=difficulty or "Medium",
                category=category or "General",
                nodes=nodes,
                edges=edges,
                elapsedTime=elapsed_time,
                lastAssessment=last_assessment,
                assessmentCount=assessment_count,
                createdAt=item["createdAt"],
                updatedAt=now,
                lastAttemptedAt=now,
            )
        except ClientError as e:
            print(f"Error creating/updating attempt: {e}")
            raise

    def get_attempt_by_problem(
        self, user_id: str, problem_id: str
    ) -> Optional[AttemptResponse]:
        """Get a user's attempt for a specific problem using direct key lookup."""
        try:
            response = self.attempts_table.get_item(
                Key={"userId": user_id, "problemId": problem_id}
            )

            item = response.get("Item")
            if item:
                print(
                    f"Retrieved item from DynamoDB: lastAssessment = {item.get('lastAssessment')}"
                )
                item_float: Dict[str, Any] = convert_decimal_to_float(item)
                print(
                    f"After decimal conversion: lastAssessment = {item_float.get('lastAssessment')}"
                )
                # Add composite ID for frontend compatibility
                item_float["id"] = f"{user_id}#{problem_id}"
                result = AttemptResponse(**item_float)
                print(f"AttemptResponse: lastAssessment = {result.lastAssessment}")
                return result

            return None
        except ClientError as e:
            print(f"Error getting attempt: {e}")
            return None

    def get_user_attempts(self, user_id: str) -> List[AttemptResponse]:
        """Get all attempts for a user using partition key query."""
        try:
            items: List[Dict[str, Any]] = []
            response = self.attempts_table.query(
                KeyConditionExpression=Key("userId").eq(user_id)
            )
            response_items = response.get("Items", [])
            items.extend(response_items)

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.attempts_table.query(
                    KeyConditionExpression=Key("userId").eq(user_id),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                response_items = response.get("Items", [])
                items.extend(response_items)

            # Convert Decimal back to float and add composite ID for frontend compatibility
            items_float = [convert_decimal_to_float(item) for item in items]
            for item in items_float:
                item["id"] = f"{item['userId']}#{item['problemId']}"
            return [AttemptResponse(**item) for item in items_float]
        except ClientError as e:
            print(f"Error querying attempts: {e}")
            return []

    def delete_attempt(self, user_id: str, problem_id: str) -> bool:
        """Delete a problem attempt using composite key."""
        try:
            self.attempts_table.delete_item(
                Key={"userId": user_id, "problemId": problem_id}
            )
            return True
        except ClientError:
            return False


# Global DynamoDB service instance
dynamodb_service = DynamoDBService()
