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
from app.models.diagram_models import Diagram

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
                updated_user = self.update_user_google_id(existing_user.id, google_id, picture)
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
                Item=item,
                ConditionExpression="attribute_not_exists(id)"
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')  # type: ignore[union-attr]
            if error_code == 'ConditionalCheckFailedException':
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

    def update_user_google_id(self, user_id: str, google_id: str, picture: Optional[str] = None) -> Optional[User]:
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
                    ExclusiveStartKey=response["LastEvaluatedKey"]
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
                KeyConditionExpression=Key("category").eq(category)
            )
            items.extend(response.get("Items", []))
            
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.problems_table.query(
                    IndexName="category-index",
                    KeyConditionExpression=Key("category").eq(category),
                    ExclusiveStartKey=response["LastEvaluatedKey"]
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
                KeyConditionExpression=Key("difficulty").eq(difficulty)
            )
            items.extend(response.get("Items", []))
            
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.problems_table.query(
                    IndexName="difficulty-index",
                    KeyConditionExpression=Key("difficulty").eq(difficulty),
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))
            
            return items
        except ClientError:
            return []


# Global DynamoDB service instance
dynamodb_service = DynamoDBService()
