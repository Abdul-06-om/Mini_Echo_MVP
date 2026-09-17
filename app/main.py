from dotenv import load_dotenv

load_dotenv()

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.avatar_simli import SimliAvatarProvider
from app.bedrock import get_reply
from app.personas import get_persona, list_personas
from app.tts import list_voices, synthesize_speech

logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

avatar_provider = SimliAvatarProvider()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RoleplaySessionRequest(BaseModel):
    persona_id: str
    scenario: str
    objective: str
    mood: str
    difficulty: Literal["easy", "medium", "hard"]


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session: RoleplaySessionRequest | None = None


class ChatResponse(BaseModel):
    reply: str


class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    persona = None
    session_dict = None
    if request.session is not None:
        persona = get_persona(request.session.persona_id)
        if persona is None:
            raise HTTPException(status_code=400, detail="Unknown persona_id.")
        session_dict = request.session.model_dump()

    try:
        if persona is not None:
            reply = get_reply(messages, persona=persona, session=session_dict)
        else:
            reply = get_reply(messages)
    except Exception:
        logger.exception("Bedrock call failed")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable. Please try again.",
        )

    return ChatResponse(reply=reply)


@app.get("/personas")
def personas():
    return [
        {
            "id": p.id,
            "name": p.name,
            "role_title": p.role_title,
            "category": p.category,
            "voice_id": p.voice_id,
            "face_id": p.face_id,
        }
        for p in list_personas()
    ]


@app.post("/avatar/session")
def avatar_session():
    try:
        return avatar_provider.create_session()
    except Exception:
        logger.exception("Avatar session creation failed")
        raise HTTPException(
            status_code=503,
            detail="The avatar service is temporarily unavailable. Please try again.",
        )


@app.get("/voices")
def voices():
    try:
        return list_voices()
    except Exception:
        logger.exception("Voice list fetch failed")
        raise HTTPException(
            status_code=503,
            detail="Could not load voices. Please try again.",
        )


@app.post("/tts")
def tts(request: TTSRequest):
    try:
        if request.voice_id:
            audio = synthesize_speech(request.text, request.voice_id)
        else:
            audio = synthesize_speech(request.text)
    except Exception:
        logger.exception("Speech synthesis failed")
        raise HTTPException(
            status_code=503,
            detail="Could not generate speech. Please try again.",
        )
    return Response(content=audio, media_type="audio/pcm")
