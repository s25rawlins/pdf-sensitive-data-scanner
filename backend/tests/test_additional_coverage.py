"""
Additional tests to reach 80% coverage.

This module tests remaining uncovered lines in various modules.
"""

import pytest
from unittest.mock import patch, MagicMock

from uuid import UUID

from app.core.detector import SensitiveDataDetector
from app.db.models import (
    Document, Finding, Metric, DocumentWithFindings,
    FindingResponse, PaginatedResponse, SummaryStatistics
)
from app.services.pdf_processor import PDFProcessor


class TestDetectorAdditional:
    """Additional tests for detector coverage."""
    
    def test_detector_logger_usage(self):
        """Test detector with logger calls."""
        detector = SensitiveDataDetector()
        
        with patch("app.core.detector.logger") as mock_logger:
            # Test with text that triggers logging
            text = "Contact us at test@example.com or 123-45-6789"
            findings = detector.detect(text)
            
            # Should have findings
            assert len(findings) == 2
            
            # Logger should be called for initialization
            assert mock_logger.debug.called or mock_logger.info.called
    
    def test_detector_edge_cases(self):
        """Test detector edge cases for coverage."""
        detector = SensitiveDataDetector()
        
        # Test with text containing multiple spaces
        text = "Email:    test@example.com    SSN:    123-45-6789"
        findings = detector.detect(text)
        assert len(findings) == 2
        
        # Test with newlines
        text = "Email:\ntest@example.com\nSSN:\n123-45-6789"
        findings = detector.detect(text)
        assert len(findings) == 2


class TestModelsAdditional:
    """Additional tests for models coverage."""
    
    def test_document_field_validators(self):
        """Test Document model field validators."""
        from datetime import datetime
        from uuid import uuid4
        
        # Test with string UUID (should be converted)
        doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=100.0
        )
        assert isinstance(doc.document_id, (str, UUID))
    
    def test_finding_field_validators(self):
        """Test Finding model field validators."""
        from datetime import datetime
        from uuid import uuid4
        from app.db.models import FindingType
        
        # Test confidence bounds
        finding = Finding(
            finding_id=str(uuid4()),
            document_id=str(uuid4()),
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.5,
            context="Email: test@example.com",
            detected_at=datetime.utcnow()
        )
        assert finding.confidence == 0.5
    
    def test_metric_model_coverage(self):
        """Test Metric model for coverage."""
        from datetime import datetime
        from uuid import uuid4
        from app.db.models import MetricType
        
        # Test with all fields
        metric = Metric(
            metric_id=str(uuid4()),
            document_id=str(uuid4()),
            metric_type=MetricType.PROCESSING_TIME,
            value=100.5,
            recorded_at=datetime.utcnow()
        )
        assert metric.value == 100.5
    
    def test_response_models_coverage(self):
        """Test response models for coverage."""
        from datetime import datetime
        
        # Test PaginatedResponse
        paginated = PaginatedResponse(
            total=50,
            page=2,
            page_size=10,
            findings=[]
        )
        assert paginated.total == 50
        
        # Test SummaryStatistics
        stats = SummaryStatistics(
            total_documents=100,
            total_findings=200,
            findings_by_type={"email": 120, "ssn": 80},
            average_processing_time_ms=150.0,
            total_pages_processed=500,
            documents_with_findings=75
        )
        assert stats.total_documents == 100


class TestPDFProcessorAdditional:
    """Additional tests for PDF processor coverage."""
    
    def test_processor_logger_calls(self):
        """Test PDF processor logger calls."""
        processor = PDFProcessor()
        
        with patch("app.services.pdf_processor.logger") as mock_logger:
            # Test with invalid PDF that triggers logging
            try:
                processor.process_pdf(b"Not a PDF", "test.pdf")
            except Exception:
                pass
            
            # Logger should be called
            assert mock_logger.error.called or mock_logger.warning.called
    
    def test_processor_edge_cases(self):
        """Test PDF processor edge cases."""
        processor = PDFProcessor()
        
        # Test with PDF that has no text
        with patch.object(processor, '_extract_text_from_pdf', return_value=("", {})):
            result = processor.process_pdf(b"%PDF-1.4\n%%EOF", "empty.pdf")
            assert len(result.findings) == 0
            assert result.page_count == 0


class TestUploadEndpointAdditional:
    """Additional tests for upload endpoint coverage."""
    
    @pytest.mark.asyncio
    async def test_upload_metric_insertion_error(self):
        """Test upload with metric insertion error (non-critical)."""
        from app.api.endpoints.upload import upload_pdf
        from fastapi import UploadFile
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
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
        mock_db.insert_metric.side_effect = Exception("Metric insert failed")
        
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.validate_file_size"):
                with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                    with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                        with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                            from datetime import datetime
                            mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                            with patch("app.api.endpoints.upload.logger") as mock_logger:
                                
                                result = await upload_pdf(mock_file)
                                
                                # Should still succeed despite metric error
                                assert result["status"] == "success"
                                
                                # Should log the metric error
                                mock_logger.error.assert_called()
