class ModelAssetsUnavailable(RuntimeError):
    """Raised when an adapter's pinned local assets are not available."""

    def __init__(self, *, model_name: str, fetch_command: str) -> None:
        if not model_name.strip() or "\n" in model_name:
            raise ValueError("model_name must be a non-empty single-line value")
        if not fetch_command.strip() or "\n" in fetch_command:
            raise ValueError("fetch_command must be a non-empty single-line value")

        self.model_name = model_name
        self.fetch_command = fetch_command
        super().__init__("Required local model assets are unavailable.")


class UnsafeImageError(ValueError):
    """Raised when untrusted image bytes fail the bounded decode contract."""
