from __future__ import annotations

import json
import os
from typing import Any, Dict, Set, DefaultDict
from collections import defaultdict

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()


SUB_BASE_URL = os.getenv("SUB_BASE_URL", "http://127.0.0.1:8001")

# 룸별 연결된 소켓 목록 (동일 프로세스 내 브로드캐스트용)
room_clients: DefaultDict[int, Set[WebSocket]] = defaultdict(set)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    joined_rooms: Set[int] = set()
    try:
        while True:
            raw = await ws.receive_text()
            print(f"[WS] recv: {raw[:200]}")
            try:
                data: Dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "message": "invalid_json"}))
                continue

            event_type = data.get("type")

            if event_type == "join_room":
                rid = int(data.get("roomId"))
                print(f"[WS] join_room roomId={rid}")
                room_clients[rid].add(ws)
                joined_rooms.add(rid)
                await ws.send_text(json.dumps({"type": "joined", "roomId": rid}))
                continue

            if event_type == "leave_room":
                rid = int(data.get("roomId"))
                print(f"[WS] leave_room roomId={rid}")
                room_clients[rid].discard(ws)
                joined_rooms.discard(rid)
                await ws.send_text(json.dumps({"type": "left", "roomId": rid}))
                continue

            if event_type == "publish":
                payload = {
                    "roomId": data.get("roomId"),
                    "senderId": data.get("senderId"),
                    "toUserId": data.get("toUserId"),
                    "content": data.get("content"),
                    "replyToId": data.get("replyToId"),
                }
                print(f"[WS] publish room={payload['roomId']} sender={payload['senderId']} to={payload['toUserId']}")
                async with httpx.AsyncClient() as client:
                    r = await client.post(f"{SUB_BASE_URL}/messages", json=payload, timeout=10)
                if r.status_code == 200:
                    msg = r.json()
                    print(f"[WS] publish ok id={msg.get('id')} seq={msg.get('seq')}")
                    await ws.send_text(json.dumps({"type": "ack", "data": msg}))
                    # 동일 프로세스 내 같은 룸 클라이언트에게 브로드캐스트 (빠른 반영)
                    try:
                        rid = int(payload["roomId"])
                        broadcast = json.dumps({"type": "message", "data": msg})
                        for peer in list(room_clients.get(rid, set())):
                            try:
                                if peer is not ws:
                                    await peer.send_text(broadcast)
                                    print(f"[WS] broadcast to room={rid}")
                            except Exception:
                                pass
                    except Exception:
                        pass
                else:
                    await ws.send_text(
                        json.dumps({"type": "error", "code": r.status_code, "message": r.text})
                    )
                continue

            await ws.send_text(json.dumps({"type": "error", "message": "unknown_event"}))
    except WebSocketDisconnect:
        pass
    finally:
        # 연결 종료 시, 가입했던 룸에서 제거
        for rid in joined_rooms:
            room_clients[rid].discard(ws)


