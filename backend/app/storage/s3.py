from uuid import uuid4

from botocore.exceptions import ClientError

from backend.app.storage.local import ObjectNotFound


class S3ObjectStore:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def _key(self, uri: str) -> str:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ObjectNotFound(uri)
        return uri.removeprefix(prefix)

    def put_image(self, data: bytes, *, content_type: str) -> str:
        extension = "png" if content_type == "image/png" else "jpg"
        key = f"uploads/{uuid4().hex}.{extension}"
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return f"s3://{self.bucket}/{key}"

    def get_uri(self, uri: str) -> str:
        self._key(uri)
        return uri

    def delete(self, uri: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(uri))

    def open(self, uri: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(uri))
        except ClientError as exc:
            raise ObjectNotFound(uri) from exc
        return response["Body"].read()
