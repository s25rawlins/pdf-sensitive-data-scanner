"""
Test suite for PDF processing functionality.

Tests cover PDF text extraction, sensitive data detection in PDFs,
error handling for corrupted files, and performance requirements.
"""

import io
import os
import tempfile
from pathlib import Path
from typing import BinaryIO
from unittest.mock import Mock, patch

import pytest
from PyPDF2 import PdfWriter, PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.services.pdf_processor import (
    PDFProcessor,
    PDFProcessingError,
    PDFProcessingResult,
    CorruptedPDFError,
    PDFSizeLimitError,
    create_pdf_processor
)


class TestPDFProcessor:
    """Test suite for PDF processing functionality."""
    
    @pytest.fixture
    def processor(self) -> PDFProcessor:
        """Create a PDF processor instance for testing."""
        return create_pdf_processor()
    
    @pytest.fixture
    def simple_pdf_bytes(self) -> bytes:
        """Create a simple PDF with text content."""
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        
        # Add text content
        pdf_canvas.drawString(100, 750, "Test Document")
        pdf_canvas.drawString(100, 700, "Email: test@example.com")
        pdf_canvas.drawString(100, 650, "SSN: 123-45-6789")
        pdf_canvas.save()
        
        buffer.seek(0)
        return buffer.read()
    
    @pytest.fixture
    def multi_page_pdf_bytes(self) -> bytes:
        """Create a multi-page PDF with sensitive data on different pages."""
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        
        # Page 1
        pdf_canvas.drawString(100, 750, "Page 1")
        pdf_canvas.drawString(100, 700, "Contact: admin@company.com")
        pdf_canvas.showPage()
        
        # Page 2
        pdf_canvas.drawString(100, 750, "Page 2")
        pdf_canvas.drawString(100, 700, "Employee SSN: 456-78-9012")
        pdf_canvas.showPage()
        
        # Page 3
        pdf_canvas.drawString(100, 750, "Page 3")
        pdf_canvas.drawString(100, 700, "Support: support@company.com")
        
        pdf_canvas.save()
        buffer.seek(0)
        return buffer.read()
    
    @pytest.fixture
    def empty_pdf_bytes(self) -> bytes:
        """Create an empty PDF with no text content."""
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        pdf_canvas.save()
        buffer.seek(0)
        return buffer.read()
    
    @pytest.fixture
    def corrupted_pdf_bytes(self) -> bytes:
        """Create corrupted PDF data."""
        return b"%PDF-1.4\n corrupted content that is not valid PDF"
    
    def test_processor_initialization(self):
        """Test that PDF processor initializes correctly."""
        processor = PDFProcessor()
        assert processor is not None
        assert hasattr(processor, 'detector')
        assert hasattr(processor, 'max_file_size')
    
    def test_factory_function(self):
        """Test the factory function creates a valid processor."""
        processor = create_pdf_processor()
        assert isinstance(processor, PDFProcessor)
    
    def test_process_simple_pdf(self, processor, simple_pdf_bytes):
        """Test processing a simple PDF with sensitive data."""
        result = processor.process_pdf(simple_pdf_bytes, filename="test.pdf")
        
        assert isinstance(result, PDFProcessingResult)
        assert result.filename == "test.pdf"
        assert result.status == "success"
        assert result.page_count == 1
        assert result.file_size == len(simple_pdf_bytes)
        assert len(result.findings) == 2  # 1 email + 1 SSN
        
        # Check findings
        email_findings = [f for f in result.findings if f.type.value == "email"]
        ssn_findings = [f for f in result.findings if f.type.value == "ssn"]
        
        assert len(email_findings) == 1
        assert len(ssn_findings) == 1
        assert email_findings[0].value == "test@example.com"
        assert ssn_findings[0].value == "123-45-6789"
    
    def test_process_multi_page_pdf(self, processor, multi_page_pdf_bytes):
        """Test processing a multi-page PDF."""
        result = processor.process_pdf(multi_page_pdf_bytes, filename="multipage.pdf")
        
        assert result.page_count == 3
        assert len(result.findings) == 3  # 2 emails + 1 SSN
        
        # Verify findings include page numbers
        for finding in result.findings:
            assert hasattr(finding, 'page_number')
            assert 1 <= finding.page_number <= 3
    
    def test_process_empty_pdf(self, processor, empty_pdf_bytes):
        """Test processing an empty PDF."""
        result = processor.process_pdf(empty_pdf_bytes, filename="empty.pdf")
        
        assert result.status == "success"
        assert result.page_count >= 0
        assert len(result.findings) == 0
        assert result.extracted_text.strip() == ""
    
    def test_process_corrupted_pdf(self, processor, corrupted_pdf_bytes):
        """Test handling of corrupted PDF files."""
        with pytest.raises(CorruptedPDFError) as exc_info:
            processor.process_pdf(corrupted_pdf_bytes, filename="corrupted.pdf")
        
        assert "corrupted.pdf" in str(exc_info.value)
    
    def test_file_size_limit(self, processor):
        """Test enforcement of file size limits."""
        # Create a "large" PDF by setting a small limit
        processor.max_file_size = 1024  # 1KB limit
        
        # Create PDF larger than limit
        large_pdf = b"%PDF-1.4\n" + b"x" * 2048
        
        with pytest.raises(PDFSizeLimitError) as exc_info:
            processor.process_pdf(large_pdf, filename="large.pdf")
        
        assert "exceeds maximum size" in str(exc_info.value)
    
    def test_process_pdf_from_file_path(self, processor, simple_pdf_bytes):
        """Test processing PDF from file path."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(simple_pdf_bytes)
            tmp_path = tmp_file.name
        
        try:
            result = processor.process_pdf_from_path(tmp_path)
            assert result.filename == os.path.basename(tmp_path)
            assert result.status == "success"
            assert len(result.findings) == 2
        finally:
            os.unlink(tmp_path)
    
    def test_process_pdf_from_stream(self, processor, simple_pdf_bytes):
        """Test processing PDF from file-like object."""
        stream = io.BytesIO(simple_pdf_bytes)
        result = processor.process_pdf_from_stream(stream, filename="stream.pdf")
        
        assert result.filename == "stream.pdf"
        assert result.status == "success"
        assert len(result.findings) == 2
    
    def test_extract_text_with_encoding_issues(self, processor):
        """Test handling of PDFs with various text encodings."""
        # Create PDF with special characters
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        pdf_canvas.drawString(100, 750, "Special chars: café, naïve")
        pdf_canvas.drawString(100, 700, "Email: user@café.com")
        pdf_canvas.save()
        
        buffer.seek(0)
        result = processor.process_pdf(buffer.read(), filename="encoding.pdf")
        
        assert result.status == "success"
        assert "café" in result.extracted_text or "cafe" in result.extracted_text
    
    def test_finding_metadata(self, processor, simple_pdf_bytes):
        """Test that findings include proper metadata."""
        result = processor.process_pdf(simple_pdf_bytes, filename="test.pdf")
        
        for finding in result.findings:
            # Check required metadata fields
            assert hasattr(finding, 'page_number')
            assert hasattr(finding, 'type')
            assert hasattr(finding, 'value')
            assert hasattr(finding, 'confidence')
            assert finding.page_number == 1  # All on first page
    
    def test_processing_metrics(self, processor, simple_pdf_bytes):
        """Test that processing metrics are collected."""
        result = processor.process_pdf(simple_pdf_bytes, filename="test.pdf")
        
        assert hasattr(result, 'processing_time_ms')
        assert result.processing_time_ms > 0
        assert result.processing_time_ms < 5000  # Should be under 5 seconds
    
    def test_concurrent_processing_safety(self, processor, simple_pdf_bytes):
        """Test that processor can handle concurrent requests safely."""
        # Process same PDF multiple times
        results = []
        for i in range(3):
            result = processor.process_pdf(
                simple_pdf_bytes, 
                filename=f"concurrent_{i}.pdf"
            )
            results.append(result)
        
        # All results should be independent
        for i, result in enumerate(results):
            assert result.filename == f"concurrent_{i}.pdf"
            assert len(result.findings) == 2
    
    def test_memory_efficient_processing(self, processor):
        """Test memory-efficient processing of large PDFs."""
        # Create a PDF with many pages
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        
        for i in range(50):  # 50 pages
            pdf_canvas.drawString(100, 750, f"Page {i+1}")
            pdf_canvas.drawString(100, 700, f"Email: user{i}@example.com")
            pdf_canvas.showPage()
        
        pdf_canvas.save()
        buffer.seek(0)
        
        # Process should complete without memory issues
        result = processor.process_pdf(buffer.read(), filename="large.pdf")
        
        assert result.page_count == 50
        assert len(result.findings) == 50  # One email per page
    
    def test_password_protected_pdf_handling(self, processor):
        """Test handling of password-protected PDFs."""
        # Create a password-protected PDF
        buffer = io.BytesIO()
        writer = PdfWriter()
        
        # Create a simple page
        from reportlab.pdfgen import canvas
        page_buffer = io.BytesIO()
        c = canvas.Canvas(page_buffer, pagesize=letter)
        c.drawString(100, 750, "Protected content")
        c.save()
        
        # Note: Actual password protection would require additional setup
        # This test demonstrates the expected behavior
        
        # For now, test with regular PDF and mock protection
        with patch.object(processor, '_is_pdf_encrypted', return_value=True):
            with pytest.raises(PDFProcessingError) as exc_info:
                processor.process_pdf(b"encrypted_pdf_data", filename="protected.pdf")
            
            assert "password-protected" in str(exc_info.value).lower()
    
    def test_get_summary_statistics(self, processor, multi_page_pdf_bytes):
        """Test generation of summary statistics."""
        result = processor.process_pdf(multi_page_pdf_bytes, filename="stats.pdf")
        
        stats = result.get_summary()
        assert stats['total_findings'] == 3
        assert stats['findings_by_type']['email'] == 2
        assert stats['findings_by_type']['ssn'] == 1
        assert stats['pages_with_findings'] == 3
        assert stats['file_size_kb'] > 0
