from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.bedrock import get_reply

app = FastAPI()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    reply = get_reply(messages)
    return ChatResponse(reply=reply)
