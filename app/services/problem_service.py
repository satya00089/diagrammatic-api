"""MongoDB database service for problems collection."""

from typing import List, Optional
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from app.utils.config import get_settings
from app.models.problem_models import ProblemSummary, ProblemDetail

logger = logging.getLogger(__name__)


class ProblemService:
    """Service class for problem database operations."""

    def __init__(self):
        self.settings = get_settings()
        print(f"ProblemService initialized with settings: {self.settings}")
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.collection = None

    async def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.settings.mongodb_uri)
            self.db = self.client[self.settings.mongo_dbname]
            self.collection = self.db[self.settings.mongo_collname]
            # Test the connection
            await self.client.admin.command("ping")
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error("Failed to connect to MongoDB: %s", e)
            # Ensure we drop half-open client
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
                self.client = None
            self.db = None
            self.collection = None
            raise

    def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
        self.client = None
        self.db = None
        self.collection = None

    async def ensure_connected(self):
        """Ensure there is a healthy connection; recreate if loop changed or closed.

        Handles serverless environments where the event loop may be recycled and the
        underlying Motor client becomes bound to a closed loop, triggering
        'Event loop is closed' errors on use.
        """
        if self.client is None:
            await self.connect()
            return
        try:
            await self.client.admin.command("ping")
        except Exception as e:
            # Any issue -> rebuild client
            warn_msg = f"Reinitializing MongoDB client after ping failure: {e}"  # noqa: E501
            logger.warning(warn_msg)
            self.disconnect()
            await self.connect()

    async def get_all_problems(self) -> List[ProblemSummary]:
        """Get all problems with summary information."""
        try:
            await self.ensure_connected()
            # Project only the fields needed for summary
            print(f"ProblemService initialized with settings: {self.settings}")
            projection = {
                "_id": 0,
                "id": 1,
                "title": 1,
                "description": 1,
                "difficulty": 1,
                "category": 1,
                "estimated_time": 1,
                "estimatedTime": 1,  # Handle both field names
                "tags": 1,
                "companies": 1,
            }
            print(f'connection: {self.client}, db: {self.db}, collection: {self.collection}')
            cursor = self.collection.find({}, projection)
            problems = []

            async for doc in cursor:
                # Handle both estimated_time and estimatedTime field names
                if "estimated_time" not in doc and "estimatedTime" in doc:
                    doc["estimated_time"] = doc["estimatedTime"]
                elif "estimatedTime" not in doc and "estimated_time" in doc:
                    doc["estimatedTime"] = doc["estimated_time"]

                problems.append(ProblemSummary(**doc))

            return problems
        except Exception as e:
            logger.error("Error fetching all problems: %s", e)
            raise

    async def get_problem_by_id(self, problem_id: str) -> Optional[ProblemDetail]:
        """Get a specific problem by ID with full details."""
        try:
            await self.ensure_connected()
            doc = await self.collection.find_one(
                {"id": problem_id}, {"_id": 0}  # Exclude MongoDB _id field
            )

            if doc:
                # Handle both estimated_time and estimatedTime field names
                if "estimated_time" not in doc and "estimatedTime" in doc:
                    doc["estimated_time"] = doc["estimatedTime"]
                elif "estimatedTime" not in doc and "estimated_time" in doc:
                    doc["estimatedTime"] = doc["estimated_time"]

                return ProblemDetail(**doc)
            return None
        except Exception as e:
            logger.error("Error fetching problem %s: %s", problem_id, e)
            raise

    async def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            await self.ensure_connected()
            return True
        except PyMongoError as e:
            logger.error("Database health check failed: %s", e)
            return False


# Global instance (lazy-initialized)
problem_service = ProblemService()


def get_problem_service() -> ProblemService:
    """Dependency to get problem service instance."""
    return problem_service
