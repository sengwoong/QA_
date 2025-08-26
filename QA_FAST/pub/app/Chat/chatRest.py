from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
import httpx
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.Chat.chat_service import (
    create_room,
    add_room_member,
    list_room_messages,
    list_all_room_messages,
    list_rooms,
    remove_room_member,
    list_room_members,
)
from app.User.user_service import (
    add_friend,
    list_friends,
    delete_friend,
)


router = APIRouter(prefix="/chat", tags=["chat"])

SUB_BASE_URL = os.getenv("SUB_BASE_URL", "http://127.0.0.1:8001")




class FriendCreate(BaseModel):
    userId: int
    friendUserId: int


@router.get("/friends")
def _list_friends(userId: int, page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    items, total = list_friends(db, user_id=userId, page=page, size=size)
    return {"items": items, "total": total, "page": page, "size": size}


class RoomCreate(BaseModel):
    type: str  # dm | group
    title: str


class RoomMemberCreate(BaseModel):
    roomId: int
    userId: int


class MessageCreate(BaseModel):
    roomId: int
    senderId: int
    content: str
    replyToId: Optional[int] = None



@router.post("/friends")
def _add_friend(body: FriendCreate, db: Session = Depends(get_db)):
    return add_friend(db, user_id=body.userId, friend_user_id=body.friendUserId)


@router.delete("/friends")
def _delete_friend(userId: int, friendUserId: int, db: Session = Depends(get_db)):
    ok = delete_friend(db, user_id=userId, friend_user_id=friendUserId)
    return {"deleted": ok}


@router.post("/rooms")
def _create_room(body: RoomCreate, db: Session = Depends(get_db)):
    return create_room(db, type=body.type, title=body.title)


@router.get("/rooms")
def _list_rooms(page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    items, total = list_rooms(db, page=page, size=size)
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/room-members")
def _add_room_member(body: RoomMemberCreate, db: Session = Depends(get_db)):
    return add_room_member(db, room_id=body.roomId, user_id=body.userId)


@router.get("/room-members")
def _list_room_members(roomId: int, page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    items, total = list_room_members(db, room_id=roomId, page=page, size=size)
    return {"items": items, "total": total, "page": page, "size": size}


@router.delete("/room-members")
def _leave_room(roomId: int, userId: int, db: Session = Depends(get_db)):
    ok = remove_room_member(db, room_id=roomId, user_id=userId)
    return {"left": ok}


@router.delete("/rooms/{room_id}/leave")
def _leave_room_by_path(room_id: int, userId: int, db: Session = Depends(get_db)):
    ok = remove_room_member(db, room_id=room_id, user_id=userId)
    return {"left": ok}




@router.get("/messages")
def _list_all_messages(roomId: int, db: Session = Depends(get_db)):
    return list_all_room_messages(db, room_id=roomId)


@router.get("/rooms/{room_id}/messages")
def _list_messages(room_id: int, page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    items, total = list_room_messages(db, room_id=room_id, page=page, size=size)
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/rooms/{room_id}/history")
def _room_history(room_id: int, limit: int = 50):
    # SUB 서비스의 메시지 히스토리 프록시
    with httpx.Client() as client:
        r = client.get(f"{SUB_BASE_URL}/messages", params={"roomId": room_id, "limit": limit}, timeout=5)
    r.raise_for_status()
    return r.json()


