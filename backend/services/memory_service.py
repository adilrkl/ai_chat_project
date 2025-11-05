# backend/services/memory_service.py

import json
import asyncio
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import models
from config import (
    OPENROUTER_API_KEY, OPENROUTER_API_URL, MEMORY_CHARACTER_LIMIT, SUMMARIZER_MODEL
)



async def generate_and_update_profile_summary(session_id: int, db: Session):
    """
    Sohbet geçmişini analiz eder, kullanıcı hakkında bilgi çıkarır,
    belirlenen karakter limitini aşmamasını sağlar ve profili günceller.
    """
    print(f"\n--- 🧠 Sohbet Sonu Hafıza Analizi Başlatılıyor (Oturum: {session_id}) ---")

    messages = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == session_id).order_by(models.ChatMessage.created_at).all()
    
    # Analiz için minimum mesaj sayısı (örn: 2 kullanıcı, 2 asistan)
    if len(messages) < 4:
        print("--- 🧠 Hafıza Analizi: Yeterli konuşma olmadığı için atlandı. ---")
        return

    profile = db.query(models.UserProfile).filter(models.UserProfile.id == 1).first()
    if not profile:
        profile = models.UserProfile(id=1, auto_summary_json="{}")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    
    current_summary_json = profile.auto_summary_json

    conversation_text = ""
    for msg in messages:
        try:
            content_data = json.loads(msg.content)
            text_content = content_data.get("content", "")
        except (json.JSONDecodeError, TypeError):
            text_content = msg.content
        if text_content:
            conversation_text += f"{msg.role}: {text_content}\n"

    prompt = f"""
    You are a highly intelligent entity tasked with creating a psychological and factual profile of a user based on their conversation.
    Your goal is to update a JSON object that represents the user's memory profile.
    Analyze the following conversation.
    - Extract key facts, preferences, personality traits, and any other relevant information about the 'user'.
    - DO NOT invent information. Only use what is explicitly stated or strongly implied in the text.
    - Update the provided "Current Profile JSON". If a key already exists, update its value if new information contradicts or refines it. If the information is new, add a new key.
    - Keep the profile concise and factual. Remove temporary or outdated information (e.g., 'currently looking for ideas').
    - Your FINAL output MUST be ONLY the updated JSON object, and nothing else. No explanations, no introductory text.

    Current Profile JSON:
    {current_summary_json}

    Conversation to Analyze:
    ---
    {conversation_text}
    ---
    
    Updated Profile JSON:
    """

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": SUMMARIZER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "max_tokens": 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            response_data = response.json()
            new_summary_str = response_data["choices"][0]["message"]["content"]
            
            # Bellek Limiti Kontrolü
            if len(new_summary_str) > MEMORY_CHARACTER_LIMIT:
                print(f"--- ⚠️ Hafıza limiti aşıldı ({len(new_summary_str)} > {MEMORY_CHARACTER_LIMIT}). Özet kısaltılıyor... ---")
                shrinking_prompt = f"""
                The following user profile JSON is too long. Your task is to summarize and shrink it.
                - Keep the most essential, timeless, and important facts about the user.
                - Remove any trivial, temporary, or less important details.
                - The final output MUST be a valid JSON object, and it MUST be under {MEMORY_CHARACTER_LIMIT} characters.
                - Output ONLY the final, shortened JSON. No explanations.

                JSON to shrink:
                {new_summary_str}
                """
                shrinking_payload = {
                    "model": SUMMARIZER_MODEL,
                    "messages": [{"role": "user", "content": shrinking_prompt}],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 1024
                }
                shrinking_response = await client.post(OPENROUTER_API_URL, headers=headers, json=shrinking_payload)
                shrinking_response.raise_for_status()
                shrinking_data = shrinking_response.json()
                new_summary_str = shrinking_data["choices"][0]["message"]["content"]
                print("--- ✅ Hafıza başarıyla kısaltıldı. ---")
            
            json.loads(new_summary_str)
            
            profile.auto_summary_json = new_summary_str
            db.commit()
            print(f"--- ✅ Hafıza başarıyla güncellendi. Yeni profil: {new_summary_str} ---")

    except Exception as e:
        print(f"--- ❌ Hafıza analizi veya kısaltma sırasında hata oluştu: {e} ---")

async def run_summary_if_inactive(session_id: int, disconnected_at: datetime, delay_seconds: int):
    """
    Belirlenen süre sonunda, eğer kullanıcı hala pasifse özetleme işlemini çalıştırır.
    Bu fonksiyon bir arka plan görevi olarak çalıştırılmak üzere tasarlanmıştır.
    """
    try:
        print(f"--- ⏰ Özetleme task başlatıldı (Oturum: {session_id}). {delay_seconds} sn bekleniyor... ---")
        await asyncio.sleep(delay_seconds)
        print(f"--- ⏰ Bekleme tamamlandı. Özetleme kontrolü yapılıyor (Oturum: {session_id})... ---")
        
        from database import SessionLocal # Gecikmeli import, dairesel bağımlılığı önler

        db = SessionLocal()
        try:
            session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
            
            if not session:
                print(f"--- 🧠 Özetleme iptal edildi (Oturum: {session_id}). Oturum bulunamadı. ---")
                return
            
            # Eğer son aktivite, ayrılma zamanından daha yeniyse (yani kullanıcı geri döndüyse), işlemi iptal et.
            if session.last_active_at and session.last_active_at > disconnected_at:
                print(f"--- 🧠 Özetleme iptal edildi (Oturum: {session_id}). Kullanıcı geri döndü (last_active: {session.last_active_at}, disconnected: {disconnected_at}). ---")
                return

            # Kullanıcı geri dönmediyse, asıl özetleme fonksiyonunu çağır.
            print(f"--- 🧠 Kullanıcı hala pasif. Özetleme başlatılıyor (Oturum: {session_id})... ---")
            await generate_and_update_profile_summary(session_id, db)
        finally:
            db.close()
    except Exception as e:
        import traceback
        print(f"--- ❌ Özetleme background task'ında hata oluştu (Oturum: {session_id}): {e} ---")
        print(f"--- ❌ Traceback: {traceback.format_exc()} ---")