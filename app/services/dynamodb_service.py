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

    # User operations
    def create_user(
        self,
        email: str,
        password_hash: Optional[str] = None,
        name: Optional[str] = None,
        google_id: Optional[str] = None,
    ) -> User:
        """Create a new user in DynamoDB."""
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
        if google_id:
            item["googleId"] = google_id

        self.users_table.put_item(Item=item)

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

        print(f"Creating diagram with ID: {diagram_id}, userId: {user_id}, title: {title}")
        self.diagrams_table.put_item(Item=item)
        print(f"Diagram created successfully")

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
            print(f"Query for userId={user_id}: Found {len(response_items)} items in first page")
            items.extend(response_items)
            
            # Continue fetching if there are more pages
            while "LastEvaluatedKey" in response:
                response = self.diagrams_table.query(
                    KeyConditionExpression=Key("userId").eq(user_id),
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                response_items = response.get("Items", [])
                print(f"Fetched {len(response_items)} more items from next page")
                items.extend(response_items)
            
            print(f"Total items retrieved: {len(items)}")
            for item in items:
                print(f"  - Diagram ID: {item.get('id')}, Title: {item.get('title')}")
            
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


# Global DynamoDB service instance
dynamodb_service = DynamoDBService()
