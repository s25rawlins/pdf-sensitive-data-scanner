"""
Tests for Pydantic models.

This module tests all data models to ensure proper validation,
serialization, and business logic.
"""

from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import (
    Document,
    DocumentWithFindings,
    Finding,
    FindingResponse,
    FindingType,
    Metric,
    MetricType,
    PaginatedResponse,
    ProcessingStatus,
    SummaryStatistics,
    UploadResponse,
)


class TestEnums:
    """Test suite for enum types used in models."""

    def test_finding_type_values(self) -> None:
        """Test FindingType enum has correct values."""
        assert FindingType.EMAIL.value == "email"
        assert FindingType.SSN.value == "ssn"

        # Verify all expected values are present
        assert set(FindingType.__members__.keys()) == {"EMAIL", "SSN"}

    def test_processing_status_values(self) -> None:
        """Test ProcessingStatus enum has correct values."""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PROCESSING.value == "processing"
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.FAILED.value == "failed"

        # Verify all expected values are present
        expected_statuses = {"PENDING", "PROCESSING", "SUCCESS", "FAILED"}
        assert set(ProcessingStatus.__members__.keys()) == expected_statuses

    def test_metric_type_values(self) -> None:
        """Test MetricType enum has correct values."""
        assert MetricType.PROCESSING_TIME.value == "processing_time"
        assert MetricType.PAGE_COUNT.value == "page_count"
        assert MetricType.FINDING_COUNT.value == "finding_count"
        assert MetricType.FILE_SIZE.value == "file_size"

        # Verify all expected values are present
        expected_types = {"PROCESSING_TIME", "PAGE_COUNT", "FINDING_COUNT", "FILE_SIZE"}
        assert set(MetricType.__members__.keys()) == expected_types


class TestDocument:
    """Test suite for Document model validation and behavior."""

    def test_valid_document(self) -> None:
        """Test creating a valid document with all required fields."""
        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        doc = Document(
            document_id=doc_id,
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=timestamp,
            processing_time_ms=150.5,
            status=ProcessingStatus.SUCCESS,
            error_message=None,
        )

        assert str(doc.document_id) == doc_id
        assert doc.filename == "test.pdf"
        assert doc.file_size == 1024
        assert doc.page_count == 5
        assert doc.upload_timestamp == timestamp
        assert doc.processing_time_ms == 150.5
        assert doc.status == ProcessingStatus.SUCCESS
        assert doc.error_message is None

    def test_document_with_error(self) -> None:
        """Test creating a document with failed status and error message."""
        error_msg = "Failed to process PDF: Invalid format"

        doc = Document(
            document_id=str(uuid4()),
            filename="corrupted.pdf",
            file_size=1024,
            page_count=0,
            upload_timestamp=datetime.now(timezone.utc),
            processing_time_ms=50.0,
            status=ProcessingStatus.FAILED,
            error_message=error_msg,
        )

        assert doc.status == ProcessingStatus.FAILED
        assert doc.error_message == error_msg
        assert doc.page_count == 0  # Failed documents may have 0 pages

    def test_document_validation_errors(self) -> None:
        """Test document validation with invalid inputs."""
        base_params = {
            "filename": "test.pdf",
            "file_size": 1024,
            "page_count": 5,
            "upload_timestamp": datetime.now(timezone.utc),
            "processing_time_ms": 150.5,
            "status": ProcessingStatus.SUCCESS,
        }

        # Test invalid UUID format
        with pytest.raises(ValidationError) as exc_info:
            Document(document_id="not-a-valid-uuid", **base_params)
        assert "document_id" in str(exc_info.value)

        # Test negative file size
        with pytest.raises(ValidationError) as exc_info:
            Document(document_id=str(uuid4()), file_size=-1, **{k: v for k, v in base_params.items() if k != "file_size"})
        assert "file_size" in str(exc_info.value)

        # Test negative page count
        with pytest.raises(ValidationError) as exc_info:
            Document(document_id=str(uuid4()), page_count=-1, **{k: v for k, v in base_params.items() if k != "page_count"})
        assert "page_count" in str(exc_info.value)


class TestFinding:
    """Test suite for Finding model validation and behavior."""

    def test_valid_finding(self) -> None:
        """Test creating a valid finding with all required fields."""
        finding_id = str(uuid4())
        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        finding = Finding(
            finding_id=finding_id,
            document_id=doc_id,
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
            detected_at=timestamp,
        )

        assert str(finding.finding_id) == finding_id
        assert str(finding.document_id) == doc_id
        assert finding.finding_type == FindingType.EMAIL
        assert finding.value == "test@example.com"
        assert finding.page_number == 1
        assert finding.confidence == 0.95
        assert finding.context == "Email: test@example.com"
        assert finding.detected_at == timestamp

    def test_finding_confidence_bounds(self) -> None:
        """Test confidence score validation (must be between 0 and 1)."""
        doc_id = str(uuid4())
        base_params = {
            "document_id": doc_id,
            "finding_type": FindingType.SSN,
            "value": "123-45-6789",
            "page_number": 1,
            "context": "SSN: 123-45-6789",
            "detected_at": datetime.now(timezone.utc),
        }

        # Test valid confidence scores
        valid_scores = [0.0, 0.1, 0.5, 0.9, 1.0]
        for score in valid_scores:
            finding = Finding(
                finding_id=str(uuid4()),
                confidence=score,
                **base_params
            )
            assert finding.confidence == score

        # Test invalid confidence scores
        invalid_scores = [-0.1, -1.0, 1.1, 2.0, 10.0]
        for score in invalid_scores:
            with pytest.raises(ValidationError) as exc_info:
                Finding(
                    finding_id=str(uuid4()),
                    confidence=score,
                    **base_params
                )
            assert "confidence" in str(exc_info.value)

    def test_finding_page_number_validation(self) -> None:
        """Test page number validation (must be positive)."""
        base_params = {
            "finding_id": str(uuid4()),
            "document_id": str(uuid4()),
            "finding_type": FindingType.EMAIL,
            "value": "test@example.com",
            "confidence": 1.0,
            "context": "Email: test@example.com",
            "detected_at": datetime.now(timezone.utc),
        }

        # Test valid page numbers
        for page_num in [1, 10, 100, 1000]:
            finding = Finding(page_number=page_num, **base_params)
            assert finding.page_number == page_num

        # Test invalid page numbers
        for page_num in [0, -1, -10]:
            with pytest.raises(ValidationError) as exc_info:
                Finding(page_number=page_num, **base_params)
            assert "page_number" in str(exc_info.value)


class TestMetric:
    """Test suite for Metric model validation and behavior."""

    def test_valid_metric(self) -> None:
        """Test creating a valid metric with all required fields."""
        metric_id = str(uuid4())
        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        metric = Metric(
            metric_id=metric_id,
            document_id=doc_id,
            metric_type=MetricType.PROCESSING_TIME,
            value=150.5,
            recorded_at=timestamp,
        )

        assert str(metric.metric_id) == metric_id
        assert str(metric.document_id) == doc_id
        assert metric.metric_type == MetricType.PROCESSING_TIME
        assert metric.value == 150.5
        assert metric.recorded_at == timestamp

    def test_metric_types(self) -> None:
        """Test different metric types with appropriate values."""
        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        test_cases = [
            (MetricType.PROCESSING_TIME, 150.5),  # milliseconds
            (MetricType.PAGE_COUNT, 10.0),  # pages
            (MetricType.FINDING_COUNT, 5.0),  # count
            (MetricType.FILE_SIZE, 1048576.0),  # bytes (1MB)
        ]

        for metric_type, value in test_cases:
            metric = Metric(
                metric_id=str(uuid4()),
                document_id=doc_id,
                metric_type=metric_type,
                value=value,
                recorded_at=timestamp,
            )
            assert metric.metric_type == metric_type
            assert metric.value == value


class TestResponses:
    """Test suite for API response models."""

    def test_upload_response(self) -> None:
        """Test UploadResponse model for successful upload."""
        doc_id = str(uuid4())

        response = UploadResponse(
            document_id=doc_id,
            filename="test.pdf",
            status="success",
            findings_count=5,
            page_count=10,
            processing_time_ms=150.5,
            message="File processed successfully",
        )

        assert response.document_id == doc_id
        assert response.filename == "test.pdf"
        assert response.status == "success"
        assert response.findings_count == 5
        assert response.page_count == 10
        assert response.processing_time_ms == 150.5
        assert response.message == "File processed successfully"

    def test_finding_response(self) -> None:
        """Test FindingResponse model for API output."""
        finding_id = str(uuid4())

        response = FindingResponse(
            finding_id=finding_id,
            finding_type="email",
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
        )

        assert response.finding_id == finding_id
        assert response.finding_type == "email"
        assert response.value == "test@example.com"
        assert response.page_number == 1
        assert response.confidence == 0.95
        assert response.context == "Email: test@example.com"

    def test_document_with_findings(self) -> None:
        """Test DocumentWithFindings composite model."""
        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        # Create test findings
        findings = [
            FindingResponse(
                finding_id=str(uuid4()),
                finding_type="email",
                value="test@example.com",
                page_number=1,
                confidence=1.0,
                context="Email: test@example.com",
            ),
            FindingResponse(
                finding_id=str(uuid4()),
                finding_type="ssn",
                value="123-45-6789",
                page_number=2,
                confidence=0.95,
                context="SSN: 123-45-6789",
            ),
        ]

        # Create document with findings
        doc_with_findings = DocumentWithFindings(
            document_id=doc_id,
            filename="test.pdf",
            upload_timestamp=timestamp,
            page_count=2,
            findings=findings,
            summary={"total": 2, "email": 1, "ssn": 1},
        )

        assert doc_with_findings.document_id == doc_id
        assert doc_with_findings.filename == "test.pdf"
        assert doc_with_findings.upload_timestamp == timestamp
        assert doc_with_findings.page_count == 2
        assert len(doc_with_findings.findings) == 2
        assert doc_with_findings.summary["total"] == 2
        assert doc_with_findings.summary["email"] == 1
        assert doc_with_findings.summary["ssn"] == 1

    def test_paginated_response(self) -> None:
        """Test PaginatedResponse for paginated API results."""
        # Create test data
        findings_data: List[Dict] = [
            {
                "document_id": str(uuid4()),
                "filename": f"test{i}.pdf",
                "findings": [],
            }
            for i in range(5)
        ]

        paginated = PaginatedResponse(
            total=100,
            page=2,
            page_size=5,
            findings=findings_data,
        )

        assert paginated.total == 100
        assert paginated.page == 2
        assert paginated.page_size == 5
        assert len(paginated.findings) == 5

    def test_summary_statistics(self) -> None:
        """Test SummaryStatistics model for analytics data."""
        stats = SummaryStatistics(
            total_documents=100,
            total_findings=250,
            findings_by_type={"email": 150, "ssn": 100},
            average_processing_time_ms=125.5,
            total_pages_processed=500,
            documents_with_findings=80,
        )

        assert stats.total_documents == 100
        assert stats.total_findings == 250
        assert stats.findings_by_type["email"] == 150
        assert stats.findings_by_type["ssn"] == 100
        assert stats.average_processing_time_ms == 125.5
        assert stats.total_pages_processed == 500
        assert stats.documents_with_findings == 80


class TestModelSerialization:
    """Test suite for model serialization and deserialization."""

    def test_document_json_serialization(self) -> None:
        """Test Document model JSON serialization round-trip."""
        original_doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=datetime.now(timezone.utc),
            processing_time_ms=150.5,
            status=ProcessingStatus.SUCCESS,
            error_message=None,
        )

        # Serialize to JSON
        json_data = original_doc.model_dump_json()
        assert isinstance(json_data, str)
        assert "test.pdf" in json_data
        assert "success" in json_data

        # Deserialize from JSON
        restored_doc = Document.model_validate_json(json_data)
        assert restored_doc.document_id == original_doc.document_id
        assert restored_doc.filename == original_doc.filename
        assert restored_doc.file_size == original_doc.file_size
        assert restored_doc.status == original_doc.status

    def test_finding_dict_serialization(self) -> None:
        """Test Finding model dictionary serialization."""
        original_finding = Finding(
            finding_id=str(uuid4()),
            document_id=str(uuid4()),
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
            detected_at=datetime.now(timezone.utc),
        )

        # Serialize to dictionary
        dict_data = original_finding.model_dump()
        assert isinstance(dict_data, dict)
        assert dict_data["finding_type"] == "email"
        assert dict_data["value"] == "test@example.com"
        assert dict_data["confidence"] == 0.95

        # Create from dictionary
        restored_finding = Finding.model_validate(dict_data)
        assert restored_finding.finding_id == original_finding.finding_id
        assert restored_finding.value == original_finding.value
        assert restored_finding.finding_type == original_finding.finding_type


class TestModelDefaults:
    """Test suite for model default values and behaviors."""

    def test_document_defaults(self) -> None:
        """Test Document model default values."""
        # Create document with minimal required fields
        doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=0,
            upload_timestamp=datetime.now(timezone.utc),
            processing_time_ms=0.0,
        )

        # Status should default to PENDING
        assert doc.status == ProcessingStatus.PENDING
        # Error message should default to None
        assert doc.error_message is None

    def test_metric_defaults(self) -> None:
        """Test Metric model default values."""
        # Create metric without recorded_at
        metric = Metric(
            metric_id=str(uuid4()),
            document_id=str(uuid4()),
            metric_type=MetricType.PROCESSING_TIME,
            value=150.5,
        )

        # recorded_at should be automatically set
        assert metric.recorded_at is not None
        assert isinstance(metric.recorded_at, datetime)
        
        # Verify the timestamp is recent (within last minute)
        # Handle both naive and aware datetimes
        if metric.recorded_at.tzinfo is None:
            # Naive datetime - compare with utcnow()
            from datetime import datetime as dt
            time_diff = dt.utcnow() - metric.recorded_at
        else:
            # Aware datetime - compare with now(timezone.utc)
            time_diff = datetime.now(timezone.utc) - metric.recorded_at
        
        assert time_diff.total_seconds() < 60
