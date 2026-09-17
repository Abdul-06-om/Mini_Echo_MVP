import os

import httpx

FACE_ID = "f0ba4efe-7946-45de-9955-c04a04c367b9"  # Simli preset "Doctor" face
TOKEN_URL = "https://api.simli.ai/compose/token"


class SimliAvatarProvider:
    def __init__(self):
        self.api_key = os.environ["SIMLI_API_KEY"]

    def create_session(self, face_id: str | None = None) -> dict:
        response = httpx.post(
            TOKEN_URL,
            json={
                "faceId": face_id or FACE_ID,
                "handleSilence": True,
                "maxSessionLength": 600,
                "maxIdleTime": 180,
            },
            headers={
                "Content-Type": "application/json",
                "x-simli-api-key": self.api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
