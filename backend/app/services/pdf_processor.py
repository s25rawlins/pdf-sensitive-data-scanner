"""
PDF processing service for extracting text and detecting sensitive data.

This module handles PDF file processing, text extraction, and integration
with the sensitive data detector to identify PII in PDF documents.
"""

import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Union, Tuple

import PyPDF2
import pdfplumber
from PyPDF2.errors import PdfReadError

from app.core.detector import Finding, FindingType, create_detector, SensitiveDataDetector

logger = logging.getLogger(__name__)


class PDFProcessingError(Exception):
    """Base exception for PDF processing errors."""
    pass


class CorruptedPDFError(PDFProcessingError):
    """Raised when PDF file is corrupted or unreadable."""
    pass


class PDFSizeLimitError(PDFProcessingError):
    """Raised when PDF file exceeds size limit."""
    pass


@dataclass
class PageFinding(Finding):
    """Finding with additional page number information."""
    page_number: int = 1


@dataclass
class PDFProcessingResult:
    """Result of PDF processing including findings and metadata."""
    filename: str
    status: str
    page_count: int
    file_size: int
    findings: List[Finding]
    extracted_text: str
    processing_time_ms: float
    error_message: Optional[str] = None
    
    def get_summary(self) -> Dict[str, Union[int, float, Dict[str, int]]]:
        """
        Generate summary statistics for the processing result.
        
        Returns:
            Dictionary containing summary statistics.
        """
        findings_by_type = {}
        pages_with_findings = set()
        
        for finding in self.findings:
            finding_type = finding.type.value
            findings_by_type[finding_type] = findings_by_type.get(finding_type, 0) + 1
            
            if hasattr(finding, 'page_number'):
                pages_with_findings.add(finding.page_number)
        
        return {
            'total_findings': len(self.findings),
            'findings_by_type': findings_by_type,
            'pages_with_findings': len(pages_with_findings),
            'file_size_kb': round(self.file_size / 1024, 2),
            'processing_time_ms': self.processing_time_ms,
            'page_count': self.page_count
        }


class PDFProcessor:
    """
    Processes PDF files to extract text and detect sensitive data.
    
    This processor handles various PDF formats, extracts text content,
    and uses the SensitiveDataDetector to identify PII. It includes
    error handling for corrupted files and size limits.
    """
    
    DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    def __init__(self, max_file_size: int = DEFAULT_MAX_FILE_SIZE):
        """
        Initialize PDF processor with configuration.
        
        Args:
            max_file_size: Maximum allowed file size in bytes.
        """
        self.detector = create_detector()
        self.max_file_size = max_file_size
        logger.info(f"PDFProcessor initialized with max file size: {max_file_size} bytes")
    
    def _is_pdf_encrypted(self, pdf_data: bytes) -> bool:
        """
        Check if PDF is encrypted/password-protected.
        
        Args:
            pdf_data: Raw PDF data.
            
        Returns:
            True if PDF is encrypted, False otherwise.
        """
        try:
            pdf_stream = io.BytesIO(pdf_data)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            return pdf_reader.is_encrypted
        except Exception:
            return False
    
    def _extract_with_pypdf2(self, pdf_data: bytes) -> Tuple[str, List[str]]:
        """Extract text using PyPDF2 as fallback method."""
        page_texts = []
        
        pdf_stream = io.BytesIO(pdf_data)
        pdf_reader = PyPDF2.PdfReader(pdf_stream)
        
        for page_num in range(len(pdf_reader.pages)):
            try:
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                page_texts.append(text)
            except Exception as e:
                logger.warning(f"Failed to extract page {page_num + 1}: {e}")
                page_texts.append("")
        
        full_text = "\n".join(page_texts)
        return full_text, page_texts
    
    def _extract_with_pdfplumber(self, pdf_data: bytes) -> Tuple[str, List[str]]:
        """Extract text using pdfplumber for better layout handling."""
        page_texts = []
        
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text() or ""
                    page_texts.append(text)
                except Exception as e:
                    logger.warning(f"Failed to extract page {page_num + 1}: {e}")
                    page_texts.append("")
        
        full_text = "\n".join(page_texts)
        return full_text, page_texts
    
    def _extract_text_from_pdf(self, pdf_data: bytes) -> Tuple[str, List[str]]:
        """
        Extract text content from PDF using multiple methods for reliability.
        
        Args:
            pdf_data: Raw PDF data.
            
        Returns:
            Tuple of (full_text, list_of_page_texts).
        """
        # Try pdfplumber first (better for complex layouts)
        try:
            return self._extract_with_pdfplumber(pdf_data)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed, trying PyPDF2: {e}")
        
        # Fallback to PyPDF2
        try:
            return self._extract_with_pypdf2(pdf_data)
        except Exception as e:
            logger.error(f"Both extraction methods failed: {e}")
            raise
    
    def _detect_sensitive_data_by_page(self, page_texts: List[str]) -> List[PageFinding]:
        """
        Detect sensitive data in each page and track page numbers.
        
        Args:
            page_texts: List of text content for each page.
            
        Returns:
            List of PageFinding objects with page numbers.
        """
        all_findings = []
        
        for page_num, page_text in enumerate(page_texts, start=1):
            if not page_text.strip():
                continue
            
            # Detect sensitive data in this page
            page_findings = self.detector.detect(page_text)
            
            # Convert to PageFinding with page number
            for finding in page_findings:
                page_finding = PageFinding(
                    type=finding.type,
                    value=finding.value,
                    start_pos=finding.start_pos,
                    end_pos=finding.end_pos,
                    confidence=finding.confidence,
                    context=finding.context,
                    redaction_text=finding.redaction_text,
                    page_number=page_num
                )
                all_findings.append(page_finding)
        
        return all_findings
    
    def process_pdf(self, pdf_data: bytes, filename: str = "unnamed.pdf") -> PDFProcessingResult:
        """
        Process PDF data to extract text and detect sensitive information.
        
        Args:
            pdf_data: Raw PDF file data.
            filename: Name of the PDF file for reference.
            
        Returns:
            PDFProcessingResult containing findings and metadata.
            
        Raises:
            PDFSizeLimitError: If file exceeds size limit.
            CorruptedPDFError: If PDF is corrupted or unreadable.
            PDFProcessingError: For other processing errors.
        """
        start_time = time.time()
        
        # Validate file size
        file_size = len(pdf_data)
        if file_size > self.max_file_size:
            raise PDFSizeLimitError(
                f"File {filename} size ({file_size} bytes) exceeds maximum size ({self.max_file_size} bytes)"
            )
        
        # Check for password protection
        if self._is_pdf_encrypted(pdf_data):
            raise PDFProcessingError(f"Cannot process password-protected PDF: {filename}")
        
        try:
            # Extract text from PDF
            extracted_text, page_texts = self._extract_text_from_pdf(pdf_data)
            page_count = len(page_texts)
            
            # Detect sensitive data
            findings = self._detect_sensitive_data_by_page(page_texts)
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Successfully processed {filename}: {page_count} pages, {len(findings)} findings"
            )
            
            return PDFProcessingResult(
                filename=filename,
                status="success",
                page_count=page_count,
                file_size=file_size,
                findings=findings,
                extracted_text=extracted_text,
                processing_time_ms=processing_time_ms
            )
            
        except (PdfReadError, ValueError) as e:
            logger.error(f"Corrupted PDF file {filename}: {e}")
            raise CorruptedPDFError(f"Failed to read PDF {filename}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error processing {filename}: {e}")
            raise PDFProcessingError(f"Failed to process PDF {filename}: {str(e)}")
    
    def process_pdf_from_path(self, file_path: Union[str, Path]) -> PDFProcessingResult:
        """
        Process PDF from file path.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            PDFProcessingResult containing findings and metadata.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise PDFProcessingError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise PDFProcessingError(f"Not a file: {file_path}")
        
        with open(file_path, 'rb') as pdf_file:
            pdf_data = pdf_file.read()
        
        return self.process_pdf(pdf_data, filename=file_path.name)
    
    def process_pdf_from_stream(
        self, 
        stream: BinaryIO, 
        filename: str = "stream.pdf"
    ) -> PDFProcessingResult:
        """
        Process PDF from file-like object.
        
        Args:
            stream: File-like object containing PDF data.
            filename: Name for reference.
            
        Returns:
            PDFProcessingResult containing findings and metadata.
        """
        pdf_data = stream.read()
        return self.process_pdf(pdf_data, filename=filename)


def create_pdf_processor(max_file_size: Optional[int] = None) -> PDFProcessor:
    """
    Factory function to create a configured PDFProcessor instance.
    
    Args:
        max_file_size: Maximum allowed file size in bytes.
        
    Returns:
        Configured PDFProcessor instance.
    """
    if max_file_size is None:
        max_file_size = PDFProcessor.DEFAULT_MAX_FILE_SIZE
    
    return PDFProcessor(max_file_size=max_file_size)


if __name__ == "__main__":
    # Example usage
    processor = create_pdf_processor()
    
    # Process a sample PDF file
    sample_pdf_path = Path("sample.pdf")
    if sample_pdf_path.exists():
        result = processor.process_pdf_from_path(sample_pdf_path)
        print(f"Processed {result.filename}:")
        print(f"  Pages: {result.page_count}")
        print(f"  Findings: {len(result.findings)}")
        print(f"  Processing time: {result.processing_time_ms:.2f}ms")
        
        for finding in result.findings:
            print(f"  - {finding.type.value}: {finding.value} (page {finding.page_number})")