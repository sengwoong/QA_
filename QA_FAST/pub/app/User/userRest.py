from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.User.user_service import (
    create_user,
    list_users,
    update_user,
    get_or_create_user_by_username,
)
from app.db.session import get_db

router = APIRouter(prefix="/user", tags=["user"])


# Schemas
class UserCreate(BaseModel):
    username: str

@router.post("/users")
def _create_user(body: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, username=body.username)


@router.get("/users")
def _list_users(page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    items, total = list_users(db, page=page, size=size)
    return {"items": items, "total": total, "page": page, "size": size}


class UserUpdate(BaseModel):
    username: Optional[str] = None
    status: Optional[str] = None


@router.patch("/users/{user_id}")
def _update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db)):
    return update_user(db, user_id=user_id, username=body.username, status=body.status)


class LoginRequest(BaseModel):
    username: str


@router.post("/login")
def _login(body: LoginRequest, db: Session = Depends(get_db)):
    user = get_or_create_user_by_username(db, username=body.username)
    # 간단한 로그인: 토큰 없이 사용자 정보만 반환 (테스트용)
    return {"userId": user.id, "username": user.username}
