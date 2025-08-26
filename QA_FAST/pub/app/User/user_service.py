from datetime import datetime
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from app.User.user import User
from app.User.friend import Friend


def paginate(query, page: int, size: int):
    page = max(page, 1)
    size = max(min(size, 100), 1)
    return query.offset((page - 1) * size).limit(size)

def update_user(db: Session, *, user_id: int, username: Optional[str] = None, status: Optional[str] = None) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise ValueError("USER_NOT_FOUND")
    if username is not None:
        user.username = username
    if status is not None:
        user.status = status
    db.commit()
    db.refresh(user)
    return user


def delete_friend(db: Session, *, user_id: int, friend_user_id: int) -> bool:
    obj = (
        db.query(Friend)
        .filter(Friend.user_id == user_id, Friend.friend_user_id == friend_user_id)
        .first()
    )
    if obj is None:
        return False
    db.delete(obj)
    db.commit()
    return True


# Users
def create_user(db: Session, *, username: str) -> User:
    user = User(username=username, status="active", created_at=datetime.utcnow())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, *, page: int, size: int) -> Tuple[List[User], int]:
    base = db.query(User).order_by(User.id.desc())
    total = base.count()
    items = paginate(base, page, size).all()
    return items, total


# Friends
def add_friend(db: Session, *, user_id: int, friend_user_id: int) -> Friend:
    fr = Friend(user_id=user_id, friend_user_id=friend_user_id, created_at=datetime.utcnow())
    db.add(fr)
    db.commit()
    db.refresh(fr)
    return fr


def list_friends(db: Session, *, user_id: int, page: int, size: int) -> Tuple[List[User], int]:
    base = (
        db.query(User)
        .join(Friend, Friend.friend_user_id == User.id)
        .filter(Friend.user_id == user_id)
        .order_by(User.id.desc())
    )
    total = base.count()
    items = paginate(base, page, size).all()
    return items, total


# Auth (lightweight): get or create by username
def get_or_create_user_by_username(db: Session, *, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is not None:
        return user
    return create_user(db, username=username)