"""
Input validation utilities for the PDF scanner application.

This module provides validation functions for file uploads and
other user inputs to ensure security and data integrity.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# PDF file signatures (magic bytes)
PDF_SIGNATURES = [
    b"%PDF-1.",  # Standard PDF header
    b"%PDF-2.",  # PDF 2.0
]

# Valid finding types
VALID_FINDING_TYPES = ["email", "ssn"]

# UUID regex pattern
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


def validate_file_extension(filename: str) -> bool:
    """
    Validate file extension against allowed extensions.
    
    Args:
        filename: Name of the file to validate.
        
    Returns:
        True if extension is allowed.
        
    Raises:
        HTTPException: If extension is not allowed.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    settings = get_settings()
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in settings.allowed_file_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File extension {file_ext} is not allowed. Allowed extensions: {settings.allowed_file_extensions}"
        )
    
    return True


def validate_file_size(size: int) -> bool:
    """
    Validate file size against maximum allowed size.
    
    Args:
        size: File size in bytes.
        
    Returns:
        True if size is valid.
        
    Raises:
        HTTPException: If size exceeds limit or is invalid.
    """
    if size <= 0:
        raise HTTPException(status_code=400, detail="File size must be positive")
    
    settings = get_settings()
    if size > settings.max_upload_size:
        max_mb = settings.max_upload_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {max_mb:.1f}MB"
        )
    
    return True


def validate_pdf_content(content: bytes) -> bool:
    """
    Validate that content is a valid PDF.
    
    Args:
        content: File content bytes.
        
    Returns:
        True if content is valid PDF.
        
    Raises:
        HTTPException: If content is not valid PDF.
    """
    if not content:
        raise HTTPException(status_code=400, detail="File content is empty")
    
    # Check PDF signature
    if not any(content.startswith(sig) for sig in PDF_SIGNATURES):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")
    
    # Check for EOF marker
    if not content.rstrip().endswith(b"%%EOF"):
        raise HTTPException(status_code=400, detail="PDF file is corrupted or incomplete")
    
    return True


def validate_pagination(page: Optional[int], page_size: Optional[int]) -> Tuple[int, int]:
    """
    Validate and normalize pagination parameters.
    
    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page.
        
    Returns:
        Tuple of (page, page_size) with defaults applied.
        
    Raises:
        HTTPException: If parameters are invalid.
    """
    # Apply defaults
    page = page or 1
    page_size = page_size or 20
    
    # Validate page number
    if page < 1:
        raise HTTPException(status_code=422, detail="Page number must be >= 1")
    
    # Validate page size
    if page_size < 1:
        raise HTTPException(status_code=422, detail="Page size must be >= 1")
    
    if page_size > 100:
        raise HTTPException(status_code=422, detail="Page size must be <= 100")
    
    return page, page_size


def validate_finding_type(finding_type: Optional[str]) -> Optional[str]:
    """
    Validate finding type parameter.
    
    Args:
        finding_type: Type of finding to filter by.
        
    Returns:
        Validated finding type or None.
        
    Raises:
        HTTPException: If finding type is invalid.
    """
    if not finding_type:
        return None
    
    if finding_type not in VALID_FINDING_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid finding type. Must be one of: {VALID_FINDING_TYPES}"
        )
    
    return finding_type


def validate_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate date range parameters.
    
    Args:
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        Tuple of (start_date, end_date).
        
    Raises:
        HTTPException: If date range is invalid.
    """
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="End date must be after start date"
        )
    
    return start_date, end_date


def validate_document_id(document_id: str) -> str:
    """
    Validate document ID format (UUID).
    
    Args:
        document_id: Document ID to validate.
        
    Returns:
        Validated document ID.
        
    Raises:
        HTTPException: If document ID is invalid.
    """
    if not document_id or not UUID_PATTERN.match(str(document_id)):
        raise HTTPException(
            status_code=422,
            detail="Invalid document ID format. Must be a valid UUID."
        )
    
    return document_id


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename.
        
    Returns:
        Sanitized filename safe for filesystem storage.
    """
    if not filename:
        return "unnamed"
    
    # Get base name without path
    safe_name = Path(filename).name
    
    # Replace spaces with underscores
    safe_name = safe_name.replace(" ", "_")
    
    # Remove path traversal attempts
    safe_name = safe_name.replace("..", "")
    safe_name = safe_name.replace("/", "")
    safe_name = safe_name.replace("\\", "")
    
    # Remove special characters but keep dots, dashes, and underscores
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '', safe_name)
    
    # Ensure filename is not empty after sanitization
    if not safe_name or safe_name in [".", ".."]:
        return "unnamed"
    
    # Limit length
    if len(safe_name) > 255:
        # Keep extension if present
        ext = Path(safe_name).suffix
        base = Path(safe_name).stem
        max_base_len = 255 - len(ext)
        safe_name = base[:max_base_len] + ext
    
    return safe_name


# Legacy functions for backward compatibility
def validate_pdf_content_legacy(file_content: bytes, max_size: Optional[int] = None) -> bool:
    """Legacy function for PDF content validation."""
    try:
        if max_size:
            validate_file_size(len(file_content))
        validate_pdf_content(file_content)
        return True
    except HTTPException:
        return False


def validate_filename(filename: str, allowed_extensions: Optional[list] = None) -> bool:
    """Legacy function for filename validation."""
    try:
        if allowed_extensions:
            # Temporarily override settings
            settings = get_settings()
            original = settings.allowed_file_extensions
            settings.allowed_file_extensions = allowed_extensions
            result = validate_file_extension(filename)
            settings.allowed_file_extensions = original
            return result
        else:
            validate_file_extension(filename)
            return True
    except HTTPException:
        return False


def get_safe_filename(filename: str) -> str:
    """Legacy function for filename sanitization."""
    return sanitize_filename(filename)


def validate_mime_type(file_content: bytes, filename: str) -> bool:
    """Legacy function for MIME type validation."""
    try:
        validate_pdf_content(file_content)
        validate_file_extension(filename)
        return True
    except HTTPException:
        return False


def validate_upload_file(
    file_content: bytes,
    filename: str,
    max_size: int,
    allowed_extensions: list,
) -> tuple[bool, Optional[str]]:
    """Legacy function for comprehensive file validation."""
    try:
        validate_file_extension(filename)
        validate_file_size(len(file_content))
        validate_pdf_content(file_content)
        return True, None
    except HTTPException as e:
        return False, str(e.detail)
