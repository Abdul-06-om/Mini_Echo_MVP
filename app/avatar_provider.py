from typing import Protocol


class AvatarProvider(Protocol):
    def create_session(self, face_id: str | None = None) -> dict:
        """Create a new avatar session and return connection info for the frontend."""
        ...
