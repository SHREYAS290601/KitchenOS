import boto3

from backend.app.config import Settings
from backend.app.storage.base import ObjectStore
from backend.app.storage.local import LocalObjectStore
from backend.app.storage.s3 import S3ObjectStore


def make_object_store(settings: Settings) -> ObjectStore:
    if settings.storage_backend == "local":
        return LocalObjectStore(settings.storage_path)
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    return S3ObjectStore(client, settings.s3_bucket)


__all__ = ["ObjectStore", "make_object_store"]
