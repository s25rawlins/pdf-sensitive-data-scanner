"""
Additional tests for validators to increase coverage.

This module tests the legacy functions and edge cases in validators.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.utils.validators import (
    validate_pdf_content_legacy,
    validate_filename,
    get_safe_filename,
    validate_mime_type,
    validate_upload_file,
)


class TestValidatorsLegacyFunctions:
    """Test suite for legacy validator functions."""
    
    def test_validate_pdf_content_legacy_valid(self):
        """Test legacy PDF content validation with valid content."""
        valid_pdf = b"%PDF-1.4\nContent\n%%EOF"
        
        # Without size limit
        assert validate_pdf_content_legacy(valid_pdf) is True
        
        # With size limit
        assert validate_pdf_content_legacy(valid_pdf, max_size=1024) is True
    
    def test_validate_pdf_content_legacy_invalid(self):
        """Test legacy PDF content validation with invalid content."""
        # Invalid PDF
        assert validate_pdf_content_legacy(b"Not a PDF") is False
        
        # Empty content
        assert validate_pdf_content_legacy(b"") is False
        
        # Exceeds size limit
        large_pdf = b"%PDF-1.4\n" + b"x" * 1000 + b"\n%%EOF"
        assert validate_pdf_content_legacy(large_pdf, max_size=100) is False
    
    def test_validate_filename_valid(self):
        """Test legacy filename validation with valid names."""
        # Default allowed extensions
        assert validate_filename("document.pdf") is True
        
        # Custom allowed extensions
        assert validate_filename("document.doc", allowed_extensions=[".doc", ".pdf"]) is True
        assert validate_filename("document.pdf", allowed_extensions=[".doc", ".pdf"]) is True
    
    def test_validate_filename_invalid(self):
        """Test legacy filename validation with invalid names."""
        # Invalid extension with default settings
        assert validate_filename("document.txt") is False
        
        # Invalid extension with custom settings
        assert validate_filename("document.txt", allowed_extensions=[".pdf", ".doc"]) is False
        
        # Empty filename
        assert validate_filename("") is False
    
    def test_get_safe_filename(self):
        """Test legacy filename sanitization."""
        # Normal filename
        assert get_safe_filename("document.pdf") == "document.pdf"
        
        # Filename with special characters
        assert get_safe_filename("my@file#.pdf") == "myfile.pdf"
        
        # Path traversal attempt
        assert get_safe_filename("../../etc/passwd") == "passwd"
        
        # Empty or None
        assert get_safe_filename("") == "unnamed"
        assert get_safe_filename(None) == "unnamed"
        
        # Very long filename
        long_name = "a" * 300 + ".pdf"
        result = get_safe_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")
    
    def test_validate_mime_type_valid(self):
        """Test legacy MIME type validation with valid content."""
        valid_pdf = b"%PDF-1.4\nContent\n%%EOF"
        
        assert validate_mime_type(valid_pdf, "document.pdf") is True
    
    def test_validate_mime_type_invalid(self):
        """Test legacy MIME type validation with invalid content."""
        # Invalid PDF content
        assert validate_mime_type(b"Not a PDF", "document.pdf") is False
        
        # Invalid filename
        assert validate_mime_type(b"%PDF-1.4\nContent\n%%EOF", "document.txt") is False
        
        # Both invalid
        assert validate_mime_type(b"Not a PDF", "document.txt") is False
    
    def test_validate_upload_file_valid(self):
        """Test legacy upload file validation with valid file."""
        valid_pdf = b"%PDF-1.4\nContent\n%%EOF"
        
        is_valid, error = validate_upload_file(
            file_content=valid_pdf,
            filename="document.pdf",
            max_size=1024 * 1024,
            allowed_extensions=[".pdf"]
        )
        
        assert is_valid is True
        assert error is None
    
    def test_validate_upload_file_invalid_extension(self):
        """Test legacy upload file validation with invalid extension."""
        valid_pdf = b"%PDF-1.4\nContent\n%%EOF"
        
        with patch("app.utils.validators.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                allowed_file_extensions=[".pdf"],
                max_upload_size=1024 * 1024
            )
            
            is_valid, error = validate_upload_file(
                file_content=valid_pdf,
                filename="document.txt",
                max_size=1024 * 1024,
                allowed_extensions=[".pdf"]
            )
            
            assert is_valid is False
            assert "not allowed" in error
    
    def test_validate_upload_file_invalid_size(self):
        """Test legacy upload file validation with oversized file."""
        large_pdf = b"%PDF-1.4\n" + b"x" * 2000 + b"\n%%EOF"
        
        with patch("app.utils.validators.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                allowed_file_extensions=[".pdf"],
                max_upload_size=1024
            )
            
            is_valid, error = validate_upload_file(
                file_content=large_pdf,
                filename="document.pdf",
                max_size=1024,
                allowed_extensions=[".pdf"]
            )
            
            assert is_valid is False
            assert "exceeds maximum" in error
    
    def test_validate_upload_file_invalid_content(self):
        """Test legacy upload file validation with invalid PDF content."""
        invalid_pdf = b"Not a PDF file"
        
        with patch("app.utils.validators.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                allowed_file_extensions=[".pdf"],
                max_upload_size=1024 * 1024
            )
            
            is_valid, error = validate_upload_file(
                file_content=invalid_pdf,
                filename="document.pdf",
                max_size=1024 * 1024,
                allowed_extensions=[".pdf"]
            )
            
            assert is_valid is False
            assert "valid PDF" in error
