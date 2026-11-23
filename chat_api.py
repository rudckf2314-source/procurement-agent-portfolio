from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from utils.chatbot import generate_chat_response

router = APIRouter()

# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    context: Optional[str] = ""

@router.post("/chat")
def chat(request: ChatRequest):
    """Chatbot endpoint."""
    # Convert Pydantic models to dicts
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    response = generate_chat_response(messages, context=request.context)
    return {"response": response}
