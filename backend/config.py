import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL_NAME = os.getenv("MODEL_NAME", "google/gemini-2.0-flash-001")
MEMORY_CHARACTER_LIMIT = int(os.getenv("MEMORY_CHARACTER_LIMIT", "2000"))
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "google/gemini-2.5-flash")
# Desteklenen modeller
AVAILABLE_MODELS = {
    "google/gemini-2.0-flash-001": "Google Gemini 2.0 Flash",
    "openai/gpt-5": "OpenAI GPT-5",
    "openai/gpt-4.1-mini": "GPT-4.1 Mini",
    "google/gemini-2.5-flash-image-preview": "Google Gemini 2.5 Flash Image",
    "qwen/qwen3-coder": "Qwen3 Coder",
    "openai/gpt-4-turbo": "OpenAI GPT-4 Turbo",
}

# Görsel üretimi destekleyen modeller
IMAGE_GENERATION_MODELS = {
    "google/gemini-2.5-flash-image-preview",
}

# Reasoning modelleri için max_tokens limiti
REASONING_MODELS_MAX_TOKENS = {
    "openai/gpt-5": 32000,
}

# Uygulama genelinde kullanılacak model (başlangıç değeri)
# Bu değişkeni bir sınıf içinde yönetmek, global state'i azaltır.
class AppState:
    def __init__(self):
        self.current_model = DEFAULT_MODEL_NAME

    def set_model(self, model_id: str):
        if model_id in AVAILABLE_MODELS:
            self.current_model = model_id
            print(f"✅ Model seçildi: {AVAILABLE_MODELS[model_id]} ({model_id})")
            return True
        return False

    def get_model(self) -> str:
        return self.current_model

app_state = AppState()