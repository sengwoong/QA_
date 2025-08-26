from fastapi import APIRouter

from .v1 import health, messages, sse


router = APIRouter()
router.include_router(health.router)
router.include_router(messages.router, prefix="/messages", tags=["messages"])
router.include_router(sse.router, prefix="/sse", tags=["sse"])


