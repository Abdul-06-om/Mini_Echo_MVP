import os

import httpx

BASE_URL = "https://api.elevenlabs.io"
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # "Sarah" — matches the persona name


def _headers() -> dict:
    return {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}


def synthesize_speech(text: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    response = httpx.post(
        f"{BASE_URL}/v1/text-to-speech/{voice_id}",
        params={"output_format": "pcm_16000"},
        json={"text": text, "model_id": "eleven_turbo_v2_5"},
        headers={**_headers(), "Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.content


def list_voices() -> list[dict]:
    response = httpx.get(
        f"{BASE_URL}/v2/voices",
        headers=_headers(),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return [{"voice_id": v["voice_id"], "name": v["name"]} for v in data["voices"]]
