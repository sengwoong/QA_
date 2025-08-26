from fastapi import FastAPI

from app.Etc.health import router as health_router
from app.Chat.chatWs import router as chatWs
from app.Chat.chatRest import router as chatRest
from app.User.userRest import router as user_router
from app.model_base import Base
from app.db.session import engine


def create_application() -> FastAPI:
    application = FastAPI(
        title="QA_FAST-PUB",
        version="0.1.0",
        docs_url="/swagger",
        redoc_url=None,
    )
    application.include_router(health_router)
    application.include_router(chatWs)
    application.include_router(chatRest)
    application.include_router(user_router)
    return application


app = create_application()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    # Ensure missing columns exist (lightweight safeguard for dev)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE message ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP NULL"
        )


