from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import engine
from app.routes import activities, auth, files, folders, search, shares, starred, trash

app = FastAPI(title="Cloud Drive API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # For the MVP we create tables directly. Swap for Alembic migrations
    # once the schema stabilizes / before a real production rollout.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(folders.router)
app.include_router(files.router)
app.include_router(shares.router)
app.include_router(search.router)
app.include_router(trash.router)
app.include_router(starred.router)
app.include_router(activities.router)
