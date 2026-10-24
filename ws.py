"""
WebSocket protocol (all changes go through REST; the socket only delivers events):

  client -> {"type": "auth", "token": "<jwt>"}           must be the first message, within 10 s
  client -> {"type": "subscribe", "room_id": "..."}       allowed only for active participants of that room
  client -> {"type": "unsubscribe", "room_id": "..."}
  client -> {"type": "ping"}
  server -> {"type": "ready"} | {"type": "error", ...} | events like chat_message, room_phase, leaderboard, notification

Unknown message types are rejected; more than 30 messages in 10 s, messages over 4 KB, or more than
5 sockets per user close the connection.
"""
import asyncio
import json
import time
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.db import SessionLocal, utcnow
from ..core.security import user_from_token
from ..models import RoomParticipant
from ..services.realtime import hub

router = APIRouter()
MAX_SOCKETS = 5
MAX_BYTES = 4096


def _authenticate(token: str):
    with SessionLocal() as db:
        u = user_from_token(db, token)
        if u:
            u.last_seen_at = utcnow()
            db.commit()
        return u.id if u else None


def _is_participant(room_id: str, user_id: str) -> bool:
    with SessionLocal() as db:
        p = db.query(RoomParticipant).filter_by(room_id=room_id, user_id=user_id, status="active").first()
        return p is not None


@router.websocket("/ws")
async def socket(ws: WebSocket):
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10)
        msg = json.loads(first) if len(first) <= MAX_BYTES else {}
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        await ws.close(code=1008)
        return
    user_id = await asyncio.to_thread(_authenticate, str(msg.get("token", ""))) if msg.get("type") == "auth" else None
    if not user_id:
        await ws.send_text(json.dumps({"type": "error", "code": "UNAUTHORIZED"}))
        await ws.close(code=1008)
        return
    if hub.connection_count(user_id) >= MAX_SOCKETS:
        await ws.send_text(json.dumps({"type": "error", "code": "TOO_MANY_CONNECTIONS"}))
        await ws.close(code=1008)
        return
    was_online = hub.is_online(user_id)
    hub.add(user_id, ws)
    await ws.send_text(json.dumps({"type": "ready"}))
    recent: deque = deque()
    rooms: set[str] = set()
    try:
        while True:
            raw = await ws.receive_text()
            now = time.monotonic()
            recent.append(now)
            while recent and recent[0] < now - 10:
                recent.popleft()
            if len(recent) > 30 or len(raw) > MAX_BYTES:
                await ws.close(code=1008)
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            if t == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif t == "subscribe" and isinstance(msg.get("room_id"), str):
                rid = msg["room_id"][:32]
                if await asyncio.to_thread(_is_participant, rid, user_id):
                    hub.join_room(rid, ws)
                    rooms.add(rid)
                    await ws.send_text(json.dumps({"type": "subscribed", "room_id": rid}))
                    if not was_online:
                        hub.to_room(rid, "status_changed", {"user_id": user_id})
                else:
                    await ws.send_text(json.dumps({"type": "error", "code": "FORBIDDEN", "room_id": rid}))
            elif t == "unsubscribe" and isinstance(msg.get("room_id"), str):
                hub.leave_room(msg["room_id"], ws)
                rooms.discard(msg["room_id"])
            else:
                await ws.send_text(json.dumps({"type": "error", "code": "UNKNOWN_EVENT"}))
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(user_id, ws)
        if not hub.is_online(user_id):
            for rid in rooms:
                hub.to_room(rid, "status_changed", {"user_id": user_id})
