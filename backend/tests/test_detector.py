"""
Test suite for the sensitive data detection module.

Tests cover email detection, SSN detection with various formats,
validation logic, edge cases, and performance requirements.
"""

import time
from typing import List

import pytest

from app.core.detector import (
    DetectorError,
    Finding,
    FindingType,
    InvalidPatternError,
    SensitiveDataDetector,
    create_detector
)


class TestSensitiveDataDetector:
    """Test suite for sensitive data detection functionality."""
    
    @pytest.fixture
    def detector(self) -> SensitiveDataDetector:
        """Create a detector instance for testing."""
        return create_detector()
    
    @pytest.fixture
    def email_test_cases(self) -> List[tuple]:
        """Provide email test cases with expected results."""
        return [
            ("Contact me at john.doe@example.com for more info.", ["john.doe@example.com"]),
            ("Emails: admin@company.com, support@company.co.uk", ["admin@company.com", "support@company.co.uk"]),
            ("User email: user123@example.com", ["user123@example.com"]),
            ("Email with dots: first.last.name@sub.domain.com", ["first.last.name@sub.domain.com"]),
            ("Multiple domains: test@domain.org and test@domain.edu", ["test@domain.org", "test@domain.edu"]),
        ]
    
    @pytest.fixture
    def ssn_test_cases(self) -> List[tuple]:
        """Provide SSN test cases with expected results."""
        return [
            ("Employee SSN: 123-45-6789", ["123-45-6789"]),
            ("The SSN is 123456789 in the system.", ["123456789"]),
            ("Social Security: 123 45 6789", ["123 45 6789"]),
            ("Multiple formats: 111-22-3333 and 444556666", ["111-22-3333", "444556666"]),
        ]
    
    @pytest.fixture
    def invalid_ssn_cases(self) -> List[str]:
        """Provide invalid SSN test cases that should not be detected."""
        return [
            "Invalid SSN: 000-12-3456",  # Invalid area
            "Bad SSN: 666-12-3456",       # Invalid area
            "Wrong SSN: 900-12-3456",     # Invalid area
            "Bad format: 123-00-4567",    # Invalid group
            "Wrong format: 123-45-0000",  # Invalid serial
            "Not SSN: 12-345-6789",       # Wrong format
            "Not SSN: 1234-56-789",       # Wrong format
        ]
    
    def test_detector_initialization(self):
        """Test that detector initializes successfully."""
        detector = SensitiveDataDetector()
        assert detector is not None
        assert hasattr(detector, '_email_pattern')
        assert hasattr(detector, '_ssn_patterns')
    
    def test_factory_function(self):
        """Test the factory function creates a valid detector."""
        detector = create_detector()
        assert isinstance(detector, SensitiveDataDetector)
    
    def test_detect_emails_parametrized(self, detector, email_test_cases):
        """Test email detection with various cases."""
        for text, expected_emails in email_test_cases:
            findings = detector.detect(text)
            email_findings = [f for f in findings if f.type == FindingType.EMAIL]
            found_emails = [f.value for f in email_findings]
            
            assert len(found_emails) == len(expected_emails)
            assert set(found_emails) == set(expected_emails)
    
    def test_detect_ssns_parametrized(self, detector, ssn_test_cases):
        """Test SSN detection with various formats."""
        for text, expected_ssns in ssn_test_cases:
            findings = detector.detect(text)
            ssn_findings = [f for f in findings if f.type == FindingType.SSN]
            found_ssns = [f.value for f in ssn_findings]
            
            assert len(found_ssns) == len(expected_ssns)
            assert set(found_ssns) == set(expected_ssns)
    
    def test_invalid_ssns_not_detected(self, detector, invalid_ssn_cases):
        """Test that invalid SSNs are properly filtered out."""
        for text in invalid_ssn_cases:
            findings = detector.detect(text)
            ssn_findings = [f for f in findings if f.type == FindingType.SSN]
            assert len(ssn_findings) == 0, f"Invalid SSN detected in: {text}"
    
    def test_email_position_tracking(self, detector):
        """Test accurate position tracking for email addresses."""
        text = "Contact me at john.doe@example.com for more info."
        findings = detector.detect(text)
        
        assert len(findings) == 1
        finding = findings[0]
        assert finding.type == FindingType.EMAIL
        assert finding.value == "john.doe@example.com"
        assert finding.start_pos == 14
        assert finding.end_pos == 35
        assert text[finding.start_pos:finding.end_pos] == finding.value
    
    def test_ssn_position_tracking(self, detector):
        """Test accurate position tracking for SSNs."""
        text = "Employee SSN: 123-45-6789"
        findings = detector.detect(text)
        
        ssn_findings = [f for f in findings if f.type == FindingType.SSN]
        assert len(ssn_findings) == 1
        finding = ssn_findings[0]
        assert finding.value == "123-45-6789"
        assert finding.start_pos == 14
        assert finding.end_pos == 25
        assert text[finding.start_pos:finding.end_pos] == finding.value
    
    def test_mixed_content_detection(self, detector):
        """Test detection of both emails and SSNs in the same text."""
        text = """
        Employee Record:
        Name: John Doe
        Email: john.doe@company.com
        SSN: 123-45-6789
        Backup email: jdoe@personal.com
        """
        findings = detector.detect(text)
        
        email_findings = [f for f in findings if f.type == FindingType.EMAIL]
        ssn_findings = [f for f in findings if f.type == FindingType.SSN]
        
        assert len(email_findings) == 2
        assert len(ssn_findings) == 1
        
        email_values = {f.value for f in email_findings}
        assert email_values == {"john.doe@company.com", "jdoe@personal.com"}
        assert ssn_findings[0].value == "123-45-6789"
    
    def test_ssn_confidence_with_context(self, detector):
        """Test SSN confidence scoring based on context."""
        text_with_context = "The employee's social security number is 123-45-6789"
        text_without_context = "Random number in text: 123-45-6789"
        
        findings_with = detector.detect(text_with_context)
        findings_without = detector.detect(text_without_context)
        
        assert len(findings_with) == 1
        assert len(findings_without) == 1
        
        assert findings_with[0].confidence == 1.0  # Has context
        assert findings_without[0].confidence == 0.8  # No context
    
    def test_empty_and_none_input(self, detector):
        """Test handling of empty and None inputs."""
        assert detector.detect("") == []
        assert detector.detect(None) == []
        assert detector.detect("   ") == []  # Whitespace only
    
    def test_findings_sorted_by_position(self, detector):
        """Test that findings are returned sorted by position."""
        text = "SSN: 123-45-6789, Email: test@example.com, Another SSN: 987-65-4321"
        findings = detector.detect(text)
        
        assert len(findings) == 3
        positions = [f.start_pos for f in findings]
        assert positions == sorted(positions)
    
    def test_context_extraction(self, detector):
        """Test context extraction for findings."""
        text = "This is a long text with an email address test@example.com in the middle of it."
        findings = detector.detect(text)
        
        assert len(findings) == 1
        context = findings[0].context
        assert "test@example.com" in context
        assert context.startswith("...")
        assert context.endswith("...")
    
    def test_redaction_text_field(self, detector):
        """Test that findings include redaction text."""
        text = "Email: test@example.com"
        findings = detector.detect(text)
        
        assert len(findings) == 1
        assert findings[0].redaction_text == "[REDACTED]"
    
    def test_performance_large_text(self, detector):
        """Test performance requirements for large texts."""
        # Generate large text with many sensitive items
        large_text_parts = []
        for i in range(100):
            large_text_parts.append(
                f"Email{i}: user{i}@example.com and SSN{i}: {100+i:03d}-{10+(i%90):02d}-{1000+i:04d}"
            )
        large_text = " ".join(large_text_parts)
        
        start_time = time.time()
        findings = detector.detect(large_text)
        elapsed_time = time.time() - start_time
        
        # Performance requirement: process in under 1 second
        assert elapsed_time < 1.0, f"Processing took {elapsed_time:.2f}s, expected < 1s"
        
        # Verify correct number of findings
        email_findings = [f for f in findings if f.type == FindingType.EMAIL]
        ssn_findings = [f for f in findings if f.type == FindingType.SSN]
        assert len(email_findings) == 100
        assert len(ssn_findings) == 100
    
    def test_special_characters_in_email(self, detector):
        """Test email detection with special characters."""
        text = "Valid emails: user+tag@example.com, first_last@company.co"
        findings = detector.detect(text)
        
        email_findings = [f for f in findings if f.type == FindingType.EMAIL]
        assert len(email_findings) == 2
        
        email_values = {f.value for f in email_findings}
        assert email_values == {"user+tag@example.com", "first_last@company.co"}
    
    def test_edge_case_positions(self, detector):
        """Test detection at the beginning and end of text."""
        text_start = "admin@example.com is the admin email."
        text_end = "The employee's SSN is 123-45-6789"
        
        findings_start = detector.detect(text_start)
        findings_end = detector.detect(text_end)
        
        assert len(findings_start) == 1
        assert findings_start[0].start_pos == 0
        
        assert len(findings_end) == 1
        assert findings_end[0].end_pos == len(text_end)
    
    def test_overlapping_patterns(self, detector):
        """Test handling of potentially overlapping patterns."""
        text = "SSN formats: 123-45-6789, 123456789, 123 45 6789 (all same number)"
        findings = detector.detect(text)
        
        ssn_findings = [f for f in findings if f.type == FindingType.SSN]
        # Should detect all three formats as separate findings
        assert len(ssn_findings) == 3
        
        # Verify they're at different positions
        positions = [(f.start_pos, f.end_pos) for f in ssn_findings]
        assert len(set(positions)) == 3