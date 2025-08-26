from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.User.user import User
from app.User.friend import Friend
from app.Chat.room import Room
from app.Chat.room_member import RoomMember
from app.Chat.message import Message


def paginate(query, page: int, size: int):
    page = max(page, 1)
    size = max(min(size, 100), 1)
    return query.offset((page - 1) * size).limit(size)



# Rooms
def create_room(db: Session, *, type: str, title: str) -> Room:
    room = Room(type=type, title=title, created_at=datetime.utcnow())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def list_rooms(db: Session, *, page: int, size: int) -> Tuple[List[Room], int]:
    base = db.query(Room).order_by(Room.id.desc())
    total = base.count()
    items = paginate(base, page, size).all()
    return items, total


# Room Members
def add_room_member(db: Session, *, room_id: int, user_id: int) -> RoomMember:
    member = RoomMember(room_id=room_id, user_id=user_id, joined_at=datetime.utcnow())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_room_member(db: Session, *, room_id: int, user_id: int) -> bool:
    obj = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
    )
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True


def list_room_members(
    db: Session, *, room_id: int, page: int, size: int
) -> Tuple[List[RoomMember], int]:
    base = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id)
        .order_by(RoomMember.id.desc())
    )
    total = base.count()
    items = paginate(base, page, size).all()
    return items, total


# Messages
def _next_seq_for_room(db: Session, room_id: int) -> int:
    return (
        db.query(func.coalesce(func.max(Message.seq), 0)).filter(Message.room_id == room_id).scalar() + 1
    )


def create_message(
    db: Session,
    *,
    room_id: int,
    sender_id: int,
    content: str,
    reply_to_id: Optional[int] = None,
) -> Message:
    seq = _next_seq_for_room(db, room_id)
    msg = Message(
        room_id=room_id,
        sender_id=sender_id,
        content=content,
        seq=seq,
        reply_to_id=reply_to_id,
        created_at=datetime.utcnow(),
        edited_at=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_room_messages(
    db: Session, *, room_id: int, page: int, size: int
) -> Tuple[List[Message], int]:
    # 최신순 정렬(desc)
    base = db.query(Message).filter(Message.room_id == room_id).order_by(Message.seq.desc())
    total = base.count()
    items = paginate(base, page, size).all()
    return items, total


def list_all_room_messages(db: Session, *, room_id: int) -> List[Message]:
    return (
        db.query(Message)
        .filter(Message.room_id == room_id)
        .order_by(Message.seq.asc())
        .all()
    )





