from fastapi import APIRouter, HTTPException
from config import AVAILABLE_MODELS, app_state

router = APIRouter()

@router.get("/api/models")
def get_available_models():
    """Tüm kullanılabilir modelleri ve şu anki seçili modeli döndürür."""
    return {
        "available_models": AVAILABLE_MODELS,
        "current_model": app_state.get_model()
    }

@router.post("/api/models/select/{model_id:path}")
def select_model(model_id: str):
    """Kullanılacak modeli seçer."""
    if not app_state.set_model(model_id):
        raise HTTPException(status_code=400, detail=f"Model '{model_id}' not found")
    
    current_model_id = app_state.get_model()
    return {
        "message": f"Model changed to {AVAILABLE_MODELS[current_model_id]}",
        "current_model": current_model_id,
        "model_name": AVAILABLE_MODELS[current_model_id]
    }