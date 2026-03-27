import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.db.session import engine

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Attach a StreamHandler to the root logger so app.* messages reach stdout.

    Uvicorn only configures its own loggers (uvicorn, uvicorn.access). Without
    this, any logger under the 'app' namespace silently drops messages because
    the root logger has no handler.  We add one only if none is present yet
    (idempotent — safe to call in --reload mode).
    """
    root = logging.getLogger()
    has_stream = any(isinstance(h, logging.StreamHandler) and h.stream in (sys.stdout, sys.stderr) for h in root.handlers)
    if not has_stream:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        root.addHandler(handler)
    # Ensure all app.* loggers emit INFO and above
    logging.getLogger("app").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging FIRST — before any startup work emits log messages
    _configure_logging()

    # Startup: ensure vector columns match configured dimension
    from app.services.setup_service import ensure_embedding_dimensions

    logger.info("QueryWise startup: checking embedding dimensions")
    try:
        await ensure_embedding_dimensions()
    except Exception:
        logger.warning(
            "ensure_embedding_dimensions() failed; "
            "vector search may be unavailable until DB is reachable",
            exc_info=True,
        )

    # Pre-embed intent catalog so first query does not pay embedding cost
    # Wrapped in try/except — failure logs warning but does NOT prevent startup
    from app.llm.graph.intent_catalog import INTENT_CATALOG, ensure_catalog_embedded

    logger.info("QueryWise startup: pre-embedding intent catalog (%d entries)", len(INTENT_CATALOG))
    try:
        await ensure_catalog_embedded()
        logger.info("QueryWise startup: intent catalog embedded OK")
    except Exception:
        logger.warning(
            "Intent catalog pre-embedding failed; first query will embed on demand",
            exc_info=True,
        )

    if settings.auto_setup_sample_db:
        from app.services.setup_service import auto_setup_sample_db

        logger.info("QueryWise startup: running auto-setup for sample DB")
        await auto_setup_sample_db()

    logger.info("QueryWise startup complete")
    yield
    # Shutdown
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
