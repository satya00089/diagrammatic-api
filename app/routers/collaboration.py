"""WebSocket router for real-time collaboration on diagrams."""

import json
from typing import Dict, List, Any
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.dynamodb_service import dynamodb_service
from app.services.validation import validate_diagram_access
from app.services.auth_service import auth_service

router = APIRouter()

# Store active connections: diagram_id -> list of (websocket, user_id)
active_connections: Dict[str, List[tuple]] = {}


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
                {"type": "error", "message": "Authentication required"}
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
                {"type": "error", "message": "Invalid or expired token"}
            )
            await websocket.close(code=1008)
            return

        # Validate access to diagram
        has_access, error_msg = validate_diagram_access(user_id, diagram_id, "read")
        if not has_access:
            await websocket.send_json({"type": "error", "message": error_msg})
            await websocket.close(code=1008)
            return

        # Add to active connections
        if diagram_id not in active_connections:
            active_connections[diagram_id] = []
        active_connections[diagram_id].append((websocket, user_id))

        # Notify others that user joined
        await notify_collaborators(
            diagram_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            exclude_user_id=user_id,
        )

        # Send welcome message
        await websocket.send_json(
            {
                "type": "welcome",
                "message": f"Connected to diagram {diagram_id}",
                "user_id": user_id,
            }
        )

        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                message_type = data.get("type")

                if message_type == "diagram_update":
                    # Validate edit permission
                    has_edit_access, error_msg = validate_diagram_access(
                        user_id, diagram_id, "update"
                    )
                    if not has_edit_access:
                        await websocket.send_json(
                            {"type": "error", "message": error_msg}
                        )
                        continue

                    # Broadcast the update to all collaborators
                    update_data = {
                        "type": "diagram_update",
                        "user_id": user_id,
                        "data": data.get("data", {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    # Save the update to database
                    try:
                        # Extract update data
                        update_payload = data.get("data", {})
                        nodes = update_payload.get("nodes")
                        edges = update_payload.get("edges")
                        title = update_payload.get("title")
                        description = update_payload.get("description")

                        # Get the diagram to find the owner
                        diagram = dynamodb_service.get_diagram(user_id, diagram_id)
                        if not diagram:
                            # Find in shared diagrams
                            shared_diagrams = (
                                dynamodb_service.get_shared_diagrams_for_user(user_id)
                            )
                            diagram = next(
                                (d for d in shared_diagrams if d.id == diagram_id), None
                            )

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

                            # Broadcast to all collaborators
                            await notify_collaborators(diagram_id, update_data)
                        else:
                            await websocket.send_json(
                                {"type": "error", "message": "Diagram not found"}
                            )

                    except Exception as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"Failed to save update: {str(e)}",
                            }
                        )

                elif message_type == "cursor_position":
                    # Broadcast cursor position to other collaborators
                    cursor_data = {
                        "type": "cursor_update",
                        "user_id": user_id,
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
                        }
                    )

            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "message": "Invalid JSON received"}
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
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
