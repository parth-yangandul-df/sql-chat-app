import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import setup_logging
from app.db.session import engine

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Delegate to centralized loguru configuration.

    Idempotent — safe to call in --reload mode.
    """
    setup_logging(
        app_name=settings.app_name.lower(),
        level="DEBUG" if settings.debug else settings.log_level,
        file_enabled=settings.log_file_enabled,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
    )


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

    # Validate FieldRegistry completeness before traffic starts
    # Uses StartupIntegrityError (not assert) so it survives Python -O optimization
    from app.llm.graph.nodes.field_registry import validate_registry_completeness, StartupIntegrityError

    logger.info("QueryWise startup: validating field registry completeness")
    try:
        validate_registry_completeness()
        logger.info("QueryWise startup: field registry validated OK")
    except StartupIntegrityError as e:
        logger.error("QueryWise startup: field registry validation FAILED — %s", e)
        raise

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
