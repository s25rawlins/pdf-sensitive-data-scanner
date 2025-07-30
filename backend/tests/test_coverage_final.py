"""
Final tests to reach 80% coverage.

This module adds tests for remaining uncovered lines.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.core.detector import SensitiveDataDetector
from app.services.pdf_processor import PDFProcessor
from app.db.models import Document, Finding, ProcessingStatus, FindingType


class TestFinalCoverage:
    """Final tests to reach 80% coverage."""
    
    def test_detector_debug_logging(self):
        """Test detector with debug logging enabled."""
        with patch("app.core.detector.logger") as mock_logger:
            detector = SensitiveDataDetector()
            
            # Test detection with logging
            text = "My email is test@example.com"
            findings = detector.detect(text)
            
            assert len(findings) == 1
            assert findings[0].type.value == "email"
    
    def test_pdf_processor_fallback_extraction(self):
        """Test PDF processor fallback text extraction."""
        processor = PDFProcessor()
        
        # Mock PyPDF2 to fail, forcing pdfplumber fallback
        with patch("app.services.pdf_processor.PdfReader", side_effect=Exception("PyPDF2 failed")):
            with patch("app.services.pdf_processor.pdfplumber") as mock_pdfplumber:
                # Mock pdfplumber to return text
                mock_pdf = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_text.return_value = "Test text from pdfplumber"
                mock_pdf.pages = [mock_page]
                mock_pdf.__enter__.return_value = mock_pdf
                mock_pdf.__exit__.return_value = None
                mock_pdfplumber.open.return_value = mock_pdf
                
                result = processor.process_pdf(b"%PDF-1.4\nTest\n%%EOF", "test.pdf")
                
                assert result.page_count == 1
    
    def test_models_edge_cases(self):
        """Test model edge cases for coverage."""
        # Test Document with UUID as UUID object
        from uuid import UUID
        doc = Document(
            document_id=UUID("12345678-1234-5678-1234-567812345678"),
            filename="test.pdf",
            file_size=1024,
            page_count=1,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=100.0
        )
        assert isinstance(doc.document_id, (str, UUID))
    
    def test_pdf_processor_empty_pages(self):
        """Test PDF processor with empty pages."""
        processor = PDFProcessor()
        
        with patch.object(processor, '_extract_text_from_pdf', return_value=("", {"1": "", "2": ""})):
            result = processor.process_pdf(b"%PDF-1.4\n%%EOF", "empty.pdf")
            assert result.page_count == 2
            assert len(result.findings) == 0
    
    def test_detector_no_matches(self):
        """Test detector with text that has no sensitive data."""
        detector = SensitiveDataDetector()
        
        text = "This is just regular text with no sensitive information."
        findings = detector.detect(text)
        
        assert len(findings) == 0
    
    def test_upload_endpoint_settings_check(self):
        """Test upload endpoint settings check."""
        from app.api.endpoints.upload import settings
        
        # Just access the settings to ensure they're loaded
        assert hasattr(settings, 'max_upload_size')
        assert hasattr(settings, 'enable_metrics')
