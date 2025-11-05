from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # user_id alanı daha sonra eklenecek
    # summary alanı daha sonra eklenecek
    model_used = Column(String)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

ChatSession.messages = relationship(
    "ChatMessage", 
    back_populates="session", 
    order_by=ChatMessage.created_at
)

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    # Gerçek bir uygulamada burası bir kullanıcı ID'sine bağlı olurdu.
    # Şimdilik tek profil için ID=1 kullanacağız.
    
    # Model tarafından otomatik olarak oluşturulan ve güncellenen özet.
    auto_summary_json = Column(Text, default="{}")