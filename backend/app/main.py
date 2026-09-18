from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import resume, sessions, stats, voice

app = FastAPI(title="Interview Prep Simulator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # "*" locally (any localhost port); set CORS_ORIGINS to the real deployed frontend
    # URL(s) in production, comma-separated if there's more than one.
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(stats.router)
app.include_router(resume.router)
app.include_router(voice.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
