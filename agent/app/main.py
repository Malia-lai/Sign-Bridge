from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, sentence

app = FastAPI(title="Sign Bridge Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sentence.router)
app.include_router(health.router, prefix="/api")
app.include_router(sentence.router, prefix="/api")