"""MandiSync FastAPI application entrypoint."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

load_dotenv(Path(__file__).resolve().parent / ".env")

from rate_limit import limiter, rate_limit_exceeded_handler
from routers.admin import router as admin_router
from routers.arbitrage import router as arbitrage_router
from routers.leads import router as leads_router
from security import parse_allowed_origins

app = FastAPI(
    title="MandiSync API",
    description="Indian crop arbitrage and logistics routing API.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Exact origins from ALLOWED_ORIGINS, plus GitHub Pages project sites.
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(),
    allow_origin_regex=r"^https://[a-z0-9-]+\.github\.io$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key", "Content-Type"],
)

app.include_router(arbitrage_router, prefix="/api/arbitrage")
app.include_router(leads_router, prefix="/api/leads")
app.include_router(admin_router, prefix="/api/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "MandiSync API",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
