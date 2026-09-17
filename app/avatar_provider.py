from typing import Protocol


class AvatarProvider(Protocol):
    def create_session(self) -> dict:
        """Create a new avatar session and return connection info for the frontend."""
        ...
