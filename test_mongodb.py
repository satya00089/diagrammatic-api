#!/usr/bin/env python3
"""Test script for MongoDB problem API endpoints."""

import asyncio
from app.services.problem_service import ProblemService
from app.models.problem_models import ProblemSummary, ProblemDetail

async def test_mongodb_connection():
    """Test MongoDB connection and basic operations."""
    print("🧪 Testing MongoDB Integration...")
    
    service = ProblemService()
    
    try:
        # Test connection
        print("📡 Connecting to MongoDB...")
        await service.connect()
        print("✅ MongoDB connection successful!")
        
        # Test health check
        print("🏥 Testing health check...")
        is_healthy = await service.health_check()
        print(f"✅ Health check: {'Healthy' if is_healthy else 'Unhealthy'}")
        
        # Test fetching all problems
        print("📋 Fetching all problems...")
        try:
            problems = await service.get_all_problems()
            print(f"✅ Found {len(problems)} problems")
            
            if problems:
                first_problem = problems[0]
                print(f"📄 First problem: {first_problem.title}")
                
                # Test fetching specific problem
                print(f"🔍 Fetching problem details for: {first_problem.id}")
                problem_detail = await service.get_problem_by_id(first_problem.id)
                
                if problem_detail:
                    print(f"✅ Problem details retrieved: {problem_detail.title}")
                    print(f"   Requirements: {len(problem_detail.requirements)}")
                    print(f"   Constraints: {len(problem_detail.constraints)}")
                    print(f"   Hints: {len(problem_detail.hints)}")
                else:
                    print("❌ Problem details not found")
        except Exception as e:
            print(f"⚠️  Error fetching problems: {e}")
            
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
    finally:
        await service.disconnect()
        print("👋 Disconnected from MongoDB")

if __name__ == "__main__":
    asyncio.run(test_mongodb_connection())
