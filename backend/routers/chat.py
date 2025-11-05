import json
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import models
import database
from config import (
    OPENROUTER_API_KEY, OPENROUTER_API_URL, AVAILABLE_MODELS, 
    IMAGE_GENERATION_MODELS, REASONING_MODELS_MAX_TOKENS, app_state
)
from services.memory_service import run_summary_if_inactive

router = APIRouter()

@router.websocket("/ws/chat/{session_id_or_new}")
async def websocket_endpoint(
    websocket: WebSocket, 
    session_id_or_new: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    await websocket.accept()

    chat_session: models.ChatSession
    model_for_api_call: str

    if session_id_or_new == "new":
        model_for_api_call = app_state.get_model()
        chat_session = models.ChatSession(model_used=model_for_api_call)
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        await websocket.send_json({"type": "session_created", "session_id": chat_session.id, "model_used": model_for_api_call})
        print(f"New chat session created with ID: {chat_session.id} (Model: {AVAILABLE_MODELS.get(model_for_api_call, model_for_api_call)})")
    else:
        try:
            session_id = int(session_id_or_new)
            session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
            if not session:
                await websocket.send_json({"type": "error", "message": "Session not found"})
                await websocket.close(code=1008)
                return
            chat_session = session
            model_for_api_call = chat_session.model_used
            print(f"Resuming chat session with ID: {chat_session.id} (Model: {AVAILABLE_MODELS.get(model_for_api_call, model_for_api_call)})")
        except (ValueError, Exception) as e:
            await websocket.send_json({"type": "error", "message": f"Error loading session: {str(e)}"})
            await websocket.close(code=1008)
            return

    # Bağlantı kurulduğunda son aktivite zamanını güncelle
    chat_session.last_active_at = datetime.now(timezone.utc)
    db.commit()
    
    new_message_sent_in_this_connection = False
    try:
        while True:
            data = await websocket.receive_text()
            new_message_sent_in_this_connection = True
            
            # Her mesajda son aktivite zamanını güncelle
            chat_session.last_active_at = datetime.now(timezone.utc)
            
            # Model değişikliğini kontrol et: Eğer global state'teki model session'ın model'inden farklıysa, session'ı güncelle
            current_global_model = app_state.get_model()
            if chat_session.model_used != current_global_model:
                chat_session.model_used = current_global_model
                model_for_api_call = current_global_model
                print(f"🔄 Model güncellendi: {AVAILABLE_MODELS.get(chat_session.model_used, chat_session.model_used)} (Session ID: {chat_session.id})")
            
            db.commit()

            message_history_from_frontend = json.loads(data)
            
            last_message = message_history_from_frontend[-1]
            user_message_content = json.dumps({"content": last_message.get('content', ''), "images": last_message.get('images', [])})
            db_user_message = models.ChatMessage(session_id=chat_session.id, role="user", content=user_message_content)
            db.add(db_user_message)
            db.commit()

            api_messages = []

            # 1. UZUN SÜRELİ HAFIZAYI YÜKLE
            profile = db.query(models.UserProfile).filter(models.UserProfile.id == 1).first()
            if profile and profile.auto_summary_json and profile.auto_summary_json != "{}":
                try:
                    summary_data = json.loads(profile.auto_summary_json)
                    facts = [f"- {key.replace('_', ' ').title()}: {value}" for key, value in summary_data.items()]
                    formatted_summary = "\n".join(facts)
                    memory_message = {"role": "system", "content": f"This is a summary of what you know about the user. Use this information to personalize your responses:\n{formatted_summary}"}
                    api_messages.append(memory_message)
                    print(f"🧠 Otomatik hafıza yüklendi.")
                except json.JSONDecodeError:
                    print("⚠️ Hafıza JSON'u bozuk, yüklenemedi.")

            # 2. CANLI SOHBET ÖNBELLEĞİNİ UYGULA
            def convert_message_to_api_format(message):
                content = message.get("content", "")
                if isinstance(content, str) and content:
                    return {"role": message["role"], "content": [{"type": "text", "text": content}]}
                if isinstance(content, list):
                    return {"role": message["role"], "content": content}
                return message
            
            cache_boundary = (len(message_history_from_frontend) // 10) * 10
            if cache_boundary > 0:
                messages_to_cache = message_history_from_frontend[:cache_boundary]
                messages_after_cache = message_history_from_frontend[cache_boundary:]
                
                cached_history_text = ""
                for msg in messages_to_cache:
                    content = msg.get("content", "")
                    if isinstance(content, str) and content:
                        cached_history_text += f"{msg.get('role', 'unknown')}: {content}\n\n"

                system_message = {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": f"Here is a summary of the conversation so far (messages 1-{cache_boundary}). Use this for context:"},
                        {"type": "text", "text": cached_history_text, "cache_control": {"type": "ephemeral"}}
                    ]
                }
                api_messages.append(system_message)
                
                for msg in messages_after_cache:
                    api_messages.append(convert_message_to_api_format(msg))
            else:
                api_messages.extend([convert_message_to_api_format(msg) for msg in message_history_from_frontend])
            
            # --- Geri kalan kod (API Çağrısı, Streaming, DB Kayıt) aynı ---
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}","X-Title": "test chat",  "Content-Type": "application/json"}
            payload = {"model": model_for_api_call, "messages": api_messages, "stream": True}
            
            if model_for_api_call in IMAGE_GENERATION_MODELS: payload["modalities"] = ["image", "text"]
            if model_for_api_call in REASONING_MODELS_MAX_TOKENS: payload["max_tokens"] = REASONING_MODELS_MAX_TOKENS[model_for_api_call]

            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream("POST", OPENROUTER_API_URL, headers=headers, json=payload) as response:
                        response.raise_for_status()
                        
                        assistant_response_content, assistant_reasoning_content, assistant_images = "", "", []

                        async for line in response.aiter_lines():
                            if not line.strip() or not line.startswith('data: '): continue
                            data_str = line[6:]
                            if data_str == '[DONE]': break
                            try:
                                data_obj = json.loads(data_str)
                                choice = data_obj.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                message = choice.get("message", {})
                                
                                if reasoning := delta.get("reasoning"): assistant_reasoning_content += reasoning; await websocket.send_json({"type": "reasoning", "content": reasoning})
                                if content := delta.get("content"): assistant_response_content += content; await websocket.send_json({"type": "chat_message", "content": content})
                                if images_in_chunk := delta.get("images") or message.get("images"):
                                    for image in images_in_chunk:
                                        if (image_url := image.get("image_url", {}).get("url") or image.get("url")) and image_url not in assistant_images:
                                            assistant_images.append(image_url); await websocket.send_json({"type": "image", "image_url": image_url})
                            except json.JSONDecodeError: print(f"⚠️ JSON decode error, data: {data_str[:200]}")

                message_data = {"content": assistant_response_content, "reasoning": assistant_reasoning_content, "images": assistant_images}
                message_data = {k: v for k, v in message_data.items() if v}
                if message_data:
                    db_assistant_message = models.ChatMessage(session_id=chat_session.id, role="assistant", content=json.dumps(message_data))
                    db.add(db_assistant_message); db.commit()
                
                await websocket.send_json({"type": "stream_end"})

            except Exception as e:
                error_message = f"API Error or unexpected error: {str(e)}"; print(error_message)
                await websocket.send_json({"type": "error", "message": error_message}); await websocket.send_json({"type": "stream_end"})

    except WebSocketDisconnect:
        try:
            if chat_session and hasattr(chat_session, 'id') and chat_session.id and new_message_sent_in_this_connection:
                session_id, disconnected_at, delay_seconds = chat_session.id, datetime.now(timezone.utc), 15
                print(f"--- ⌛ Kullanıcı ayrıldı (Oturum: {session_id}). Özetleme {delay_seconds} sn sonra için programlandı. ---")
                background_tasks.add_task(run_summary_if_inactive, session_id, disconnected_at, delay_seconds)
            else:
                session_id = chat_session.id if chat_session and hasattr(chat_session, 'id') else "unknown"
                print(f"--- ⏭️ Client disconnected for session {session_id}. No new messages, skipping summary. ---")
        except Exception as e:
            print(f"--- ❌ Error in WebSocketDisconnect handler: {e} ---")
            
    except Exception as e:
        session_id = chat_session.id if chat_session and hasattr(chat_session, 'id') else "unknown"
        print(f"--- ❌ Error in WebSocket session {session_id}: {e} ---")
        import traceback
        print(f"--- ❌ Traceback: {traceback.format_exc()} ---")
    finally:
        db.close()