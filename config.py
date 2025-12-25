from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DISCORD_TOKEN: str
    ALLOWED_ROLE_ID: int
    ALLOWED_CHANNEL_IDS: List[int] = []
    TIMEZONE: str = "Europe/Warsaw"

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()  # pyright: ignore[reportCallIssue]
