from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.message import Message
from app.sse_bus import bus


class PublishMessageRequest(BaseModel):
    roomId: int
    senderId: int
    content: str
    toUserId: Optional[int] = None
    replyToId: Optional[int] = None


router = APIRouter()


@router.post("")
def publish_message(body: PublishMessageRequest, db: Session = Depends(get_db)):
    print(f"[PUB] room={body.roomId} sender={body.senderId} to={body.toUserId}")
    # seq는 룸별 증가. 간단히 최대 seq+1로 할당(동시성은 트랜잭션/락/DB함수로 보완 가능)
    next_seq = (
        db.query(func.coalesce(func.max(Message.seq), 0))
        .filter(Message.room_id == body.roomId)
        .scalar()
        + 1
    )
    msg = Message(
        room_id=body.roomId,
        sender_id=body.senderId,
        to_user_id=body.toUserId,
        content=body.content,
        reply_to_id=body.replyToId,
        seq=next_seq,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    try:
        bus.publish(
            msg.room_id,
            {
                "id": msg.id,
                "roomId": msg.room_id,
                "senderId": msg.sender_id,
                "toUserId": msg.to_user_id,
                "seq": msg.seq,
                "content": msg.content,
            },
        )
    except Exception:
        pass
    try:
        payload = {
            "id": msg.id,
            "roomId": msg.room_id,
            "senderId": msg.sender_id,
            "toUserId": msg.to_user_id,
            "seq": msg.seq,
            "content": msg.content,
        }
        print(f"[PUB] saved id={msg.id} seq={msg.seq}")
    except Exception:
        pass

    return {
        "id": msg.id,
        "roomId": msg.room_id,
        "senderId": msg.sender_id,
        "toUserId": msg.to_user_id,
        "content": msg.content,
        "seq": msg.seq,
        "createdAt": msg.created_at.isoformat() + "Z",
        "replyToId": msg.reply_to_id,
    }


@router.get("")
def list_messages(roomId: int, limit: int = 50, db: Session = Depends(get_db)):
    # 최근 메시지 limit개, 과거->현재 순서로 반환
    limit = max(min(limit, 200), 1)
    q = (
        db.query(Message)
        .filter(Message.room_id == roomId)
        .order_by(Message.seq.desc())
        .limit(limit)
        .all()
    )
    items = list(reversed([
        {
            "id": m.id,
            "roomId": m.room_id,
            "senderId": m.sender_id,
            "toUserId": m.to_user_id,
            "content": m.content,
            "seq": m.seq,
            "createdAt": m.created_at.isoformat() + "Z",
            "replyToId": m.reply_to_id,
        }
        for m in q
    ]))
    return {"items": items}


