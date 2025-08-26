from __future__ import annotations

import json
import os
from typing import AsyncGenerator

from fastapi import APIRouter
from starlette.responses import StreamingResponse


from app.sse_bus import bus

router = APIRouter()


def _dsn_from_env() -> str:
    return ""


async def listen_event_stream(room_id: int, to_user_id: int) -> AsyncGenerator[str, None]:
    print(f"[SSE] subscribe room={room_id} to={to_user_id}")
    queue = bus.add_subscriber(room_id)
    try:
        while True:
            payload = await queue.get()
            if payload.get("toUserId") is not None and payload.get("toUserId") != to_user_id:
                continue
            seq = payload.get("seq")
            print(
                f"[SSE] emit room={payload.get('roomId')} sender={payload.get('senderId')} to={payload.get('toUserId')} seq={seq}"
            )
            data = json.dumps(
                {
                    "id": payload.get("id"),
                    "roomId": payload.get("roomId"),
                    "senderId": payload.get("senderId"),
                    "toUserId": payload.get("toUserId"),
                    "seq": seq,
                    "content": payload.get("content"),
                }
            )
            lines = []
            if seq is not None:
                lines.append(f"id: {seq}")
            lines.append("event: message")
            lines.append(f"data: {data}")
            yield "\n".join(lines) + "\n\n"
    finally:
        bus.remove_subscriber(room_id, queue)


@router.get("/rooms/{room_id}")
async def sse_room(room_id: int, toUserId: int):
    print(f"[SSE] subscribe room={room_id} to={toUserId}")
    return EventSourceResponse(listen_event_stream(room_id, toUserId))


class EventSourceResponse(StreamingResponse):
    media_type = "text/event-stream"


