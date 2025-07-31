"""
PDF redaction service for creating censored versions of documents.

This module handles the generation of redacted PDFs where sensitive
data is blacked out while maintaining the original document structure.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import fitz  # PyMuPDF

from app.services.pdf_processor import PageFinding

logger = logging.getLogger(__name__)


class RedactionError(Exception):
    """Base exception for redaction errors."""
    
    pass


class PDFRedactor:
    """
    Creates redacted versions of PDFs by blacking out sensitive data.
    
    Uses PyMuPDF (fitz) to maintain document structure while applying
    redactions at specific text locations.
    """
    
    # Default configuration values
    DEFAULT_REDACTION_COLOR = (0, 0, 0)  # RGB black
    DEFAULT_BORDER_EXPAND = 2  # Pixels to expand redaction box
    DEFAULT_PREVIEW_ZOOM = 2.0  # Zoom factor for preview images
    
    def __init__(
        self,
        redaction_color: Tuple[int, int, int] = DEFAULT_REDACTION_COLOR,
        border_expand: int = DEFAULT_BORDER_EXPAND
    ):
        """
        Initialize the PDF redactor.
        
        Args:
            redaction_color: RGB color tuple for redaction boxes.
            border_expand: Pixels to expand redaction box for better coverage.
        """
        self.redaction_color = redaction_color
        self.border_expand = border_expand
    
    def create_redacted_pdf(
        self,
        pdf_data: bytes,
        findings: List[PageFinding],
        output_path: Optional[Path] = None
    ) -> bytes:
        """
        Create a redacted version of the PDF with sensitive data blacked out.
        
        Args:
            pdf_data: Original PDF file data.
            findings: List of findings with page numbers and positions.
            output_path: Optional path to save the redacted PDF.
            
        Returns:
            Redacted PDF as bytes.
            
        Raises:
            RedactionError: If redaction fails.
        """
        if not pdf_data:
            raise RedactionError("PDF data cannot be empty")
        
        pdf_document = None
        try:
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            
            findings_by_page = self._group_findings_by_page(findings)
            
            # Apply redactions to each page containing findings
            for page_num, page_findings in findings_by_page.items():
                if 1 <= page_num <= pdf_document.page_count:
                    page = pdf_document[page_num - 1]  # Convert to 0-indexed
                    self._redact_page(page, page_findings)
                else:
                    logger.warning(
                        f"Skipping invalid page number {page_num} "
                        f"(document has {pdf_document.page_count} pages)"
                    )
            
            redacted_data = pdf_document.tobytes()
            
            if output_path:
                self._save_redacted_pdf(redacted_data, output_path)
            
            logger.info(
                f"Successfully redacted PDF with {len(findings)} findings "
                f"across {len(findings_by_page)} pages"
            )
            return redacted_data
            
        except fitz.FileDataError as e:
            raise RedactionError(f"Invalid PDF data: {e}")
        except Exception as e:
            logger.error(f"Failed to create redacted PDF: {e}")
            raise RedactionError(f"Redaction failed: {e}")
        finally:
            if pdf_document:
                pdf_document.close()
    
    def create_redaction_preview(
        self,
        pdf_data: bytes,
        findings: List[PageFinding],
        page_number: int = 1,
        zoom: float = DEFAULT_PREVIEW_ZOOM
    ) -> bytes:
        """
        Create a preview image of a redacted page.
        
        Args:
            pdf_data: Original PDF data.
            findings: List of findings.
            page_number: Page to preview (1-indexed).
            zoom: Zoom factor for preview quality.
            
        Returns:
            PNG image data of the redacted page.
            
        Raises:
            RedactionError: If preview generation fails.
        """
        if not pdf_data:
            raise RedactionError("PDF data cannot be empty")
        
        pdf_document = None
        try:
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            
            if not 1 <= page_number <= pdf_document.page_count:
                raise RedactionError(
                    f"Page {page_number} does not exist "
                    f"(document has {pdf_document.page_count} pages)"
                )
            
            page = pdf_document[page_number - 1]
            
            # Filter findings for the requested page
            page_findings = [
                f for f in findings 
                if f.page_number == page_number
            ]
            
            if page_findings:
                self._redact_page(page, page_findings)
            
            # Render page to high-quality image
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix)
            img_data = pixmap.tobytes(output="png")
            
            return img_data
            
        except fitz.FileDataError as e:
            raise RedactionError(f"Invalid PDF data: {e}")
        except Exception as e:
            logger.error(f"Failed to create preview: {e}")
            raise RedactionError(f"Preview generation failed: {e}")
        finally:
            if pdf_document:
                pdf_document.close()
    
    def get_redaction_statistics(
        self, 
        findings: List[PageFinding]
    ) -> Dict[str, any]:
        """
        Get statistics about what will be redacted.
        
        Args:
            findings: List of findings to be redacted.
            
        Returns:
            Dictionary with redaction statistics including:
            - total_redactions: Total number of redactions
            - by_type: Count of redactions by finding type
            - by_page: Count of redactions by page number
            - unique_values: Count of unique values by type
        """
        stats = {
            "total_redactions": len(findings),
            "by_type": {},
            "by_page": {},
            "unique_values": {}
        }
        
        # Track unique values per type for accurate counting
        unique_values_by_type: Dict[str, Set[str]] = {}
        
        for finding in findings:
            finding_type = finding.type.value
            
            # Count by type
            stats["by_type"][finding_type] = (
                stats["by_type"].get(finding_type, 0) + 1
            )
            
            # Count by page
            page = finding.page_number
            stats["by_page"][page] = stats["by_page"].get(page, 0) + 1
            
            # Track unique values
            if finding_type not in unique_values_by_type:
                unique_values_by_type[finding_type] = set()
            unique_values_by_type[finding_type].add(finding.value)
        
        # Convert sets to counts for the final statistics
        stats["unique_values"] = {
            finding_type: len(values)
            for finding_type, values in unique_values_by_type.items()
        }
        
        return stats
    
    def _group_findings_by_page(
        self, 
        findings: List[PageFinding]
    ) -> Dict[int, List[PageFinding]]:
        """
        Group findings by their page number.
        
        Args:
            findings: List of findings to group.
            
        Returns:
            Dictionary mapping page numbers to lists of findings.
        """
        grouped = {}
        for finding in findings:
            page_num = finding.page_number
            if page_num not in grouped:
                grouped[page_num] = []
            grouped[page_num].append(finding)
        return grouped
    
    def _redact_page(
        self, 
        page: fitz.Page, 
        findings: List[PageFinding]
    ) -> None:
        """
        Apply redactions to a single page.
        
        Args:
            page: PyMuPDF page object.
            findings: Findings on this page.
        """
        for finding in findings:
            # Search for all instances of the sensitive text
            text_instances = page.search_for(finding.value)
            
            if not text_instances:
                # Fallback: case-insensitive search with whitespace preservation
                text_instances = page.search_for(
                    finding.value, 
                    flags=fitz.TEXT_PRESERVE_WHITESPACE
                )
            
            if text_instances:
                self._apply_standard_redactions(page, text_instances)
            else:
                # Use fallback method if text search fails
                self._apply_fallback_redaction(page, finding.value)
        
        # Apply all redactions at once for efficiency
        page.apply_redactions()
    
    def _apply_standard_redactions(
        self, 
        page: fitz.Page, 
        text_instances: List[fitz.Rect]
    ) -> None:
        """
        Apply standard redaction annotations to text instances.
        
        Args:
            page: PyMuPDF page object.
            text_instances: List of rectangles covering text to redact.
        """
        for rect in text_instances:
            # Expand rectangle for better visual coverage
            expanded_rect = fitz.Rect(
                rect.x0 - self.border_expand,
                rect.y0 - self.border_expand,
                rect.x1 + self.border_expand,
                rect.y1 + self.border_expand
            )
            
            # Add redaction annotation
            page.add_redact_annot(expanded_rect)
    
    def _apply_fallback_redaction(
        self, 
        page: fitz.Page, 
        text: str
    ) -> None:
        """
        Apply fallback redaction using direct rectangle drawing.
        
        This method is used when standard text search fails to locate
        the sensitive text, possibly due to encoding or formatting issues.
        
        Args:
            page: PyMuPDF page object.
            text: Text to search for and redact.
        """
        # Extract text with detailed position information
        text_dict = page.get_text("dict")
        text_lower = text.lower()
        
        for block in text_dict.get("blocks", []):
            # Process only text blocks (type 0)
            if block.get("type") != 0:
                continue
                
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if text_lower in span_text.lower():
                        bbox = span.get("bbox")
                        if bbox:
                            rect = fitz.Rect(bbox)
                            # Draw filled rectangle as redaction
                            page.draw_rect(
                                rect, 
                                color=self.redaction_color, 
                                fill=self.redaction_color
                            )
    
    def _save_redacted_pdf(
        self, 
        redacted_data: bytes, 
        output_path: Path
    ) -> None:
        """
        Save redacted PDF data to file.
        
        Args:
            redacted_data: Redacted PDF bytes.
            output_path: Path to save the file.
            
        Raises:
            RedactionError: If file cannot be saved.
        """
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(redacted_data)
                
            logger.info(f"Saved redacted PDF to {output_path}")
            
        except IOError as e:
            raise RedactionError(f"Failed to save redacted PDF: {e}")


def create_redacted_filename(original_filename: str) -> str:
    """
    Create a filename for the redacted version.
    
    Args:
        original_filename: Original PDF filename.
        
    Returns:
        Redacted filename with '_REDACTED' suffix.
        
    Examples:
        >>> create_redacted_filename("document.pdf")
        'document_REDACTED.pdf'
        >>> create_redacted_filename("report.PDF")
        'report_REDACTED.PDF'
    """
    path = Path(original_filename)
    return f"{path.stem}_REDACTED{path.suffix}"
