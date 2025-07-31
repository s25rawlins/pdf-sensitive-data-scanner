"""
Tests for upload endpoint edge cases.

This module tests additional scenarios for the upload endpoint
to increase code coverage.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from app.api.endpoints.upload import upload_pdf, get_db_client
from app.services.pdf_processor import (
    PDFSizeLimitError, 
    CorruptedPDFError, 
    PDFProcessingError
)
from app.db.models import ProcessingStatus


class TestUploadEndpointCoverage:
    """Additional tests for upload endpoint coverage."""
    
    @pytest.mark.asyncio
    async def test_upload_pdf_size_limit_error(self):
        """Test upload with PDF size limit error."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "large.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nLarge content\n%%EOF")
        
        mock_processor = MagicMock()
        mock_processor.process_pdf.side_effect = PDFSizeLimitError("File too large")
        
        mock_db = AsyncMock()
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        with pytest.raises(HTTPException) as exc_info:
                            await upload_pdf(mock_file)
                        
                        assert exc_info.value.status_code == 413
                        assert "File too large" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_upload_pdf_corrupted_error(self):
        """Test upload with corrupted PDF error."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "corrupted.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nCorrupted\n%%EOF")
        
        mock_processor = MagicMock()
        mock_processor.process_pdf.side_effect = CorruptedPDFError("PDF is corrupted")
        
        mock_db = AsyncMock()
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        with pytest.raises(HTTPException) as exc_info:
                            await upload_pdf(mock_file)
                        
                        assert exc_info.value.status_code == 422
                        assert "PDF is corrupted" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_upload_pdf_processing_error_specific(self):
        """Test upload with specific PDF processing error."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "error.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nContent\n%%EOF")
        
        mock_processor = MagicMock()
        mock_processor.process_pdf.side_effect = PDFProcessingError("Processing failed")
        
        mock_db = AsyncMock()
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        with pytest.raises(HTTPException) as exc_info:
                            await upload_pdf(mock_file)
                        
                        assert exc_info.value.status_code == 500
                        assert "Failed to process PDF" in str(exc_info.value.detail)
                        
                        # Check that document was inserted with failed status
                        mock_db.insert_document.assert_called_once()
                        call_args = mock_db.insert_document.call_args[1]
                        assert call_args["status"] == "failed"
                        assert call_args["error_message"] == "Processing failed"
    
    @pytest.mark.asyncio
    async def test_upload_pdf_with_metrics(self):
        """Test upload with metric insertion."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "metrics.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nContent\n%%EOF")
        
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.document_id = str(uuid4())
        mock_result.findings = []
        mock_result.page_count = 5
        mock_result.processing_time_ms = 250.5
        mock_result.file_size = 2048
        mock_result.status = "success"
        mock_processor.process_pdf.return_value = mock_result
        
        mock_db = AsyncMock()
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        result = await upload_pdf(mock_file)
                        
                        assert result["status"] == "success"
                        
                        # Check metrics were inserted
                        assert mock_db.insert_metric.call_count == 3  # processing_time, page_count, file_size
                        
                        # Verify metric types
                        metric_calls = mock_db.insert_metric.call_args_list
                        metric_types = [call[1]["metric_type"] for call in metric_calls]
                        assert "processing_time" in metric_types
                        assert "page_count" in metric_types
                        assert "file_size" in metric_types
    
    @pytest.mark.asyncio
    async def test_upload_pdf_database_error_during_insert(self):
        """Test upload with database error during document insert."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "db_error.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nContent\n%%EOF")
        
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.document_id = str(uuid4())
        mock_result.findings = []
        mock_result.page_count = 1
        mock_result.processing_time_ms = 100.0
        mock_result.file_size = 1024
        mock_result.status = "success"
        mock_processor.process_pdf.return_value = mock_result
        
        mock_db = AsyncMock()
        mock_db.insert_document.side_effect = Exception("Database error")
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        
                        with pytest.raises(HTTPException) as exc_info:
                            await upload_pdf(mock_file)
                        
                        assert exc_info.value.status_code == 500
                        assert "An unexpected error occurred while processing the PDF" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_upload_pdf_finding_insert_continues_on_error(self):
        """Test that upload continues even if finding insert fails."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "finding_error.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nContent\n%%EOF")
        
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.document_id = str(uuid4())
        mock_finding = MagicMock()
        mock_finding.type.value = "email"
        mock_finding.value = "test@example.com"
        mock_finding.page_number = 1
        mock_finding.confidence = 0.95
        mock_finding.context = "Email: test@example.com"
        mock_result.findings = [mock_finding]
        mock_result.page_count = 1
        mock_result.processing_time_ms = 100.0
        mock_result.file_size = 1024
        mock_result.status = "success"
        mock_processor.process_pdf.return_value = mock_result
        
        mock_db = AsyncMock()
        mock_db.insert_finding.side_effect = Exception("Finding insert error")
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                    with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                        mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                        with patch("app.api.endpoints.upload.logger") as mock_logger:
                            
                            result = await upload_pdf(mock_file)
                            
                            # Should still return success
                            assert result["status"] == "success"
                            
                            # Should log the error
                            mock_logger.error.assert_called()
                            assert "Failed to insert finding" in str(mock_logger.error.call_args)
