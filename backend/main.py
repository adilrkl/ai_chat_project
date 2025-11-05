from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
import database
from routers import models as models_router
from routers import sessions as sessions_router
from routers import chat as chat_router

# Veritabanı tablolarını oluştur (eğer yoksa)
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ana uygulamaya dahil et
app.include_router(models_router.router)
app.include_router(sessions_router.router)
app.include_router(chat_router.router)

@app.get("/")
def read_root():
    return {"message": "AI Chat API is running."}