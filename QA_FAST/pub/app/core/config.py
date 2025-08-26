from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QA_FAST"
    debug: bool = False
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5433/qa_fast"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


