"""
Components Service
Handles DynamoDB operations for component management
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import boto3
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
from boto3.dynamodb.conditions import Key, Attr
from app.utils.config import get_settings

settings = get_settings()


class ComponentsService:
    """Service for managing components in DynamoDB"""
    def __init__(self):
        """Initialize DynamoDB client and table"""
        self.dynamodb: DynamoDBServiceResource = boto3.resource(
            'dynamodb',
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        self.table_name = settings.components_table_name
        self.table = self.dynamodb.Table(self.table_name)

    def get_components_by_provider(
        self,
        provider: str,
        category: Optional[str] = None,
        limit: int = 100,
        last_evaluated_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get components filtered by provider and optionally by category
        
        Args:
            provider: Provider name (aws, azure, gcp, kubernetes, etc.)
            category: Optional category filter (storage, compute, etc.)
            limit: Maximum number of items to return
            last_evaluated_key: Pagination key
            
        Returns:
            Dict with items and pagination info
        """
        try:
            # Build query parameters
            query_params: Dict[str, Any] = {
                'IndexName': 'ProviderIndex',
                'KeyConditionExpression': Key('provider').eq(provider),
                'Limit': limit,
                'FilterExpression': Attr('isActive').eq(True)
            }

            # Add category filter if provided
            if category:
                query_params['FilterExpression'] = query_params['FilterExpression'] & Attr('category').eq(category)

            # Add pagination if provided
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key

            # Execute query
            response = self.table.query(**query_params)

            return {
                'items': response.get('Items', []),
                'lastEvaluatedKey': response.get('LastEvaluatedKey'),
                'count': response.get('Count', 0)
            }

        except Exception as e:
            print(f"Error querying components by provider: {e}")
            raise

    def get_components_by_category(
        self,
        category: str,
        provider: Optional[str] = None,
        limit: int = 100,
        last_evaluated_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get components filtered by category and optionally by provider
        
        Args:
            category: Category name (storage, compute, database, etc.)
            provider: Optional provider filter
            limit: Maximum number of items to return
            last_evaluated_key: Pagination key
            
        Returns:
            Dict with items and pagination info
        """
        try:
            # Build query parameters
            query_params: Dict[str, Any] = {
                'IndexName': 'CategoryIndex',
                'KeyConditionExpression': Key('category').eq(category),
                'Limit': limit,
                'FilterExpression': Attr('isActive').eq(True)
            }

            # Add provider filter if provided
            if provider:
                query_params['FilterExpression'] = query_params['FilterExpression'] & Attr('provider').eq(provider)

            # Add pagination if provided
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key

            # Execute query
            response = self.table.query(**query_params)

            return {
                'items': response.get('Items', []),
                'lastEvaluatedKey': response.get('LastEvaluatedKey'),
                'count': response.get('Count', 0)
            }

        except Exception as e:
            print(f"Error querying components by category: {e}")
            raise

    def search_components(
        self,
        search_term: str,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Search components by name, displayName, description, or tags
        
        Args:
            search_term: Search query
            provider: Optional provider filter
            category: Optional category filter
            limit: Maximum number of items to return
            
        Returns:
            Dict with matching items
        """
        try:
            # Build scan parameters (Note: Scan is less efficient than Query)
            # For production, consider using ElasticSearch or DynamoDB Streams + Lambda
            scan_params: Dict[str, Any] = {
                'Limit': limit,
                'FilterExpression': Attr('isActive').eq(True)
            }

            # Add search filter
            search_lower = search_term.lower()
            search_filter = (
                Attr('name').contains(search_lower) |
                Attr('displayName').contains(search_term) |
                Attr('description').contains(search_term) |
                Attr('tags').contains(search_lower)
            )

            # Combine with existing filter
            scan_params['FilterExpression'] = scan_params['FilterExpression'] & search_filter

            # Add provider filter if provided
            if provider:
                scan_params['FilterExpression'] = scan_params['FilterExpression'] & Attr('provider').eq(provider)

            # Add category filter if provided
            if category:
                scan_params['FilterExpression'] = scan_params['FilterExpression'] & Attr('category').eq(category)

            # Execute scan
            response = self.table.scan(**scan_params)

            return {
                'items': response.get('Items', []),
                'count': response.get('Count', 0)
            }

        except Exception as e:
            print(f"Error searching components: {e}")
            raise

    def get_component_by_id(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single component by ID
        
        Args:
            component_id: Component ID (format: {platform}-{component-name})
            
        Returns:
            Component data or None if not found
        """
        try:
            # Extract platform from component ID (e.g., "aws-s3" -> "aws")
            platform_prefix = component_id.split('-')[0].lower() if '-' in component_id else ''
            
            # Map platform prefix to platform name (matching DynamoDB values)
            platform_map = {
                'aws': 'AWS',
                'azure': 'Azure',
                'gcp': 'GCP',
                'kubernetes': 'Kubernetes',
                'k8s': 'Kubernetes'
            }
            
            platform = platform_map.get(platform_prefix, platform_prefix.capitalize())
            
            # Use composite key (platform + id) for get_item
            response = self.table.get_item(
                Key={
                    'platform': platform,
                    'id': component_id
                }
            )
            return response.get('Item')

        except Exception as e:
            print(f"Error getting component by ID: {e}")
            raise

    def get_all_components(
        self,
        limit: int = 100,
        last_evaluated_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get all active components
        
        Args:
            limit: Maximum number of items to return
            last_evaluated_key: Pagination key
            
        Returns:
            Dict with items and pagination info
        """
        try:
            scan_params: Dict[str, Any] = {
                'Limit': limit,
                'FilterExpression': Attr('isActive').eq(True)
            }

            if last_evaluated_key:
                scan_params['ExclusiveStartKey'] = last_evaluated_key

            response = self.table.scan(**scan_params)

            return {
                'items': response.get('Items', []),
                'lastEvaluatedKey': response.get('LastEvaluatedKey'),
                'count': response.get('Count', 0)
            }

        except Exception as e:
            print(f"Error getting all components: {e}")
            raise

    def increment_usage_count(self, component_id: str) -> Dict[str, Any]:
        """
        Increment the usage count for a component
        
        Args:
            component_id: Component ID (format: {platform}-{component-name})
            
        Returns:
            Updated component data
        """
        try:
            # Extract platform from component ID
            platform_prefix = component_id.split('-')[0].lower() if '-' in component_id else ''
            
            # Map platform prefix to platform name
            platform_map = {
                'aws': 'AWS',
                'azure': 'Azure',
                'gcp': 'GCP',
                'kubernetes': 'Kubernetes',
                'k8s': 'Kubernetes'
            }
            
            platform = platform_map.get(platform_prefix, platform_prefix.capitalize())
            
            response = self.table.update_item(
                Key={
                    'platform': platform,
                    'id': component_id
                },
                UpdateExpression='SET usageCount = if_not_exists(usageCount, :zero) + :inc, updatedAt = :timestamp',
                ExpressionAttributeValues={
                    ':inc': 1,
                    ':zero': 0,
                    ':timestamp': datetime.now(timezone.utc).isoformat()
                },
                ReturnValues='ALL_NEW'
            )
            return response.get('Attributes', {})

        except Exception as e:
            print(f"Error incrementing usage count: {e}")
            raise

    def get_providers(self) -> List[str]:
        """
        Get list of unique providers
        
        Returns:
            List of provider names
        """
        try:
            # Scan and collect unique providers
            # For production, consider maintaining a separate table or cache
            response = self.table.scan(
                ProjectionExpression='provider',
                FilterExpression=Attr('isActive').eq(True)
            )

            providers: set[str] = set()
            for item in response.get('Items', []):
                if 'provider' in item:
                    providers.add(str(item['provider']))

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    ProjectionExpression='provider',
                    FilterExpression=Attr('isActive').eq(True),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                for item in response.get('Items', []):
                    if 'provider' in item:
                        providers.add(str(item['provider']))

            return sorted(providers)

        except Exception as e:
            print(f"Error getting providers: {e}")
            raise

    def get_categories(self) -> List[str]:
        """
        Get list of unique categories
        
        Returns:
            List of category names
        """
        try:
            # Scan and collect unique categories
            response = self.table.scan(
                ProjectionExpression='category',
                FilterExpression=Attr('isActive').eq(True)
            )

            categories: set[str] = set()
            for item in response.get('Items', []):
                if 'category' in item:
                    categories.add(str(item['category']))

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    ProjectionExpression='category',
                    FilterExpression=Attr('isActive').eq(True),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                for item in response.get('Items', []):
                    if 'category' in item:
                        categories.add(str(item['category']))

            return sorted(categories)

        except Exception as e:
            print(f"Error getting categories: {e}")
            raise


# Singleton instance
components_service = ComponentsService()
