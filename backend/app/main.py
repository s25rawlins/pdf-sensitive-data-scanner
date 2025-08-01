"""
FastAPI application for PDF sensitive data scanning service.

This module initializes the FastAPI application, configures middleware,
and includes all API routers for handling PDF uploads and findings retrieval.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.endpoints import findings, upload
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.db.clickhouse import ClickHouseClient, create_clickhouse_client

setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)

settings = get_settings()

# Global database client
db_client: ClickHouseClient = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Manage application lifecycle events.
    
    Handles startup and shutdown tasks including database connections
    and resource cleanup.
    """
    global db_client
    
    logger.info("Starting PDF sensitive data scanner application")
    
    try:
        db_client = create_clickhouse_client()
        await db_client.initialize()
        logger.info("ClickHouse connection established")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    logger.info("Shutting down application")
    
    try:
        if db_client:
            await db_client.close()
            logger.info("ClickHouse connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


async def log_requests(request: Request, call_next: Callable) -> Response:
    """
    Middleware to log only errors and summaries.
    
    Args:
        request: The incoming request
        call_next: The next middleware or endpoint handler
        
    Returns:
        The response from the endpoint
    """
    start_time = time.time()
    
    # Skip logging for health checks
    if "health" in request.url.path:
        return await call_next(request)
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Only log errors or slow requests
        if response.status_code >= 400:
            logger.error(
                f"{request.method} {request.url.path} - {response.status_code} ({duration:.1f}s)"
            )
        elif duration > 5.0:  # Log slow requests (> 5 seconds)
            logger.warning(
                f"Slow request: {request.method} {request.url.path} - {response.status_code} ({duration:.1f}s)"
            )
        elif request.method == "POST" and request.url.path == "/api/upload":
            logger.info(f"PDF uploaded successfully ({duration:.1f}s)")
            
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url.path} - {str(e)} ({duration:.1f}s)",
            exc_info=True
        )
        raise


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance.
    
    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for scanning PDF files for sensitive data",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    
    @app.middleware("http")
    async def request_logger(request: Request, call_next: Callable) -> Response:
        return await log_requests(request, call_next)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )
    
    app.include_router(
        upload.router,
        prefix="/api",
        tags=["upload"],
    )
    app.include_router(
        findings.router,
        prefix="/api",
        tags=["findings"],
    )
    
    @app.get("/", tags=["health"])
    async def root():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
        }
    
    @app.get("/api/health", tags=["health"])
    async def health_check():
        """Detailed health check including database status."""
        db_status = "healthy"
        
        try:
            if db_client:
                await db_client.health_check()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "unhealthy"
        
        return {
            "status": "healthy",
            "database": db_status,
            "app": settings.app_name,
            "version": settings.app_version,
        }
    
    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
