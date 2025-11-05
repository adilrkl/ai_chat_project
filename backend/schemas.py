from pydantic import BaseModel
from datetime import datetime

class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessage(ChatMessageBase):
    id: int
    session_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class ChatSessionBase(BaseModel):
    id: int
    created_at: datetime

class ChatSessionWithMessages(ChatSessionBase):
    messages: list[ChatMessage] = []
    model_used: str

    class Config:
        orm_mode = True