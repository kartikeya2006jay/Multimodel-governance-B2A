"""
backend/main.py — Application entry point.
Wires FastAPI app, routers, DB init, lifespan events.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.observability import init_metrics
from app.models.base import init_db
from app.api.routes import api_router


# ── Lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup and shutdown logic."""
    await init_db()         # initialise tables
    init_metrics()          # start Prometheus metrics server
    
    from app.agents.registry import register_all_agents
    register_all_agents()   # register default mesh agents
    
    yield
    # teardown (add cleanup here as needed)


# ── App Factory ──────────────────────────────────────────────────

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade Multi-Agent Governance Middleware.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        swagger_ui_parameters={"deepLinking": True}
    )

    # Simplified Operation IDs to avoid Swagger UI underscore warnings
    from fastapi.routing import APIRoute
    def simplify_operation_ids(app: FastAPI) -> None:
        for route in app.routes:
            if isinstance(route, APIRoute):
                route.operation_id = route.name.replace("_", "-")

    simplify_operation_ids(application)

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routers
    application.include_router(api_router, prefix="/api/v1")

    # Health check (unauthenticated)
    @application.get("/health", tags=["System"])
    async def health():
        return JSONResponse({"status": "ok", "service": settings.APP_NAME})

    return application


app = create_application()
