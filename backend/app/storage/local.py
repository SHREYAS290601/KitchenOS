from pathlib import Path
from uuid import uuid4


class ObjectNotFound(FileNotFoundError):
    pass


class LocalObjectStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, uri: str) -> Path:
        if not uri.startswith("local://"):
            raise ObjectNotFound(uri)
        name = uri.removeprefix("local://")
        if not name or Path(name).name != name:
            raise ObjectNotFound(uri)
        return self.root / name

    def put_image(self, data: bytes, *, content_type: str) -> str:
        extension = ".png" if content_type == "image/png" else ".jpg"
        name = f"{uuid4().hex}{extension}"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / name).write_bytes(data)
        return f"local://{name}"

    def get_uri(self, uri: str) -> str:
        self._path(uri)
        return uri

    def delete(self, uri: str) -> None:
        path = self._path(uri)
        try:
            path.unlink()
        except FileNotFoundError as exc:
            raise ObjectNotFound(uri) from exc

    def open(self, uri: str) -> bytes:
        try:
            return self._path(uri).read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(uri) from exc
