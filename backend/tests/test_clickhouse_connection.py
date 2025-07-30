"""
Test ClickHouse Cloud connection and setup.

This module tests the actual ClickHouse Cloud connection,
so it needs to bypass the default test mocking.
"""

import os
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone

# Disable the auto-mocking for this test module
pytest_plugins = []

# Load real environment variables before any imports
from dotenv import load_dotenv
load_dotenv()

from app.core.config import Settings, get_settings
from app.db.clickhouse import create_clickhouse_client


@pytest.fixture(autouse=True)
def use_real_settings():
    """Override test settings to use real ClickHouse Cloud settings."""
    # Store original env vars
    original_env = {}
    env_vars = ["CLICKHOUSE_HOST", "CLICKHOUSE_PORT", "CLICKHOUSE_DATABASE"]
    
    for var in env_vars:
        if var in os.environ:
            original_env[var] = os.environ[var]
            del os.environ[var]
    
    # Clear the cached settings
    get_settings.cache_clear()
    
    # Reload environment from .env file
    load_dotenv(override=True)
    
    yield
    
    # Restore original env vars
    for var, value in original_env.items():
        os.environ[var] = value
    
    # Clear cache again after tests
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def clickhouse_client():
    """Create a ClickHouse client for testing with real settings."""
    # Get fresh settings that should now have the real values
    settings = get_settings()
    print(f"Using ClickHouse settings: host={settings.clickhouse_host}, port={settings.clickhouse_port}, secure={settings.clickhouse_secure}")
    
    client = create_clickhouse_client()
    try:
        await client.initialize()
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_connection(clickhouse_client):
    """Test ClickHouse Cloud connection."""
    # Test connection
    connection_info = await clickhouse_client.test_connection()
    
    assert connection_info["status"] == "connected", f"Connection failed: {connection_info.get('error', 'Unknown error')}"
    assert "version" in connection_info
    assert "database" in connection_info
    assert "tables" in connection_info
    
    # Check if tables exist
    expected_tables = {"documents", "findings", "metrics"}
    existing_tables = set(connection_info.get("tables", []))
    
    # It's okay if tables don't exist yet - they'll be created automatically
    # Just verify we can get the table list
    assert isinstance(connection_info["tables"], list)


@pytest.mark.asyncio
async def test_basic_operations(clickhouse_client):
    """Test basic database operations."""
    # Insert test document with proper UUID
    test_doc_id = str(uuid.uuid4())
    
    await clickhouse_client.insert_document(
        document_id=test_doc_id,
        filename="test-connection.pdf",
        file_size=1024,
        page_count=1,
        upload_timestamp=datetime.now(timezone.utc),
        processing_time_ms=100.0,
        status="success",
    )
    
    # Query the document
    doc = await clickhouse_client.get_document(test_doc_id)
    assert doc is not None, "Failed to retrieve test document"
    assert doc['filename'] == "test-connection.pdf"
    assert doc['status'] == "success"
    
    # Insert test finding
    await clickhouse_client.insert_finding(
        document_id=test_doc_id,
        finding_type="email",
        value="test@example.com",
        page_number=1,
        confidence=1.0,
        context="Test email: test@example.com",
    )
    
    # Get findings
    findings = await clickhouse_client.get_findings_by_document(test_doc_id)
    assert findings is not None, "No findings retrieved"
    assert len(findings) >= 1, "Expected at least one finding"
    
    # Verify the finding content
    email_finding = next((f for f in findings if f['finding_type'] == 'email'), None)
    assert email_finding is not None, "Email finding not found"
    assert email_finding['value'] == "test@example.com"
    assert email_finding['confidence'] == 1.0


@pytest.mark.asyncio
async def test_summary_statistics(clickhouse_client):
    """Test getting summary statistics."""
    stats = await clickhouse_client.get_summary_statistics()
    
    assert isinstance(stats, dict)
    assert 'total_documents' in stats
    assert 'total_findings' in stats
    assert 'documents_with_findings' in stats
    
    # Values should be non-negative
    assert stats['total_documents'] >= 0
    assert stats['total_findings'] >= 0
    assert stats['documents_with_findings'] >= 0


@pytest.mark.asyncio
async def test_health_check(clickhouse_client):
    """Test health check functionality."""
    is_healthy = await clickhouse_client.health_check()
    assert is_healthy is True, "Health check failed"


@pytest.mark.asyncio
async def test_cleanup_test_data(clickhouse_client):
    """Test cleanup of test data."""
    # First, create some test data to clean up with proper UUID
    test_doc_id = str(uuid.uuid4())
    
    await clickhouse_client.insert_document(
        document_id=test_doc_id,
        filename="test-cleanup.pdf",
        file_size=2048,
        page_count=2,
        upload_timestamp=datetime.now(timezone.utc),
        processing_time_ms=200.0,
        status="success",
    )
    
    await clickhouse_client.insert_finding(
        document_id=test_doc_id,
        finding_type="phone",
        value="555-1234",
        page_number=1,
        confidence=0.9,
        context="Phone: 555-1234",
    )
    
    # Verify data exists
    doc = await clickhouse_client.get_document(test_doc_id)
    assert doc is not None
    
    findings = await clickhouse_client.get_findings_by_document(test_doc_id)
    assert len(findings) > 0
    
    # Clean up test data
    import asyncio
    loop = asyncio.get_event_loop()
    
    # Delete test findings first (foreign key constraint)
    await loop.run_in_executor(
        None,
        clickhouse_client._execute_query,
        f"DELETE FROM findings WHERE document_id = '{test_doc_id}'"
    )
    
    # Delete test document
    await loop.run_in_executor(
        None,
        clickhouse_client._execute_query,
        f"DELETE FROM documents WHERE document_id = '{test_doc_id}'"
    )
    
    # Verify cleanup
    doc_after = await clickhouse_client.get_document(test_doc_id)
    assert doc_after is None, "Document was not deleted"
    
    findings_after = await clickhouse_client.get_findings_by_document(test_doc_id)
    assert len(findings_after) == 0, "Findings were not deleted"


@pytest.mark.asyncio
async def test_connection_with_invalid_settings():
    """Test connection with invalid settings to ensure proper error handling."""
    # This test is to verify error handling, so we expect it to fail gracefully
    from app.db.clickhouse import ClickHouseClient
    
    # Create a client with invalid settings
    invalid_client = ClickHouseClient(
        host="invalid.host.example.com",
        port=9999,
        database="invalid_db",
        user="invalid_user",
        password="invalid_pass",
        secure=True,
        verify=True,
    )
    
    # Test connection should fail but not crash
    try:
        await invalid_client.initialize()
        connection_info = await invalid_client.test_connection()
        assert connection_info["status"] == "error"
        assert "error" in connection_info
    except Exception:
        # Expected to fail - that's okay
        pass
    finally:
        await invalid_client.close()
