from fastapi import FastAPI
from pydantic import BaseModel

from app.bedrock import get_reply

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    reply = get_reply(request.message)
    return ChatResponse(reply=reply)
