from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import sessions

app = FastAPI(title="Interview Prep Simulator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten once the frontend origin is known (Phase 2)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
