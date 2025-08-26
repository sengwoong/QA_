from fastapi import FastAPI

from app.route.routes import router as api_router
from app.models.base import Base
from app.db.session import engine
from sqlalchemy import text


def create_application() -> FastAPI:
    application = FastAPI(title="QA_FAST-SUB", version="0.1.0")
    application.include_router(api_router)
    return application


app = create_application()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    # Install NOTIFY trigger for messages (minimal payload)
    with engine.begin() as conn:
        print("[SUB] installing triggers for messages table ...")
        conn.exec_driver_sql(
            """
            create or replace function notify_message_insert() returns trigger as $$
            begin
              perform pg_notify(
                'room_evt_' || NEW.room_id::text,
                json_build_object(
                  'id', NEW.id,
                  'roomId', NEW.room_id,
                  'senderId', NEW.sender_id,
                  'toUserId', NEW.to_user_id,
                  'seq', NEW.seq,
                  'content', NEW.content
                )::text
              );
              return NEW;
            end;
            $$ language plpgsql;

            drop trigger if exists trg_message_notify on messages;
            create trigger trg_message_notify
            after insert on messages
            for each row execute function notify_message_insert();
            """
        )
        print("[SUB] triggers installed")


