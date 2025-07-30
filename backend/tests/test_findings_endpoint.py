"""
Additional tests for findings endpoint to increase coverage.

This module tests edge cases and error scenarios in the findings endpoint.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from uuid import uuid4

from fastapi import HTTPException
from app.api.endpoints.findings import (
    get_all_findings,
    get_document_findings,
    get_findings_summary,
)


class TestFindingsEndpointCoverage:
    """Additional tests for findings endpoint coverage."""
    
    @pytest.mark.asyncio
    async def test_get_all_findings_database_error(self):
        """Test get_all_findings with database error."""
        mock_db = AsyncMock()
        mock_db.count_documents.side_effect = Exception("Database connection failed")
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            with pytest.raises(HTTPException) as exc_info:
                await get_all_findings()
            
            assert exc_info.value.status_code == 500
            assert "Failed to retrieve findings" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_all_findings_empty_results(self):
        """Test get_all_findings with no documents."""
        mock_db = AsyncMock()
        mock_db.count_documents.return_value = 0
        mock_db.get_documents.return_value = []
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            result = await get_all_findings(page=1, page_size=20)
            
            assert result.total == 0
            assert result.page == 1
            assert result.page_size == 20
            assert result.findings == []
    
    @pytest.mark.asyncio
    async def test_get_document_findings_database_error(self):
        """Test get_document_findings with database error during document fetch."""
        mock_db = AsyncMock()
        mock_db.get_document.side_effect = Exception("Database error")
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            with pytest.raises(HTTPException) as exc_info:
                await get_document_findings("test-doc-id")
            
            assert exc_info.value.status_code == 500
            assert "Failed to retrieve document findings" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_document_findings_findings_fetch_error(self):
        """Test get_document_findings with error fetching findings."""
        doc_id = str(uuid4())
        mock_db = AsyncMock()
        mock_db.get_document.return_value = {
            "document_id": doc_id,
            "filename": "test.pdf",
            "file_size": 1024,
            "page_count": 1,
            "upload_timestamp": datetime.utcnow(),
            "processing_time_ms": 100.0,
            "status": "success",
            "error_message": None
        }
        mock_db.get_findings_by_document.side_effect = Exception("Findings fetch error")
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            with pytest.raises(HTTPException) as exc_info:
                await get_document_findings(doc_id)
            
            assert exc_info.value.status_code == 500
            assert "Failed to retrieve document findings" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_findings_summary_database_error(self):
        """Test get_findings_summary with database error."""
        mock_db = AsyncMock()
        mock_db.get_summary_statistics.side_effect = Exception("Statistics query failed")
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            with pytest.raises(HTTPException) as exc_info:
                await get_findings_summary()
            
            assert exc_info.value.status_code == 500
            assert "Failed to retrieve summary statistics" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_all_findings_with_all_filters(self):
        """Test get_all_findings with all filter parameters."""
        mock_db = AsyncMock()
        mock_db.count_documents.return_value = 5
        mock_db.get_documents.return_value = [
            {
                "document_id": str(uuid4()),
                "filename": "filtered.pdf",
                "file_size": 1024,
                "page_count": 1,
                "upload_timestamp": datetime(2024, 1, 15),
                "processing_time_ms": 100.0,
                "status": "success",
                "error_message": None
            }
        ]
        mock_db.get_findings_by_document.return_value = [
            {
                "finding_id": str(uuid4()),
                "document_id": str(uuid4()),
                "finding_type": "email",
                "value": "test@example.com",
                "page_number": 1,
                "confidence": 0.95,
                "context": "Email: test@example.com",
                "detected_at": datetime.utcnow()
            }
        ]
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            result = await get_all_findings(
                finding_type="email",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                page=1,
                page_size=10
            )
            
            assert result.total == 5
            assert result.page == 1
            assert result.page_size == 10
            assert len(result.findings) == 1
            
            # Verify filters were passed to count_documents
            mock_db.count_documents.assert_called_once_with(
                doc_id=ANY,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31)
            )
    
    @pytest.mark.asyncio
    async def test_get_document_findings_no_findings(self):
        """Test get_document_findings with document that has no findings."""
        doc_id = str(uuid4())
        mock_db = AsyncMock()
        mock_db.get_document.return_value = {
            "document_id": doc_id,
            "filename": "empty.pdf",
            "file_size": 1024,
            "page_count": 1,
            "upload_timestamp": datetime.utcnow(),
            "processing_time_ms": 100.0,
            "status": "success",
            "error_message": None
        }
        mock_db.get_findings_by_document.return_value = []
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            result = await get_document_findings(doc_id)
            
            assert result.document_id == doc_id
            assert result.filename == "empty.pdf"
            assert len(result.findings) == 0
            assert result.summary["total"] == 0
            assert result.summary.get("email", 0) == 0
            assert result.summary.get("ssn", 0) == 0
