"""
Input validation utilities for the PDF scanner application.

This module provides validation functions for file uploads and
other user inputs to ensure security and data integrity.
"""

import logging
import mimetypes
from pathlib import Path
from typing import BinaryIO, Optional

logger = logging.getLogger(__name__)

# PDF file signatures (magic bytes)
PDF_SIGNATURES = [
    b"%PDF-1.",  # Standard PDF header
    b"%PDF-2.",  # PDF 2.0
]

# Maximum reasonable PDF version
MAX_PDF_VERSION = 2.0


def validate_pdf_content(file_content: bytes, max_size: Optional[int] = None) -> bool:
    """
    Validate that file content is a valid PDF.
    
    Args:
        file_content: Raw file content.
        max_size: Optional maximum file size in bytes.
        
    Returns:
        True if valid PDF content, False otherwise.
    """
    if not file_content:
        logger.warning("Empty file content provided")
        return False
    
    # Check file size if limit provided
    if max_size and len(file_content) > max_size:
        logger.warning(f"File size {len(file_content)} exceeds limit {max_size}")
        return False
    
    # Check PDF signature
    if not any(file_content.startswith(sig) for sig in PDF_SIGNATURES):
        logger.warning("File does not have valid PDF signature")
        return False
    
    # Basic structure check - PDF should end with %%EOF
    if not file_content.rstrip().endswith(b"%%EOF"):
        logger.warning("PDF file does not have proper EOF marker")
        return False
    
    return True


def validate_filename(filename: str, allowed_extensions: Optional[list] = None) -> bool:
    """
    Validate filename for security and allowed extensions.
    
    Args:
        filename: Filename to validate.
        allowed_extensions: List of allowed file extensions.
        
    Returns:
        True if valid filename, False otherwise.
    """
    if not filename:
        return False
    
    # Remove any path components for security
    filename = Path(filename).name
    
    # Check for suspicious patterns
    suspicious_patterns = ["../", "..\\", "\x00", "\n", "\r"]
    if any(pattern in filename for pattern in suspicious_patterns):
        logger.warning(f"Suspicious pattern found in filename: {filename}")
        return False
    
    # Check file extension if allowed list provided
    if allowed_extensions:
        file_ext = Path(filename).suffix.lower()
        if file_ext not in allowed_extensions:
            logger.warning(f"File extension {file_ext} not in allowed list")
            return False

    if len(filename) > 255:
        logger.warning(f"Filename too long: {len(filename)} characters")
        return False
    
    return True


def get_safe_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename.
        
    Returns:
        Sanitized filename safe for filesystem storage.
    """
    # Get base name without path
    safe_name = Path(filename).name
    
    # Replace potentially problematic characters
    unsafe_chars = '<>:"|?*\x00'
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, "_")
    
    safe_name = safe_name.replace(" ", "_")
    
    # Remove any remaining non-ASCII characters
    safe_name = "".join(char for char in safe_name if ord(char) < 128)
    
    # Ensure filename is not empty after sanitization
    if not safe_name or safe_name == ".pdf":
        safe_name = "unnamed.pdf"
    
    return safe_name


def validate_mime_type(file_content: bytes, filename: str) -> bool:
    """
    Validate MIME type matches expected PDF type.
    
    Args:
        file_content: File content for magic byte checking.
        filename: Filename for extension-based validation.
        
    Returns:
        True if MIME type is valid for PDF, False otherwise.
    """
    # Check by extension
    mime_type, _ = mimetypes.guess_type(filename)
    
    if mime_type and mime_type != "application/pdf":
        logger.warning(f"Unexpected MIME type from filename: {mime_type}")
        return False
    
    # Verify with content
    if not validate_pdf_content(file_content):
        return False
    
    return True


def validate_upload_file(
    file_content: bytes,
    filename: str,
    max_size: int,
    allowed_extensions: list,
) -> tuple[bool, Optional[str]]:
    """
    Comprehensive validation for uploaded files.
    
    Args:
        file_content: Raw file content.
        filename: Original filename.
        max_size: Maximum allowed file size.
        allowed_extensions: List of allowed extensions.
        
    Returns:
        Tuple of (is_valid, error_message).
    """

    if not validate_filename(filename, allowed_extensions):
        return False, "Invalid filename or extension"
    
    if not validate_pdf_content(file_content, max_size):
        return False, "Invalid PDF content or file too large"
    
    if not validate_mime_type(file_content, filename):
        return False, "File content does not match PDF format"
    
    return True, None