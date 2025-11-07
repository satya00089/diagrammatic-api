"""WebSocket router for real-time collaboration on diagrams."""

import json
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.dynamodb_service import dynamodb_service
from app.services.validation import validate_diagram_access
from app.services.auth_service import auth_service

router = APIRouter()

# Store active connections: diagram_id -> list of (websocket, user_id)
active_connections: Dict[str, List[tuple]] = {}

# Debounced save tracking: diagram_id -> (last_update_time, pending_data, save_task)
debounced_saves: Dict[str, tuple] = {}


class RateLimiter:
    """Simple rate limiter using sliding window with burst allowance."""

    def __init__(self, max_per_second: float, burst_allowance: int = 10):
        self.max_per_second = max_per_second
        self.burst_allowance = burst_allowance
        self.timestamps: List[float] = []

    def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()

        # Remove old timestamps outside the 1-second window
        self.timestamps = [t for t in self.timestamps if now - t < 1]

        # Allow bursts up to burst_allowance, but enforce average rate
        if len(self.timestamps) >= self.max_per_second + self.burst_allowance:
            return False

        self.timestamps.append(now)
        return True


# Rate limiters per user: user_id -> message_type -> RateLimiter
user_rate_limiters: Dict[str, Dict[str, RateLimiter]] = {}


def get_rate_limiter(user_id: str, message_type: str) -> RateLimiter:
    """Get or create rate limiter for user and message type."""
    if user_id not in user_rate_limiters:
        user_rate_limiters[user_id] = {}

    if message_type not in user_rate_limiters[user_id]:
        # Set rate limits based on message type
        if message_type == "cursor_move":
            # Allow high frequency cursor updates for smooth tracking
            # Average: 120/s, Burst: up to 50 messages
            user_rate_limiters[user_id][message_type] = RateLimiter(120, 50)
        elif message_type == "diagram_update":
            # More restrictive for diagram updates to prevent spam
            user_rate_limiters[user_id][message_type] = RateLimiter(10, 5)
        elif message_type == "ping":
            # Very restrictive for ping to prevent abuse
            user_rate_limiters[user_id][message_type] = RateLimiter(1, 0)
        else:
            # Default rate limit
            user_rate_limiters[user_id][message_type] = RateLimiter(10, 2)

    return user_rate_limiters[user_id][message_type]


def validate_message(message_type: str, data: Dict[str, Any]) -> tuple[bool, str]:
    """Validate message format and required fields."""
    try:
        if message_type == "cursor_move":
            if "position" not in data:
                return False, "Missing 'position' field"
            position = data["position"]
            if (
                not isinstance(position, dict)
                or "x" not in position
                or "y" not in position
            ):
                return (
                    False,
                    "Invalid 'position' format, must contain 'x' and 'y' coordinates",
                )
            if not isinstance(position["x"], (int, float)) or not isinstance(
                position["y"], (int, float)
            ):
                return False, "Position coordinates must be numbers"

        elif message_type == "diagram_update":
            if "data" not in data:
                return False, "Missing 'data' field"

        elif message_type == "ping":
            pass  # No specific validation needed

        # Validate timestamp if present
        if "timestamp" in data:
            try:
                datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return False, "Invalid timestamp format"

        return True, ""

    except Exception as e:
        return False, f"Message validation error: {str(e)}"


async def debounced_save_diagram(
    diagram_id: str, user_id: str, update_data: Dict[str, Any]
):
    """Save diagram updates with debouncing (5-second delay)."""
    current_time = time.time()

    # Cancel any existing save task for this diagram
    if diagram_id in debounced_saves:
        _, _, existing_task = debounced_saves[diagram_id]
        if not existing_task.done():
            existing_task.cancel()

    # Schedule new save task
    async def save_after_delay():
        await asyncio.sleep(5)  # 5 second debounce
        try:
            # Extract update data
            nodes = update_data.get("nodes")
            edges = update_data.get("edges")
            title = update_data.get("title")
            description = update_data.get("description")

            # Get the diagram to find the owner
            diagram = dynamodb_service.get_diagram(user_id, diagram_id)
            if not diagram:
                # Find in shared diagrams
                shared_diagrams = dynamodb_service.get_shared_diagrams_for_user(user_id)
                diagram = next((d for d in shared_diagrams if d.id == diagram_id), None)

            if diagram:
                # Update the diagram
                dynamodb_service.update_diagram(
                    user_id=diagram.userId,  # Use owner ID
                    diagram_id=diagram_id,
                    title=title,
                    description=description,
                    nodes=nodes,
                    edges=edges,
                )
                print(f"✅ Debounced save completed for diagram {diagram_id}")
            else:
                print(f"❌ Diagram {diagram_id} not found during debounced save")

        except Exception as e:
            print(f"❌ Failed debounced save for diagram {diagram_id}: {str(e)}")
        finally:
            # Clean up tracking
            if diagram_id in debounced_saves:
                del debounced_saves[diagram_id]

    # Create and track the save task
    save_task = asyncio.create_task(save_after_delay())
    debounced_saves[diagram_id] = (current_time, update_data, save_task)


async def notify_collaborators(
    diagram_id: str, message: Dict[str, Any], exclude_user_id: str = None
):
    """Notify all collaborators of a diagram about changes."""
    if diagram_id not in active_connections:
        return

    disconnected = []
    for websocket, user_id in active_connections[diagram_id]:
        if exclude_user_id and user_id == exclude_user_id:
            continue

        try:
            await websocket.send_json(message)
        except Exception:
            # Connection is dead, mark for removal
            disconnected.append((websocket, user_id))

    # Remove disconnected clients
    for websocket, user_id in disconnected:
        if websocket in [w for w, u in active_connections[diagram_id]]:
            active_connections[diagram_id].remove((websocket, user_id))


@router.websocket("/diagrams/{diagram_id}/collaborate")
async def collaborate_on_diagram(
    websocket: WebSocket,
    diagram_id: str,
    token: str = None,
):
    """WebSocket endpoint for real-time collaboration on diagrams."""
    await websocket.accept()

    user_id = None
    try:
        # Authenticate user
        if not token:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Authentication required",
                    "code": "INVALID_TOKEN",
                }
            )
            await websocket.close(code=1008)
            return

        # Decode and validate JWT token
        try:
            payload = auth_service.decode_token(token)
            user_id = payload.get("user_id")
            if not user_id:
                raise ValueError("Invalid token payload")
        except (ValueError, TypeError):
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Invalid or expired token",
                    "code": "INVALID_TOKEN",
                }
            )
            await websocket.close(code=1008)
            return

        # Validate access to diagram
        has_access, error_msg = validate_diagram_access(user_id, diagram_id, "read")
        if not has_access:
            await websocket.send_json(
                {"type": "error", "message": error_msg, "code": "PERMISSION_DENIED"}
            )
            await websocket.close(code=1008)
            return

        # Get full user information for broadcasting
        user = dynamodb_service.get_user_by_id(user_id)
        if not user:
            await websocket.send_json(
                {"type": "error", "message": "User not found", "code": "INVALID_TOKEN"}
            )
            await websocket.close(code=1008)
            return

        user_info = {
            "id": user.id,
            "name": user.name or "Anonymous",
            "email": user.email,
            "pictureUrl": user.picture or None,
        }

        # Add to active connections
        if diagram_id not in active_connections:
            active_connections[diagram_id] = []
        active_connections[diagram_id].append((websocket, user_id))

        # Get current collaborators (other users in the same diagram)
        collaborators = []
        for ws, uid in active_connections[diagram_id]:
            if uid != user_id:
                collab_user = dynamodb_service.get_user_by_id(uid)
                if collab_user:
                    collaborators.append(
                        {
                            "id": collab_user.id,
                            "name": collab_user.name or "Anonymous",
                            "email": collab_user.email,
                            "pictureUrl": collab_user.picture or None,
                        }
                    )

        # Get current diagram data
        diagram_data = None
        is_owner = False
        user_permission = None
        owner_info = None

        try:
            diagram = dynamodb_service.get_diagram(user_id, diagram_id)
            if diagram:
                is_owner = True
            else:
                # Find in shared diagrams
                shared_diagrams = dynamodb_service.get_shared_diagrams_for_user(user_id)
                diagram = next((d for d in shared_diagrams if d.id == diagram_id), None)

            if diagram:
                # Get user's permission level
                if is_owner:
                    user_permission = "owner"
                else:
                    # Find user's permission from collaborators list
                    for collab in diagram.collaborators or []:
                        if collab.userId == user_id:
                            user_permission = collab.permission.value
                            break

                # Get owner information
                if diagram.userId:
                    owner = dynamodb_service.get_user_by_id(diagram.userId)
                    if owner:
                        owner_info = {
                            "id": owner.id,
                            "name": owner.name or "Anonymous",
                            "email": owner.email,
                            "pictureUrl": owner.picture or None,
                        }

                diagram_data = {
                    "id": diagram.id,
                    "title": diagram.title or "Untitled Diagram",
                    "description": diagram.description,
                    "nodes": diagram.nodes or [],
                    "edges": diagram.edges or [],
                    "isOwner": is_owner,
                    "permission": user_permission,
                    "owner": owner_info,
                    "createdAt": diagram.createdAt,
                    "updatedAt": diagram.updatedAt,
                }
        except Exception as e:
            # If we can't get diagram data, continue without it
            print(f"❌ Failed to get diagram data: {str(e)}")
            pass

        # Notify others that user joined
        await notify_collaborators(
            diagram_id,
            {
                "type": "user_joined",
                "user": user_info,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            exclude_user_id=user_id,
        )

        # Send welcome message with collaborators and diagram data
        welcome_message = {
            "type": "welcome",
            "user": user_info,
            "collaborators": collaborators,
            "rateLimits": {
                "cursorMove": {"average": 120, "burst": 50},
                "diagramUpdate": {"average": 10, "burst": 5},
                "ping": {"average": 1, "burst": 0},
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if diagram_data:
            welcome_message["diagram"] = diagram_data

        await websocket.send_json(welcome_message)

        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                message_type = data.get("type")

                # Validate message format
                is_valid, validation_error = validate_message(message_type, data)
                if not is_valid:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": validation_error,
                            "code": "INVALID_MESSAGE_FORMAT",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    continue

                # Apply rate limiting
                rate_limiter = get_rate_limiter(user_id, message_type)
                if not rate_limiter.is_allowed():
                    # For cursor_move, don't spam the client with errors - just drop the message
                    # This prevents UI disruption while maintaining smooth cursor tracking
                    if message_type == "cursor_move":
                        continue  # Silently drop cursor updates when rate limited
                    else:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"Rate limit exceeded for {message_type}",
                                "code": "RATE_LIMIT_EXCEEDED",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        continue

                if message_type == "diagram_update":
                    # Validate edit permission
                    has_edit_access, error_msg = validate_diagram_access(
                        user_id, diagram_id, "update"
                    )
                    if not has_edit_access:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": error_msg,
                                "code": "PERMISSION_DENIED",
                            }
                        )
                        continue

                    # Broadcast the update to all collaborators
                    update_data = {
                        "type": "diagram_update",
                        "user": user_info,
                        "data": data.get("data", {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    # Schedule debounced save to database
                    try:
                        await debounced_save_diagram(
                            diagram_id, user_id, data.get("data", {})
                        )

                        # Broadcast to all collaborators
                        await notify_collaborators(diagram_id, update_data)
                    except Exception as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"Failed to process update: {str(e)}",
                                "code": "INTERNAL_ERROR",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )

                elif message_type == "cursor_move":
                    # Broadcast cursor position to other collaborators
                    cursor_data = {
                        "type": "cursor_move",
                        "user": user_info,
                        "position": data.get("position", {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await notify_collaborators(
                        diagram_id, cursor_data, exclude_user_id=user_id
                    )

                elif message_type == "ping":
                    # Respond to ping
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}",
                            "code": "UNKNOWN_MESSAGE_TYPE",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Invalid JSON received",
                        "code": "INVALID_MESSAGE_FORMAT",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        pass

    finally:
        # Remove from active connections
        if diagram_id in active_connections and user_id:
            connections = active_connections[diagram_id]
            active_connections[diagram_id] = [
                (ws, uid) for ws, uid in connections if uid != user_id
            ]

            # Clean up empty diagram connections
            if not active_connections[diagram_id]:
                del active_connections[diagram_id]

            # Notify others that user left
            await notify_collaborators(
                diagram_id,
                {
                    "type": "user_left",
                    "user": user_info,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
