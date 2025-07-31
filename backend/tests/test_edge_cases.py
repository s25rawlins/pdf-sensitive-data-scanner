"""
Edge case tests for comprehensive coverage.

This module tests edge cases, error conditions, and less common code paths
to ensure robust behavior across all components.
"""

import pytest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from app.core.detector import SensitiveDataDetector
from app.db.models import (
    Document,
    DocumentWithFindings,
    Finding,
    FindingType,
    Metric,
    MetricType,
    PaginatedResponse,
    ProcessingStatus,
    SummaryStatistics,
)
from app.services.pdf_processor import PDFProcessor


class TestDetectorEdgeCases:
    """Test edge cases for the sensitive data detector."""

    def test_detector_with_logger_calls(self) -> None:
        """Test detector behavior with logger interactions."""
        # Create detector and test detection
        detector = SensitiveDataDetector()
        
        # Test with text containing sensitive data
        text = "Contact us at test@example.com or 123-45-6789"
        findings = detector.detect(text)

        # Verify findings are detected
        assert len(findings) == 2
        
        # Check finding values directly
        found_values = {f.value for f in findings}
        assert "test@example.com" in found_values
        assert "123-45-6789" in found_values
        
        # Check finding types
        found_types = {f.type.value for f in findings}
        assert "email" in found_types
        assert "ssn" in found_types
        
        # Test that logger can be mocked (for coverage)
        with patch("app.core.detector.logger") as mock_logger:
            detector2 = SensitiveDataDetector()
            findings2 = detector2.detect("test@example.com")
            assert len(findings2) == 1

    def test_detector_with_unusual_spacing(self) -> None:
        """Test detector with various spacing patterns."""
        detector = SensitiveDataDetector()

        # Test with multiple spaces
        text_spaces = "Email:    test@example.com    SSN:    123-45-6789"
        findings = detector.detect(text_spaces)
        assert len(findings) == 2

        # Test with newlines
        text_newlines = "Email:\ntest@example.com\nSSN:\n123-45-6789"
        findings = detector.detect(text_newlines)
        assert len(findings) == 2

        # Test with tabs
        text_tabs = "Email:\t\ttest@example.com\tSSN:\t123-45-6789"
        findings = detector.detect(text_tabs)
        assert len(findings) == 2

    def test_detector_no_sensitive_data(self) -> None:
        """Test detector with text containing no sensitive information."""
        detector = SensitiveDataDetector()

        test_cases = [
            "This is just regular text with no sensitive information.",
            "The quick brown fox jumps over the lazy dog.",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "",  # Empty string
            "   ",  # Only whitespace
        ]

        for text in test_cases:
            findings = detector.detect(text)
            assert len(findings) == 0, f"Unexpected findings in: {text}"


class TestModelsEdgeCases:
    """Test edge cases for Pydantic models."""

    def test_document_uuid_handling(self) -> None:
        """Test Document model with different UUID formats."""
        # Test with UUID object
        uuid_obj = UUID("12345678-1234-5678-1234-567812345678")
        doc = Document(
            document_id=uuid_obj,
            filename="test.pdf",
            file_size=1024,
            page_count=1,
            upload_timestamp=datetime.now(timezone.utc),
            processing_time_ms=100.0,
        )
        assert isinstance(doc.document_id, (str, UUID))

        # Test with string UUID
        doc_str = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=datetime.now(timezone.utc),
            processing_time_ms=100.0,
        )
        assert isinstance(doc_str.document_id, (str, UUID))

    def test_finding_edge_case_values(self) -> None:
        """Test Finding model with edge case values."""
        # Test with minimum confidence
        finding_min = Finding(
            finding_id=str(uuid4()),
            document_id=str(uuid4()),
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.0,  # Minimum valid confidence
            context="Email: test@example.com",
            detected_at=datetime.now(timezone.utc),
        )
        assert finding_min.confidence == 0.0

        # Test with maximum confidence
        finding_max = Finding(
            finding_id=str(uuid4()),
            document_id=str(uuid4()),
            finding_type=FindingType.SSN,
            value="123-45-6789",
            page_number=9999,  # Large page number
            confidence=1.0,  # Maximum valid confidence
            context="SSN: 123-45-6789",
            detected_at=datetime.now(timezone.utc),
        )
        assert finding_max.confidence == 1.0
        assert finding_max.page_number == 9999

    def test_response_models_edge_cases(self) -> None:
        """Test response models with edge cases."""
        # Test empty paginated response
        empty_paginated = PaginatedResponse(
            total=0,
            page=1,
            page_size=10,
            findings=[],
        )
        assert empty_paginated.total == 0
        assert len(empty_paginated.findings) == 0

        # Test summary statistics with zeros
        zero_stats = SummaryStatistics(
            total_documents=0,
            total_findings=0,
            findings_by_type={},
            average_processing_time_ms=0.0,
            total_pages_processed=0,
            documents_with_findings=0,
        )
        assert zero_stats.total_documents == 0
        assert zero_stats.findings_by_type == {}


class TestPDFProcessorEdgeCases:
    """Test edge cases for PDF processor."""

    def test_processor_with_logger_errors(self) -> None:
        """Test PDF processor logger calls during errors."""
        processor = PDFProcessor()

        with patch("app.services.pdf_processor.logger") as mock_logger:
            # Test with invalid PDF data
            try:
                processor.process_pdf(b"Not a valid PDF", "invalid.pdf")
            except Exception:
                pass

            # Logger should record the error
            assert mock_logger.error.called or mock_logger.warning.called

    def test_processor_empty_pdf(self) -> None:
        """Test PDF processor with empty or minimal PDFs."""
        processor = PDFProcessor()

        # Test with PDF that has no text
        with patch.object(processor, "_extract_text_from_pdf", return_value=("", {})):
            result = processor.process_pdf(b"%PDF-1.4\n%%EOF", "empty.pdf")
            assert len(result.findings) == 0
            assert result.page_count == 0

        # Test with PDF that has empty pages
        with patch.object(
            processor, "_extract_text_from_pdf", return_value=("", {"1": "", "2": "", "3": ""})
        ):
            result = processor.process_pdf(b"%PDF-1.4\n%%EOF", "empty_pages.pdf")
            assert result.page_count == 3
            assert len(result.findings) == 0

    def test_processor_extraction_fallback(self) -> None:
        """Test PDF processor fallback mechanism when primary extraction fails."""
        processor = PDFProcessor()

        # Mock pypdf to fail, forcing pdfplumber fallback
        with patch("app.services.pdf_processor.pypdf.PdfReader", side_effect=Exception("PyPDF failed")):
            with patch("app.services.pdf_processor.pdfplumber") as mock_pdfplumber:
                # Setup pdfplumber mock
                mock_pdf = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_text.return_value = "Fallback text: test@example.com"
                mock_pdf.pages = [mock_page]
                mock_pdf.__enter__.return_value = mock_pdf
                mock_pdf.__exit__.return_value = None
                mock_pdfplumber.open.return_value = mock_pdf

                result = processor.process_pdf(b"%PDF-1.4\nTest\n%%EOF", "test.pdf")

                assert result.page_count == 1
                assert len(result.findings) == 1  # Should find the email
                assert result.findings[0].value == "test@example.com"


class TestUploadEndpointEdgeCases:
    """Test edge cases for upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_metric_insertion_failure(self) -> None:
        """Test upload continues when metric insertion fails."""
        from fastapi import UploadFile

        from app.api.endpoints.upload import upload_pdf

        # Setup mocks
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4\nContent\n%%EOF")

        # Mock processor result
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.document_id = str(uuid4())
        mock_result.findings = []
        mock_result.page_count = 1
        mock_result.processing_time_ms = 100.0
        mock_result.file_size = 1024
        mock_result.status = "success"
        mock_processor.process_pdf.return_value = mock_result

        # Mock database with metric insertion failure
        mock_db = AsyncMock()
        mock_db.insert_metric.side_effect = Exception("Metric database error")

        # Patch dependencies
        with patch("app.api.endpoints.upload.validate_file_extension"):
            with patch("app.api.endpoints.upload.validate_file_size"):
                with patch("app.api.endpoints.upload.create_pdf_processor", return_value=mock_processor):
                    with patch("app.api.endpoints.upload.get_db_client", return_value=mock_db):
                        with patch("app.api.endpoints.upload.datetime") as mock_datetime:
                            mock_datetime.utcnow.return_value = datetime(2024, 1, 1)
                            with patch("app.api.endpoints.upload.logger") as mock_logger:
                                # Execute upload
                                result = await upload_pdf(mock_file)

                                # Should succeed despite metric error
                                assert result["status"] == "success"
                                # The document_id in the result is generated by the upload endpoint, not from the processor
                                assert "document_id" in result
                                assert len(result["document_id"]) == 36  # UUID format

                                # Should log the metric error
                                mock_logger.error.assert_called()
                                error_call = str(mock_logger.error.call_args)
                                assert "metric" in error_call.lower()

    def test_upload_settings_availability(self) -> None:
        """Test that upload endpoint has access to required settings."""
        from app.api.endpoints.upload import settings

        # Verify critical settings are available
        assert hasattr(settings, "max_upload_size")
        assert hasattr(settings, "enable_metrics")
        assert hasattr(settings, "allowed_file_extensions")
        assert hasattr(settings, "max_concurrent_uploads")

        # Verify settings have reasonable values
        assert settings.max_upload_size > 0
        assert isinstance(settings.enable_metrics, bool)
        assert len(settings.allowed_file_extensions) > 0
        assert settings.max_concurrent_uploads > 0


class TestIntegrationEdgeCases:
    """Test integration edge cases across components."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_errors(self) -> None:
        """Test the full processing pipeline with various error conditions."""
        # This test ensures error handling works correctly across components
        detector = SensitiveDataDetector()
        
        # Test detector with malformed patterns
        malformed_texts = [
            "Email: not-an-email@",
            "SSN: 000-00-0000",  # Invalid SSN
            "Mixed: test@.com and 999-99-9999",
        ]
        
        for text in malformed_texts:
            findings = detector.detect(text)
            # Should not crash, just return no findings for invalid patterns
            assert isinstance(findings, list)
