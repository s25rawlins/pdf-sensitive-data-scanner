"""
Sensitive data detection module for identifying PII in text content.

This module provides regex-based detection of sensitive information such as
email addresses and Social Security Numbers (SSNs) with validation and
context-aware confidence scoring.
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class FindingType(Enum):
    """Types of sensitive data that can be detected."""
    EMAIL = "email"
    SSN = "ssn"


@dataclass
class Finding:
    """Represents a sensitive data finding in text."""
    type: FindingType
    value: str
    start_pos: int
    end_pos: int
    confidence: float = 1.0
    context: Optional[str] = None
    redaction_text: str = "[REDACTED]"


class DetectorError(Exception):
    """Base exception for detector-related errors."""
    pass


class InvalidPatternError(DetectorError):
    """Raised when a regex pattern is invalid."""
    pass


class SensitiveDataDetector:
    """
    Detects sensitive data (emails, SSNs) in text using regex patterns.
    
    This detector uses compiled regex patterns for performance and includes
    validation logic to reduce false positives. SSN detection includes
    context-aware confidence scoring.
    """
    
    # Email regex pattern based on RFC 5322 simplified for practical use
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # SSN format patterns
    SSN_DASHED_PATTERN = r'\b(\d{3})-(\d{2})-(\d{4})\b'
    SSN_CONTINUOUS_PATTERN = r'\b(\d{3})(\d{2})(\d{4})\b'
    SSN_SPACED_PATTERN = r'\b(\d{3})\s(\d{2})\s(\d{4})\b'
    
    # Context indicators for SSN detection
    SSN_CONTEXT_KEYWORDS = frozenset([
        'ssn', 'social security', 'social', 'tin', 'taxpayer',
        'tax id', 'social security number', 'ss#', 'soc sec'
    ])
    
    # Invalid SSN prefixes according to SSA guidelines
    INVALID_SSN_AREA_NUMBERS = frozenset(['000', '666'] + [f'{i:03d}' for i in range(900, 1000)])
    
    def __init__(self):
        """Initialize the detector with compiled regex patterns."""
        try:
            self._email_pattern = re.compile(self.EMAIL_PATTERN)
            self._ssn_patterns = [
                re.compile(self.SSN_DASHED_PATTERN),
                re.compile(self.SSN_CONTINUOUS_PATTERN),
                re.compile(self.SSN_SPACED_PATTERN),
            ]
        except re.error as e:
            raise InvalidPatternError(f"Failed to compile regex pattern: {e}")
        
        logger.info("SensitiveDataDetector initialized successfully")
    
    def detect(self, text: Optional[str]) -> List[Finding]:
        """
        Detect all sensitive data in the given text.
        
        Args:
            text: The text to scan for sensitive data.
            
        Returns:
            List of Finding objects sorted by position in text.
            
        Raises:
            DetectorError: If detection fails unexpectedly.
        """
        if not text:
            return []
        
        try:
            findings = []
            findings.extend(self._detect_emails(text))
            findings.extend(self._detect_ssns(text))
            
            # Sort by position for consistent output
            findings.sort(key=lambda f: f.start_pos)
            
            logger.debug(f"Detected {len(findings)} sensitive items in text")
            return findings
            
        except Exception as e:
            logger.error(f"Unexpected error during detection: {e}")
            raise DetectorError(f"Detection failed: {e}") from e
    
    def _extract_context(self, text: str, start: int, end: int, window: int = 30) -> str:
        """
        Extract surrounding context for a finding.
        
        Args:
            text: Full text.
            start: Start position of the finding.
            end: End position of the finding.
            window: Characters to include before and after the finding.
            
        Returns:
            Context string with ellipsis if truncated.
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        
        prefix = "..." if context_start > 0 else ""
        suffix = "..." if context_end < len(text) else ""
        
        context = text[context_start:context_end]
        
        return f"{prefix}{context}{suffix}"
    
    def _detect_emails(self, text: str) -> List[Finding]:
        """
        Detect email addresses in text.
        
        Args:
            text: Text to search for email addresses.
            
        Returns:
            List of Finding objects for detected emails.
        """
        findings = []
        
        for match in self._email_pattern.finditer(text):
            email_address = match.group()
            
            finding = Finding(
                type=FindingType.EMAIL,
                value=email_address,
                start_pos=match.start(),
                end_pos=match.end(),
                confidence=1.0,
                context=self._extract_context(text, match.start(), match.end())
            )
            findings.append(finding)
            
            logger.debug(f"Found email: {email_address} at position {match.start()}")
        
        return findings
    
    def _is_valid_ssn_format(self, area: str, group: str, serial: str) -> bool:
        """
        Validate SSN components according to SSA rules.
        
        Invalid SSNs:
        - Area numbers: 000, 666, 900-999
        - Group number: 00
        - Serial number: 0000
        
        Args:
            area: First 3 digits of SSN.
            group: Middle 2 digits of SSN.
            serial: Last 4 digits of SSN.
            
        Returns:
            True if SSN format is valid, False otherwise.
        """
        if area in self.INVALID_SSN_AREA_NUMBERS:
            return False
        
        if group == '00':
            return False
        
        if serial == '0000':
            return False
        
        return True
    
    def _calculate_ssn_confidence(self, text: str, position: int, context_window: int = 50) -> float:
        """
        Calculate confidence score for SSN detection based on surrounding context.
        
        Args:
            text: Full text containing the SSN.
            position: Starting position of the SSN.
            context_window: Number of characters to examine before the SSN.
            
        Returns:
            Confidence score between 0.8 and 1.0.
        """
        context_start = max(0, position - context_window)
        context_text = text[context_start:position].lower()
        
        # Check for context keywords
        for keyword in self.SSN_CONTEXT_KEYWORDS:
            if keyword in context_text:
                return 1.0
        
        # Default confidence without strong context indicators
        return 0.8
    
    def _detect_ssns(self, text: str) -> List[Finding]:
        """
        Detect Social Security Numbers in text with validation.
        
        Args:
            text: Text to search for SSNs.
            
        Returns:
            List of Finding objects for detected and validated SSNs.
        """
        findings = []
        seen_positions: Set[Tuple[int, int]] = set()
        
        for pattern in self._ssn_patterns:
            for match in pattern.finditer(text):
                position_key = (match.start(), match.end())
                
                # Skip if already found at this position
                if position_key in seen_positions:
                    continue
                
                ssn_value = match.group()
                area_number = match.group(1)
                group_number = match.group(2)
                serial_number = match.group(3)
                
                if not self._is_valid_ssn_format(area_number, group_number, serial_number):
                    continue
                
                confidence = self._calculate_ssn_confidence(text, match.start())
                
                finding = Finding(
                    type=FindingType.SSN,
                    value=ssn_value,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=confidence,
                    context=self._extract_context(text, match.start(), match.end())
                )
                
                findings.append(finding)
                seen_positions.add(position_key)
                
                logger.debug(f"Found SSN at position {match.start()} with confidence {confidence}")
        
        return findings


def create_detector() -> SensitiveDataDetector:
    """
    Factory function to create a configured SensitiveDataDetector instance.
    
    Returns:
        Configured SensitiveDataDetector instance.
        
    Raises:
        DetectorError: If detector initialization fails.
    """
    try:
        return SensitiveDataDetector()
    except Exception as e:
        logger.error(f"Failed to create detector: {e}")
        raise DetectorError(f"Detector initialization failed: {e}") from e


if __name__ == "__main__":
    # Example usage
    sample_text = """
    Employee: John Doe
    Email: john.doe@company.com
    SSN: 123-45-6789
    Please contact admin@company.com for questions.
    """
    
    detector = create_detector()
    findings = detector.detect(sample_text)
    
    for finding in findings:
        print(f"Found {finding.type.value}: {finding.value} at position {finding.start_pos}")