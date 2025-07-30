"""
Tests for the main FastAPI application module.

This module tests the application lifecycle, startup/shutdown events,
and global configurations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import create_application, lifespan


class TestApplication:
    """Test suite for main application."""
    
    def test_create_application(self):
        """Test application creation."""
        with patch("app.main.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                app_name="Test App",
                app_version="1.0.0",
                allowed_origins=["http://localhost"],
                allowed_hosts=["localhost"],
            )
            
            app = create_application()
            
            assert app.title == "Test App"
            assert app.version == "1.0.0"
            assert app.docs_url == "/api/docs"
            assert app.redoc_url == "/api/redoc"
            assert app.openapi_url == "/api/openapi.json"
    
    @pytest.mark.asyncio
    async def test_lifespan_success(self):
        """Test successful application lifecycle."""
        mock_app = MagicMock()
        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock()
        mock_db_client.close = AsyncMock()
        
        with patch("app.main.create_clickhouse_client", return_value=mock_db_client):
            with patch("app.main.logger") as mock_logger:
                async with lifespan(mock_app):
                    # Startup
                    mock_logger.info.assert_any_call("Starting PDF sensitive data scanner application")
                    mock_db_client.initialize.assert_called_once()
                    mock_logger.info.assert_any_call("ClickHouse connection established")
                
                # Shutdown
                mock_logger.info.assert_any_call("Shutting down application")
                mock_db_client.close.assert_called_once()
                mock_logger.info.assert_any_call("ClickHouse connection closed")
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_failure(self):
        """Test application lifecycle with startup failure."""
        mock_app = MagicMock()
        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock(side_effect=Exception("Connection failed"))
        
        with patch("app.main.create_clickhouse_client", return_value=mock_db_client):
            with patch("app.main.logger") as mock_logger:
                with pytest.raises(Exception, match="Connection failed"):
                    async with lifespan(mock_app):
                        pass
                
                mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lifespan_shutdown_error(self):
        """Test application lifecycle with shutdown error."""
        mock_app = MagicMock()
        mock_db_client = AsyncMock()
        mock_db_client.initialize = AsyncMock()
        mock_db_client.close = AsyncMock(side_effect=Exception("Close failed"))
        
        with patch("app.main.create_clickhouse_client", return_value=mock_db_client):
            with patch("app.main.logger") as mock_logger:
                async with lifespan(mock_app):
                    pass
                
                # Should log error but not raise
                mock_logger.error.assert_any_call("Error during shutdown: Close failed")
    
    def test_root_endpoint(self, test_client):
        """Test root health check endpoint."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data
    
    def test_api_health_endpoint(self, test_client):
        """Test API health check endpoint."""
        with patch("app.main.db_client") as mock_db:
            mock_db.health_check = AsyncMock(return_value=True)
            
            response = test_client.get("/api/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "healthy"
    
    def test_api_health_endpoint_db_unhealthy(self, test_client):
        """Test API health check with unhealthy database."""
        with patch("app.main.db_client") as mock_db:
            mock_db.health_check = AsyncMock(side_effect=Exception("DB Error"))
            
            with patch("app.main.logger") as mock_logger:
                response = test_client.get("/api/health")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["database"] == "unhealthy"
                mock_logger.error.assert_called_once()
    
    def test_middleware_configuration(self):
        """Test middleware is properly configured."""
        with patch("app.main.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                app_name="Test App",
                app_version="1.0.0",
                allowed_origins=["http://localhost", "http://example.com"],
                allowed_hosts=["localhost", "example.com"],
            )
            
            app = create_application()
            
            # Check middleware stack
            middleware_types = [type(m) for m in app.middleware]
            middleware_names = [type(m).__name__ for m in app.middleware]
            
            # Should have CORS and TrustedHost middleware
            assert any("CORSMiddleware" in str(m) for m in middleware_names)
            assert any("TrustedHostMiddleware" in str(m) for m in middleware_names)
    
    def test_router_inclusion(self):
        """Test all routers are included."""
        app = create_application()
        
        # Get all routes
        routes = [route.path for route in app.routes]
        
        # Check upload endpoints
        assert "/api/upload" in routes
        
        # Check findings endpoints
        assert "/api/findings" in routes
        assert "/api/findings/{document_id}" in routes
        assert "/api/findings/stats/summary" in routes
        
        # Check health endpoints
        assert "/" in routes
        assert "/api/health" in routes


class TestMainModule:
    """Test main module execution."""
    
    def test_main_module_execution(self):
        """Test main module runs uvicorn when executed directly."""
        with patch("app.main.__name__", "__main__"):
            with patch("app.main.uvicorn") as mock_uvicorn:
                # Re-import to trigger __main__ block
                import importlib
                import app.main
                importlib.reload(app.main)
                
                mock_uvicorn.run.assert_called_once_with(
                    "app.main:app",
                    host="0.0.0.0",
                    port=8000,
                    reload=True,
                    log_level="info",
                )
