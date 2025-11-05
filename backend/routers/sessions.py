import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
import schemas
import database

router = APIRouter()

def parse_message_content(content: str):
    """Parse message content which may be JSON format (with images, reasoning) or plain string."""
    if not content:
        return {"content": "", "reasoning": None, "images": []}
    
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return {
                "content": parsed.get("content", ""),
                "reasoning": parsed.get("reasoning"),
                "images": parsed.get("images", [])
            }
        else:
            return {"content": str(parsed), "reasoning": None, "images": []}
    except (json.JSONDecodeError, TypeError):
        return {"content": content, "reasoning": None, "images": []}

@router.get("/api/sessions", response_model=List[schemas.ChatSessionBase])
def get_sessions(db: Session = Depends(database.get_db)):
    """Tüm sohbet oturumlarını en yeniden en eskiye doğru listeler."""
    sessions = db.query(models.ChatSession).order_by(models.ChatSession.created_at.desc()).all()
    return sessions

@router.get("/api/sessions/{session_id}")
def get_session_messages(session_id: int, db: Session = Depends(database.get_db)):
    """Belirli bir sohbet oturumuna ait tüm mesajları döndürür."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    parsed_messages = []
    for message in session.messages:
        if not message.content or not message.content.strip():
            continue
        
        parsed = parse_message_content(message.content)
        message_obj = {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": parsed["content"],
            "images": parsed["images"],
            "created_at": message.created_at.isoformat() if message.created_at else None
        }
        if parsed.get("reasoning"):
            message_obj["reasoning"] = parsed["reasoning"]
        parsed_messages.append(message_obj)
    
    return {
        "id": session.id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "model_used": session.model_used,
        "messages": parsed_messages
    }