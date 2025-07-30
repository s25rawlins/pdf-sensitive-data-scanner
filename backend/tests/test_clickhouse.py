"""
Tests for ClickHouse database client.

This module tests the ClickHouse client functionality including
connection management, queries, and error handling.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from clickhouse_driver.errors import Error as ClickHouseError

from app.db.clickhouse import ClickHouseClient, create_clickhouse_client
from app.db.models import ProcessingStatus, FindingType, MetricType


class TestClickHouseClient:
    """Test suite for ClickHouse client."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock ClickHouse client."""
        mock = MagicMock()
        mock.execute = MagicMock()
        mock.execute_iter = MagicMock()
        return mock
    
    @pytest.fixture
    def clickhouse_client(self, mock_client):
        """Create ClickHouseClient instance with mocked connection."""
        with patch("app.db.clickhouse.Client", return_value=mock_client):
            client = ClickHouseClient(
                host="localhost",
                port=9000,
                database="test_db",
                user="test_user",
                password="test_pass"
            )
            client._client = mock_client
            return client
    
    def test_client_initialization(self):
        """Test ClickHouseClient initialization."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test_db",
            user="test_user",
            password="test_pass"
        )
        
        assert client.host == "localhost"
        assert client.port == 9000
        assert client.database == "test_db"
        assert client.user == "test_user"
        assert client.password == "test_pass"
        assert client._client is None
    
    @pytest.mark.asyncio
    async def test_initialize(self, clickhouse_client, mock_client):
        """Test database initialization."""
        await clickhouse_client.initialize()
        
        # Check that tables were created
        assert mock_client.execute.call_count >= 3  # At least 3 CREATE TABLE statements
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, clickhouse_client, mock_client):
        """Test successful health check."""
        mock_client.execute.return_value = [(1,)]
        
        result = await clickhouse_client.health_check()
        
        assert result is True
        mock_client.execute.assert_called_with("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, clickhouse_client, mock_client):
        """Test failed health check."""
        mock_client.execute.side_effect = ClickHouseError("Connection failed")
        
        result = await clickhouse_client.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_insert_document(self, clickhouse_client, mock_client):
        """Test inserting a document."""
        doc_id = str(uuid4())
        
        await clickhouse_client.insert_document(
            document_id=doc_id,
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=150.5,
            status=ProcessingStatus.SUCCESS,
            error_message=None
        )
        
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "INSERT INTO documents" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_insert_finding(self, clickhouse_client, mock_client):
        """Test inserting a finding."""
        finding_id = str(uuid4())
        doc_id = str(uuid4())
        
        await clickhouse_client.insert_finding(
            finding_id=finding_id,
            document_id=doc_id,
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
            detected_at=datetime.utcnow()
        )
        
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "INSERT INTO findings" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_insert_metric(self, clickhouse_client, mock_client):
        """Test inserting a metric."""
        metric_id = str(uuid4())
        doc_id = str(uuid4())
        
        await clickhouse_client.insert_metric(
            metric_id=metric_id,
            document_id=doc_id,
            metric_type=MetricType.PROCESSING_TIME,
            value=150.5,
            recorded_at=datetime.utcnow()
        )
        
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "INSERT INTO metrics" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_get_document(self, clickhouse_client, mock_client):
        """Test retrieving a document."""
        doc_id = str(uuid4())
        mock_client.execute.return_value = [(
            doc_id,
            "test.pdf",
            1024,
            5,
            datetime.utcnow(),
            150.5,
            "success",
            None
        )]
        
        result = await clickhouse_client.get_document(doc_id)
        
        assert result is not None
        assert result["document_id"] == doc_id
        assert result["filename"] == "test.pdf"
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, clickhouse_client, mock_client):
        """Test retrieving non-existent document."""
        mock_client.execute.return_value = []
        
        result = await clickhouse_client.get_document("non-existent-id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_documents(self, clickhouse_client, mock_client):
        """Test retrieving multiple documents."""
        mock_client.execute.return_value = [
            (str(uuid4()), "doc1.pdf", 1024, 5, datetime.utcnow(), 150.5, "success", None),
            (str(uuid4()), "doc2.pdf", 2048, 10, datetime.utcnow(), 200.0, "success", None),
        ]
        
        results = await clickhouse_client.get_documents(limit=10, offset=0)
        
        assert len(results) == 2
        assert results[0]["filename"] == "doc1.pdf"
        assert results[1]["filename"] == "doc2.pdf"
    
    @pytest.mark.asyncio
    async def test_get_findings_by_document(self, clickhouse_client, mock_client):
        """Test retrieving findings for a document."""
        doc_id = str(uuid4())
        mock_client.execute.return_value = [
            (str(uuid4()), doc_id, "email", "test@example.com", 1, 0.95, "Email: test@example.com", datetime.utcnow()),
            (str(uuid4()), doc_id, "ssn", "123-45-6789", 2, 0.90, "SSN: 123-45-6789", datetime.utcnow()),
        ]
        
        results = await clickhouse_client.get_findings_by_document(doc_id)
        
        assert len(results) == 2
        assert results[0]["finding_type"] == "email"
        assert results[1]["finding_type"] == "ssn"
    
    @pytest.mark.asyncio
    async def test_count_documents(self, clickhouse_client, mock_client):
        """Test counting documents."""
        mock_client.execute.return_value = [(100,)]
        
        count = await clickhouse_client.count_documents()
        
        assert count == 100
    
    @pytest.mark.asyncio
    async def test_count_documents_with_filters(self, clickhouse_client, mock_client):
        """Test counting documents with filters."""
        mock_client.execute.return_value = [(50,)]
        
        count = await clickhouse_client.count_documents(
            finding_type=FindingType.EMAIL,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31)
        )
        
        assert count == 50
        call_args = mock_client.execute.call_args[0][0]
        assert "WHERE" in call_args
        assert "finding_type = 'email'" in call_args
    
    @pytest.mark.asyncio
    async def test_get_summary_statistics(self, clickhouse_client, mock_client):
        """Test retrieving summary statistics."""
        # Mock multiple queries
        mock_client.execute.side_effect = [
            [(100,)],  # total_documents
            [(250,)],  # total_findings
            [("email", 150), ("ssn", 100)],  # findings_by_type
            [(125.5,)],  # avg_processing_time
            [(500,)],  # total_pages
            [(80,)],  # documents_with_findings
        ]
        
        stats = await clickhouse_client.get_summary_statistics()
        
        assert stats["total_documents"] == 100
        assert stats["total_findings"] == 250
        assert stats["findings_by_type"]["email"] == 150
        assert stats["findings_by_type"]["ssn"] == 100
        assert stats["avg_processing_time"] == 125.5
        assert stats["total_pages"] == 500
        assert stats["documents_with_findings"] == 80
    
    @pytest.mark.asyncio
    async def test_close(self, clickhouse_client, mock_client):
        """Test closing the connection."""
        await clickhouse_client.close()
        
        # Should not raise any errors
        assert True
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, clickhouse_client, mock_client):
        """Test query execution with retry on success."""
        mock_client.execute.return_value = [(1,)]
        
        result = await clickhouse_client._execute_with_retry("SELECT 1")
        
        assert result == [(1,)]
        assert mock_client.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_failure_then_success(self, clickhouse_client, mock_client):
        """Test query execution with retry after initial failure."""
        mock_client.execute.side_effect = [
            ClickHouseError("Connection lost"),
            [(1,)]
        ]
        
        result = await clickhouse_client._execute_with_retry("SELECT 1")
        
        assert result == [(1,)]
        assert mock_client.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_max_retries(self, clickhouse_client, mock_client):
        """Test query execution failing after max retries."""
        mock_client.execute.side_effect = ClickHouseError("Connection lost")
        
        with pytest.raises(ClickHouseError):
            await clickhouse_client._execute_with_retry("SELECT 1", max_retries=3)
        
        assert mock_client.execute.call_count == 3
    
    def test_create_clickhouse_client(self):
        """Test factory function for creating client."""
        with patch("app.db.clickhouse.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                clickhouse_host="localhost",
                clickhouse_port=9000,
                clickhouse_database="test_db",
                clickhouse_user="test_user",
                clickhouse_password="test_pass"
            )
            
            client = create_clickhouse_client()
            
            assert isinstance(client, ClickHouseClient)
            assert client.host == "localhost"
            assert client.database == "test_db"


class TestClickHouseClientErrorHandling:
    """Test error handling in ClickHouse client."""
    
    @pytest.fixture
    def clickhouse_client(self):
        """Create ClickHouseClient instance."""
        return ClickHouseClient(
            host="localhost",
            port=9000,
            database="test_db"
        )
    
    @pytest.mark.asyncio
    async def test_insert_document_error(self, clickhouse_client):
        """Test error handling in document insertion."""
        with patch.object(clickhouse_client, "_execute_with_retry", side_effect=ClickHouseError("Insert failed")):
            with pytest.raises(ClickHouseError):
                await clickhouse_client.insert_document(
                    document_id=str(uuid4()),
                    filename="test.pdf",
                    file_size=1024,
                    page_count=5,
                    upload_timestamp=datetime.utcnow(),
                    processing_time_ms=150.5,
                    status=ProcessingStatus.SUCCESS
                )
    
    @pytest.mark.asyncio
    async def test_get_documents_error(self, clickhouse_client):
        """Test error handling in document retrieval."""
        with patch.object(clickhouse_client, "_execute_with_retry", side_effect=ClickHouseError("Query failed")):
            with pytest.raises(ClickHouseError):
                await clickhouse_client.get_documents()
