"""
Shared test fixtures and configuration for pytest.

This module provides common fixtures and test utilities used across
all test modules.
"""

import os
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"
os.environ["CLICKHOUSE_HOST"] = "localhost"
os.environ["CLICKHOUSE_PORT"] = "9000"
os.environ["CLICKHOUSE_DATABASE"] = "test_pdf_scanner"


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """
    Create a test client with proper configuration.
    
    This fixture ensures the TestClient is properly configured
    with the correct host header to pass TrustedHostMiddleware.
    """
    from app.main import app
    
    client = TestClient(app, base_url="http://localhost")
    
    # Override the host header for all requests
    original_request = client.request
    
    def request_with_host_header(method, url, **kwargs):
        headers = kwargs.get("headers", {})
        if headers is None:
            headers = {}
        headers["host"] = "localhost"
        kwargs["headers"] = headers
        return original_request(method, url, **kwargs)
    
    client.request = request_with_host_header
    
    yield client


@pytest.fixture(autouse=True)
def mock_settings():
    """
    Mock settings for testing.
    
    This fixture automatically mocks the settings to ensure
    tests don't depend on environment variables.
    """
    with patch("app.core.config.get_settings") as mock_get_settings:
        from app.core.config import Settings
        
        test_settings = Settings(
            app_name="PDF Scanner Test",
            app_version="1.0.0-test",
            debug=True,
            allowed_origins=["http://localhost", "http://testserver"],
            allowed_hosts=["localhost", "127.0.0.1", "testserver"],
            max_upload_size=50 * 1024 * 1024,
            allowed_file_extensions=[".pdf"],
            clickhouse_host="localhost",
            clickhouse_port=9000,
            clickhouse_database="test_pdf_scanner",
            clickhouse_user="default",
            clickhouse_password="",
        )
        
        mock_get_settings.return_value = test_settings
        yield mock_get_settings


@pytest.fixture
def mock_db_client():
    """
    Mock ClickHouse client for testing.
    
    This fixture provides a mock database client to avoid
    actual database connections during tests.
    """
    from unittest.mock import AsyncMock, MagicMock
    
    mock_client = MagicMock()
    mock_client.initialize = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.health_check = AsyncMock(return_value=True)
    mock_client.insert_document = AsyncMock()
    mock_client.insert_finding = AsyncMock()
    mock_client.insert_metric = AsyncMock()
    mock_client.get_document = AsyncMock()
    mock_client.get_documents = AsyncMock(return_value=[])
    mock_client.get_findings_by_document = AsyncMock(return_value=[])
    mock_client.count_documents = AsyncMock(return_value=0)
    mock_client.get_summary_statistics = AsyncMock(return_value={
        "total_documents": 0,
        "total_findings": 0,
        "findings_by_type": {},
        "avg_processing_time": 0.0,
        "total_pages": 0,
        "documents_with_findings": 0,
    })
    
    return mock_client


@pytest.fixture(autouse=True)
def mock_global_db_client(mock_db_client):
    """
    Automatically mock the global database client.
    
    This ensures all tests use the mock client instead of
    trying to connect to a real database.
    """
    with patch("app.main.db_client", mock_db_client):
        with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db_client):
            with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db_client):
                yield mock_db_client


@pytest.fixture
def sample_pdf_content() -> bytes:
    """
    Generate sample PDF content for testing.
    
    Returns:
        Bytes representing a valid PDF file.
    """
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    # Add test content
    pdf.drawString(100, 750, "Test PDF Document")
    pdf.drawString(100, 700, "Email: test@example.com")
    pdf.drawString(100, 650, "SSN: 123-45-6789")
    pdf.drawString(100, 600, "Another email: admin@company.org")
    
    # Add second page
    pdf.showPage()
    pdf.drawString(100, 750, "Page 2")
    pdf.drawString(100, 700, "Contact: john.doe@email.com")
    
    pdf.save()
    buffer.seek(0)
    return buffer.read()


@pytest.fixture
def sample_findings():
    """
    Generate sample findings for testing.
    
    Returns:
        List of finding dictionaries.
    """
    from datetime import datetime
    
    return [
        {
            "finding_id": "123e4567-e89b-12d3-a456-426614174000",
            "document_id": "doc-123",
            "finding_type": "email",
            "value": "test@example.com",
            "page_number": 1,
            "confidence": 1.0,
            "context": "Email: test@example.com",
            "detected_at": datetime.utcnow(),
        },
        {
            "finding_id": "456e7890-e89b-12d3-a456-426614174001",
            "document_id": "doc-123",
            "finding_type": "ssn",
            "value": "123-45-6789",
            "page_number": 1,
            "confidence": 0.95,
            "context": "SSN: 123-45-6789",
            "detected_at": datetime.utcnow(),
        },
    ]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_sessionstart(session):
    """Setup test environment before running tests."""

    os.environ["TESTING"] = "true"
    
    import logging
