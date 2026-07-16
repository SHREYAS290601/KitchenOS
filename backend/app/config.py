from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PANTRYOPS_")

    database_url: str
    redis_url: str
    storage_backend: Literal["local", "minio", "s3"] = "local"
    storage_path: Path = Path("data/user_uploads")
    s3_endpoint_url: str | None = None
    s3_bucket: str = "pantryops-images"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    llm_api_key: str | None = None
    llm_model: str = "deepseek/deepseek-v4-flash"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    service_name: str = "pantryops"
