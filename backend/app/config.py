from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PANTRYOPS_")

    database_url: str
    redis_url: str
    storage_backend: Literal["local", "minio", "s3"] = "local"
    service_name: str = "pantryops"
