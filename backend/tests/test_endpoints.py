"""
Tests for API endpoint modules.

This module tests the endpoint functions directly to ensure
proper coverage of error handling and edge cases.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from app.api.endpoints import upload, findings
from app.db.models import ProcessingStatus, FindingType


class TestUploadEndpoint:
    """Test suite for upload endpoint functions."""
    
    @pytest.mark.asyncio
    async def test_get_db_client(self):
        """Test getting database client."""
        mock_client = MagicMock()
        with patch("app.api.endpoints.upload.get_db_client", return_value=mock_client):
            result = upload.get_db_client()
            assert result == mock_client
    
    @pytest.mark.asyncio
    async def test_upload_pdf_success_with_findings(self):
        """Test successful PDF upload with findings."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nTest content\n%%EOF")
        
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.document_id = str(uuid4())
        mock_result.findings = [
            MagicMock(
                finding_type="email",
                value="test@example.com",
                page_number=1,
                confidence=0.95,
                context="Email: test@example.com"
            )
        ]
        mock_result.page_count = 1
        mock_result.processing_time_ms = 100.0
        mock_result.file_size = 1024
        mock_processor.process_pdf.return_value = mock_result
        
        mock_db = AsyncMock()
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        result = await upload.upload_pdf(mock_file)
                        
                        assert result["status"] == "success"
                        assert result["findings_count"] == 1
                        assert mock_db.insert_document.called
                        assert mock_db.insert_finding.called
                        assert mock_db.insert_metric.called
    
    @pytest.mark.asyncio
    async def test_upload_pdf_file_read_error(self):
        """Test upload with file read error."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(side_effect=Exception("Read error"))
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with pytest.raises(HTTPException) as exc_info:
                await upload.upload_pdf(mock_file)
            
            assert exc_info.value.status_code == 400
            assert "Failed to read uploaded file" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_upload_pdf_processing_error(self):
        """Test upload with processing error."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nTest\n%%EOF")
        
        mock_processor = MagicMock()
        mock_processor.process_pdf.side_effect = Exception("Processing failed")
        
        mock_db = AsyncMock()
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        with pytest.raises(HTTPException) as exc_info:
                            await upload.upload_pdf(mock_file)
                        
                        assert exc_info.value.status_code == 500


class TestFindingsEndpoint:
    """Test suite for findings endpoint functions."""
    
    @pytest.mark.asyncio
    async def test_get_db_client(self):
        """Test getting database client."""
        mock_client = MagicMock()
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_client):
            result = findings.get_db_client()
            assert result == mock_client
    
    @pytest.mark.asyncio
    async def test_get_findings_with_filters(self):
        """Test getting findings with all filters."""
        mock_db = AsyncMock()
        mock_db.count_documents.return_value = 10
        mock_db.get_documents.return_value = [
            {
                "document_id": str(uuid4()),
                "filename": "test.pdf",
                "file_size": 1024,
                "page_count": 1,
                "upload_timestamp": datetime.utcnow(),
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
            result = await findings.get_all_findings(
                finding_type="email",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                page=2,
                page_size=5
            )
            
            assert result.total == 10
            assert result.page == 2
            assert result.page_size == 5
            assert len(result.findings) == 1
            
            # Check that filters were passed correctly
            mock_db.count_documents.assert_called_with(
                doc_id=ANY,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31)
            )
    
    @pytest.mark.asyncio
    async def test_get_document_findings_not_found(self):
        """Test getting findings for non-existent document."""
        mock_db = AsyncMock()
        mock_db.get_document.return_value = None
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            with pytest.raises(HTTPException) as exc_info:
                await findings.get_document_findings("non-existent-id")
            
            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_document_findings_success(self):
        """Test successfully getting document findings."""
        doc_id = str(uuid4())
        mock_db = AsyncMock()
        mock_db.get_document.return_value = {
            "document_id": doc_id,
            "filename": "test.pdf",
            "file_size": 1024,
            "page_count": 2,
            "upload_timestamp": datetime.utcnow(),
            "processing_time_ms": 100.0,
            "status": "success",
            "error_message": None
        }
        mock_db.get_findings_by_document.return_value = [
            {
                "finding_id": str(uuid4()),
                "document_id": doc_id,
                "finding_type": "email",
                "value": "test@example.com",
                "page_number": 1,
                "confidence": 0.95,
                "context": "Email: test@example.com",
                "detected_at": datetime.utcnow()
            },
            {
                "finding_id": str(uuid4()),
                "document_id": doc_id,
                "finding_type": "ssn",
                "value": "123-45-6789",
                "page_number": 2,
                "confidence": 0.90,
                "context": "SSN: 123-45-6789",
                "detected_at": datetime.utcnow()
            }
        ]
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            result = await findings.get_document_findings(doc_id)
            
            assert result.document_id == doc_id
            assert result.filename == "test.pdf"
            assert len(result.findings) == 2
            assert result.summary["total"] == 2
            assert result.summary["email"] == 1
            assert result.summary["ssn"] == 1
    
    @pytest.mark.asyncio
    async def test_get_summary_statistics(self):
        """Test getting summary statistics."""
        mock_db = AsyncMock()
        mock_db.get_summary_statistics.return_value = {
            "total_documents": 100,
            "total_findings": 250,
            "findings_by_type": {"email": 150, "ssn": 100},
            "avg_processing_time": 125.5,
            "total_pages": 500,
            "documents_with_findings": 80
        }
        
        with patch("app.api.endpoints.findings.get_db_client", return_value=mock_db):
            result = await findings.get_findings_summary()
            
            assert result["total_documents"] == 100
            assert result["total_findings"] == 250
            assert result["average_processing_time_ms"] == 125.5


class TestEndpointHelpers:
    """Test helper functions in endpoints."""
    
    def test_validate_pagination(self):
        """Test pagination validation in endpoints."""
        from app.utils.validators import validate_pagination
        
        # Test defaults
        page, page_size = validate_pagination(None, None)
        assert page == 1
        assert page_size == 20
        
        # Test custom values
        page, page_size = validate_pagination(5, 50)
        assert page == 5
        assert page_size == 50
    
    def test_validate_finding_type(self):
        """Test finding type validation."""
        from app.utils.validators import validate_finding_type
        
        assert validate_finding_type("email") == "email"
        assert validate_finding_type("ssn") == "ssn"
        assert validate_finding_type(None) is None
        assert validate_finding_type("") is None
        
        with pytest.raises(HTTPException):
            validate_finding_type("invalid")
