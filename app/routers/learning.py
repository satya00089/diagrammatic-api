"""
Learning Progress Router
Handles user progress tracking for learning modules
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.services.dynamodb_service import dynamodb_service
from app.models.user import User, get_current_user
from boto3.dynamodb.conditions import Key

router = APIRouter(prefix="/learning", tags=["learning"])


class UserProgress(BaseModel):
    userId: str
    moduleId: str
    lessonId: str
    completed: bool
    score: Optional[int] = None
    completedAt: Optional[datetime] = None
    diagramSnapshot: Optional[dict] = None
    timeSpent: Optional[int] = None  # in seconds


class ModuleProgress(BaseModel):
    moduleId: str
    completedLessons: List[str]
    totalLessons: int
    progress: float
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None


class Achievement(BaseModel):
    id: str
    title: str
    description: str
    icon: str
    unlockedAt: Optional[datetime] = None
    type: str


class LearningStats(BaseModel):
    totalModules: int
    completedModules: int
    totalLessons: int
    completedLessons: int
    totalTimeSpent: int
    streak: int
    achievements: List[Achievement]


@router.get("/progress/{user_id}", response_model=List[UserProgress])
async def get_user_progress(user_id: str):
    """Get all progress records for a user"""
    try:
        table = dynamodb_client.Table("UserLearningProgress")
        response = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
        return response.get("Items", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/progress", response_model=UserProgress)
async def save_progress(progress: UserProgress):
    """Save or update user progress for a lesson"""
    try:
        table = dynamodb_client.Table("UserLearningProgress")
        
        # Create composite key
        progress_id = f"{progress.moduleId}#{progress.lessonId}"
        
        item = {
            "userId": progress.userId,
            "progressId": progress_id,
            "moduleId": progress.moduleId,
            "lessonId": progress.lessonId,
            "completed": progress.completed,
            "completedAt": progress.completedAt.isoformat() if progress.completedAt else datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
        }
        
        if progress.score is not None:
            item["score"] = progress.score
        if progress.timeSpent is not None:
            item["timeSpent"] = progress.timeSpent
        if progress.diagramSnapshot:
            item["diagramSnapshot"] = progress.diagramSnapshot
        
        table.put_item(Item=item)
        return progress
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{user_id}", response_model=LearningStats)
async def get_learning_stats(user_id: str):
    """Get overall learning statistics for a user"""
    try:
        table = dynamodb_client.Table("UserLearningProgress")
        response = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
        
        progress_items = response.get("Items", [])
        
        # Calculate stats
        completed_lessons = [p for p in progress_items if p.get("completed", False)]
        total_time = sum(p.get("timeSpent", 0) for p in progress_items)
        
        # Get unique modules
        modules = set(p.get("moduleId") for p in progress_items)
        
        # Calculate completed modules (all lessons in module completed)
        # This is simplified - in production, you'd check against actual module structure
        completed_modules = len(set(p.get("moduleId") for p in completed_lessons))
        
        # Calculate streak (simplified)
        streak = calculate_streak(progress_items)
        
        # Get achievements
        achievements = await get_user_achievements(user_id)
        
        return LearningStats(
            totalModules=len(modules),
            completedModules=completed_modules,
            totalLessons=len(progress_items),
            completedLessons=len(completed_lessons),
            totalTimeSpent=total_time,
            streak=streak,
            achievements=achievements,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/module-progress/{user_id}/{module_id}", response_model=ModuleProgress)
async def get_module_progress(user_id: str, module_id: str):
    """Get progress for a specific module"""
    try:
        table = dynamodb_client.Table("UserLearningProgress")
        response = table.query(
            KeyConditionExpression=Key("userId").eq(user_id),
            FilterExpression="moduleId = :mid",
            ExpressionAttributeValues={":mid": module_id}
        )
        
        items = response.get("Items", [])
        completed = [p["lessonId"] for p in items if p.get("completed", False)]
        
        # Get started and completed dates
        started_at = min((p.get("updatedAt") for p in items), default=None) if items else None
        completed_at = None
        if items and all(p.get("completed", False) for p in items):
            completed_at = max((p.get("completedAt") for p in items), default=None)
        
        return ModuleProgress(
            moduleId=module_id,
            completedLessons=completed,
            totalLessons=len(items),
            progress=(len(completed) / len(items) * 100) if items else 0,
            startedAt=started_at,
            completedAt=completed_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def calculate_streak(progress_items: List[dict]) -> int:
    """Calculate consecutive days of learning"""
    if not progress_items:
        return 0
    
    # Sort by date
    dates = sorted(set(
        datetime.fromisoformat(p.get("completedAt", "")).date()
        for p in progress_items
        if p.get("completedAt")
    ), reverse=True)
    
    if not dates:
        return 0
    
    streak = 1
    for i in range(len(dates) - 1):
        diff = (dates[i] - dates[i + 1]).days
        if diff == 1:
            streak += 1
        else:
            break
    
    return streak


async def get_user_achievements(user_id: str) -> List[Achievement]:
    """Get all achievements for a user"""
    try:
        table = dynamodb_client.Table("UserAchievements")
        response = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
        
        items = response.get("Items", [])
        return [
            Achievement(
                id=item["achievementId"],
                title=item["title"],
                description=item["description"],
                icon=item["icon"],
                unlockedAt=datetime.fromisoformat(item["unlockedAt"]) if item.get("unlockedAt") else None,
                type=item["type"],
            )
            for item in items
        ]
    except Exception:
        # Return empty list if table doesn't exist yet
        return []


@router.post("/achievements/{user_id}/{achievement_id}")
async def unlock_achievement(user_id: str, achievement_id: str):
    """Unlock an achievement for a user"""
    try:
        table = dynamodb_client.Table("UserAchievements")
        
        # Define achievements
        achievements_catalog = {
            "first_lesson": {
                "title": "First Steps",
                "description": "Complete your first lesson",
                "icon": "🎓",
                "type": "lesson",
            },
            "first_module": {
                "title": "Module Master",
                "description": "Complete your first module",
                "icon": "📚",
                "type": "module",
            },
            "week_streak": {
                "title": "Dedicated Learner",
                "description": "Learn for 7 days in a row",
                "icon": "🔥",
                "type": "streak",
            },
            "perfect_score": {
                "title": "Perfectionist",
                "description": "Get a perfect score on an exercise",
                "icon": "⭐",
                "type": "special",
            },
        }
        
        achievement = achievements_catalog.get(achievement_id)
        if not achievement:
            raise HTTPException(status_code=404, detail="Achievement not found")
        
        item = {
            "userId": user_id,
            "achievementId": achievement_id,
            "title": achievement["title"],
            "description": achievement["description"],
            "icon": achievement["icon"],
            "type": achievement["type"],
            "unlockedAt": datetime.utcnow().isoformat(),
        }
        
        table.put_item(Item=item)
        return {"message": "Achievement unlocked!", "achievement": achievement}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
