"""
Tests for input validators.

This module tests all validation functions to ensure proper
input validation and error handling.
"""

import pytest
from fastapi import HTTPException

from app.utils.validators import (
    validate_file_extension,
    validate_file_size,
    validate_pdf_content,
    validate_pagination,
    validate_finding_type,
    validate_date_range,
    validate_document_id,
    sanitize_filename,
)


class TestValidators:
    """Test suite for validation functions."""
    
    def test_validate_file_extension_valid(self):
        """Test valid file extensions."""
        # Valid PDF extension
        assert validate_file_extension("document.pdf") is True
        assert validate_file_extension("Document.PDF") is True
        assert validate_file_extension("file.name.pdf") is True
        
    def test_validate_file_extension_invalid(self):
        """Test invalid file extensions."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_extension("document.txt")
        assert exc_info.value.status_code == 400
        assert "not allowed" in str(exc_info.value.detail)
        
        with pytest.raises(HTTPException):
            validate_file_extension("document.docx")
        
        with pytest.raises(HTTPException):
            validate_file_extension("document")
    
    def test_validate_file_size_valid(self):
        """Test valid file sizes."""
        # Valid sizes (under 50MB)
        assert validate_file_size(1024) is True  # 1KB
        assert validate_file_size(1024 * 1024) is True  # 1MB
        assert validate_file_size(50 * 1024 * 1024 - 1) is True  # Just under 50MB
    
    def test_validate_file_size_invalid(self):
        """Test invalid file sizes."""
        # Over 50MB
        with pytest.raises(HTTPException) as exc_info:
            validate_file_size(51 * 1024 * 1024)
        assert exc_info.value.status_code == 413
        assert "exceeds maximum" in str(exc_info.value.detail)
        
        # Negative size
        with pytest.raises(HTTPException):
            validate_file_size(-1)
        
        # Zero size
        with pytest.raises(HTTPException):
            validate_file_size(0)
    
    def test_validate_pdf_content_valid(self):
        """Test valid PDF content."""
        # Valid PDF headers
        valid_pdfs = [
            b"%PDF-1.4\n...\n%%EOF",
            b"%PDF-1.5\n...\n%%EOF",
            b"%PDF-1.7\n...\n%%EOF",
            b"%PDF-2.0\n...\n%%EOF",
        ]
        
        for pdf_content in valid_pdfs:
            assert validate_pdf_content(pdf_content) is True
    
    def test_validate_pdf_content_invalid(self):
        """Test invalid PDF content."""
        # Not a PDF
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf_content(b"This is not a PDF")
        assert exc_info.value.status_code == 400
        assert "valid PDF" in str(exc_info.value.detail)
        
        # Missing EOF marker
        with pytest.raises(HTTPException):
            validate_pdf_content(b"%PDF-1.4\nContent without EOF")
        
        # Empty content
        with pytest.raises(HTTPException):
            validate_pdf_content(b"")
        
        # None content
        with pytest.raises(HTTPException):
            validate_pdf_content(None)
    
    def test_validate_pagination_valid(self):
        """Test valid pagination parameters."""
        # Valid combinations
        assert validate_pagination(1, 10) == (1, 10)
        assert validate_pagination(2, 20) == (2, 20)
        assert validate_pagination(10, 100) == (10, 100)
        
        # Default values
        assert validate_pagination(None, None) == (1, 20)
        assert validate_pagination(5, None) == (5, 20)
        assert validate_pagination(None, 50) == (1, 50)
    
    def test_validate_pagination_invalid(self):
        """Test invalid pagination parameters."""
        # Invalid page number - validate_pagination returns defaults for None/0
        # but should raise for negative values
        with pytest.raises(HTTPException):
            validate_pagination(-1, 10)
        
        # Invalid page size
        with pytest.raises(HTTPException):
            validate_pagination(1, -10)
        
        with pytest.raises(HTTPException):
            validate_pagination(1, 101)  # Over max
    
    def test_validate_finding_type_valid(self):
        """Test valid finding types."""
        assert validate_finding_type("email") == "email"
        assert validate_finding_type("ssn") == "ssn"
        assert validate_finding_type(None) is None
        assert validate_finding_type("") is None
    
    def test_validate_finding_type_invalid(self):
        """Test invalid finding types."""
        with pytest.raises(HTTPException) as exc_info:
            validate_finding_type("invalid")
        assert exc_info.value.status_code == 422
        assert "Invalid finding type" in str(exc_info.value.detail)
        
        with pytest.raises(HTTPException):
            validate_finding_type("phone")
        
        with pytest.raises(HTTPException):
            validate_finding_type("SSN")  # Case sensitive
    
    def test_validate_date_range_valid(self):
        """Test valid date ranges."""
        from datetime import datetime, timedelta, timezone
        
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        # Valid ranges
        assert validate_date_range(yesterday, now) == (yesterday, now)
        assert validate_date_range(yesterday, tomorrow) == (yesterday, tomorrow)
        
        # None values allowed
        assert validate_date_range(None, None) == (None, None)
        assert validate_date_range(yesterday, None) == (yesterday, None)
        assert validate_date_range(None, tomorrow) == (None, tomorrow)
    
    def test_validate_date_range_invalid(self):
        """Test invalid date ranges."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        
        # End before start
        with pytest.raises(HTTPException) as exc_info:
            validate_date_range(now, yesterday)
        assert exc_info.value.status_code == 422
        assert "after start date" in str(exc_info.value.detail)
    
    def test_validate_document_id_valid(self):
        """Test valid document IDs."""
        # Valid UUIDs
        valid_ids = [
            "123e4567-e89b-12d3-a456-426614174000",
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        ]
        
        for doc_id in valid_ids:
            assert validate_document_id(doc_id) == doc_id
    
    def test_validate_document_id_invalid(self):
        """Test invalid document IDs."""
        invalid_ids = [
            "not-a-uuid",
            "123456",
            "123e4567-e89b-12d3-a456",  # Too short
            "123e4567-e89b-12d3-a456-426614174000-extra",  # Too long
            "123e4567-e89b-12d3-a456-42661417400g",  # Invalid character
            "",
            None,
        ]
        
        for doc_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                validate_document_id(doc_id)
            assert exc_info.value.status_code == 422
            assert "Invalid document ID" in str(exc_info.value.detail)
    
    def test_sanitize_filename_valid(self):
        """Test filename sanitization."""
        # Normal filenames
        assert sanitize_filename("document.pdf") == "document.pdf"
        assert sanitize_filename("my-file_123.pdf") == "my-file_123.pdf"
        
        # Special characters removed
        assert sanitize_filename("file@#$%.pdf") == "file.pdf"
        assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"  # .. is removed
        assert sanitize_filename("file name with spaces.pdf") == "file_name_with_spaces.pdf"
        
        # Path traversal attempts
        assert sanitize_filename("../../../file.pdf") == "file.pdf"
        assert sanitize_filename("C:\\Windows\\System32\\file.pdf") == "CWindowsSystem32file.pdf"
        
        # Unicode characters
        assert sanitize_filename("файл.pdf") == ".pdf"  # Non-ASCII removed
        assert sanitize_filename("文档.pdf") == ".pdf"  # Non-ASCII removed
    
    def test_sanitize_filename_edge_cases(self):
        """Test edge cases for filename sanitization."""
        # Empty or None
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename(None) == "unnamed"
        
        # Only special characters
        assert sanitize_filename("@#$%^&*()") == "unnamed"
        
        # Very long filename
        long_name = "a" * 300 + ".pdf"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255
        assert sanitized.endswith(".pdf")
    
    def test_validate_file_extension_settings(self):
        """Test file extension validation with custom settings."""
        from unittest.mock import patch
        from app.core.config import Settings
        
        # Mock settings with different allowed extensions
        mock_settings = Settings(
            allowed_file_extensions=[".pdf", ".doc", ".docx"]
        )
        
        with patch("app.utils.validators.get_settings", return_value=mock_settings):
            assert validate_file_extension("document.pdf") is True
            assert validate_file_extension("document.doc") is True
            assert validate_file_extension("document.docx") is True
            
            with pytest.raises(HTTPException):
                validate_file_extension("document.txt")
    
    def test_validate_file_size_settings(self):
        """Test file size validation with custom settings."""
        from unittest.mock import patch
        from app.core.config import Settings
        
        # Mock settings with different max size (10MB)
        mock_settings = Settings(
            max_upload_size=10 * 1024 * 1024
        )
        
        with patch("app.utils.validators.get_settings", return_value=mock_settings):
            assert validate_file_size(5 * 1024 * 1024) is True  # 5MB OK
            
            with pytest.raises(HTTPException):
                validate_file_size(11 * 1024 * 1024)  # 11MB too large
