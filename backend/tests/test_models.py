"""
Tests for Pydantic models.

This module tests all data models to ensure proper validation,
serialization, and business logic.
"""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import (
    Document,
    Finding,
    FindingType,
    ProcessingStatus,
    Metric,
    MetricType,
    UploadResponse,
    FindingResponse,
    DocumentWithFindings,
    PaginatedResponse,
    SummaryStatistics,
)


class TestEnums:
    """Test enum types."""
    
    def test_finding_type_values(self):
        """Test FindingType enum values."""
        assert FindingType.EMAIL.value == "email"
        assert FindingType.SSN.value == "ssn"
        
        # Test all values
        assert set(FindingType.__members__.keys()) == {"EMAIL", "SSN"}
    
    def test_processing_status_values(self):
        """Test ProcessingStatus enum values."""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PROCESSING.value == "processing"
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.FAILED.value == "failed"
        
        # Test all values
        expected = {"PENDING", "PROCESSING", "SUCCESS", "FAILED"}
        assert set(ProcessingStatus.__members__.keys()) == expected
    
    def test_metric_type_values(self):
        """Test MetricType enum values."""
        assert MetricType.PROCESSING_TIME.value == "processing_time"
        assert MetricType.PAGE_COUNT.value == "page_count"
        assert MetricType.FINDING_COUNT.value == "finding_count"
        assert MetricType.FILE_SIZE.value == "file_size"


class TestDocument:
    """Test Document model."""
    
    def test_valid_document(self):
        """Test creating valid document."""
        doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=150.5,
            status=ProcessingStatus.SUCCESS,
            error_message=None,
        )
        
        assert doc.filename == "test.pdf"
        assert doc.file_size == 1024
        assert doc.page_count == 5
        assert doc.status == ProcessingStatus.SUCCESS
        assert doc.error_message is None
    
    def test_document_with_error(self):
        """Test document with error status."""
        doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=0,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=50.0,
            status=ProcessingStatus.FAILED,
            error_message="Failed to process PDF",
        )
        
        assert doc.status == ProcessingStatus.FAILED
        assert doc.error_message == "Failed to process PDF"
    
    def test_document_validation_errors(self):
        """Test document validation errors."""
        # Invalid UUID
        with pytest.raises(ValidationError):
            Document(
                document_id="not-a-uuid",
                filename="test.pdf",
                file_size=1024,
                page_count=5,
                upload_timestamp=datetime.utcnow(),
                processing_time_ms=150.5,
                status=ProcessingStatus.SUCCESS,
            )
        
        # Negative file size
        with pytest.raises(ValidationError):
            Document(
                document_id=str(uuid4()),
                filename="test.pdf",
                file_size=-1,
                page_count=5,
                upload_timestamp=datetime.utcnow(),
                processing_time_ms=150.5,
                status=ProcessingStatus.SUCCESS,
            )
        
        # Negative page count
        with pytest.raises(ValidationError):
            Document(
                document_id=str(uuid4()),
                filename="test.pdf",
                file_size=1024,
                page_count=-1,
                upload_timestamp=datetime.utcnow(),
                processing_time_ms=150.5,
                status=ProcessingStatus.SUCCESS,
            )


class TestFinding:
    """Test Finding model."""
    
    def test_valid_finding(self):
        """Test creating valid finding."""
        finding = Finding(
            finding_id=str(uuid4()),
            document_id=str(uuid4()),
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
            detected_at=datetime.utcnow(),
        )
        
        assert finding.finding_type == FindingType.EMAIL
        assert finding.value == "test@example.com"
        assert finding.confidence == 0.95
        assert finding.page_number == 1
    
    def test_finding_confidence_bounds(self):
        """Test confidence score bounds."""
        doc_id = str(uuid4())
        
        # Valid confidence scores
        for conf in [0.0, 0.5, 1.0]:
            finding = Finding(
                finding_id=str(uuid4()),
                document_id=doc_id,
                finding_type=FindingType.SSN,
                value="123-45-6789",
                page_number=1,
                confidence=conf,
                context="SSN: 123-45-6789",
                detected_at=datetime.utcnow(),
            )
            assert finding.confidence == conf
        
        # Invalid confidence scores
        for conf in [-0.1, 1.1, 2.0]:
            with pytest.raises(ValidationError):
                Finding(
                    finding_id=str(uuid4()),
                    document_id=doc_id,
                    finding_type=FindingType.SSN,
                    value="123-45-6789",
                    page_number=1,
                    confidence=conf,
                    context="SSN: 123-45-6789",
                    detected_at=datetime.utcnow(),
                )
    
    def test_finding_page_number_validation(self):
        """Test page number validation."""
        # Invalid page number (must be positive)
        with pytest.raises(ValidationError):
            Finding(
                finding_id=str(uuid4()),
                document_id=str(uuid4()),
                finding_type=FindingType.EMAIL,
                value="test@example.com",
                page_number=0,
                confidence=1.0,
                context="Email: test@example.com",
                detected_at=datetime.utcnow(),
            )


class TestMetric:
    """Test Metric model."""
    
    def test_valid_metric(self):
        """Test creating valid metric."""
        metric = Metric(
            metric_id=str(uuid4()),
            document_id=str(uuid4()),
            metric_type=MetricType.PROCESSING_TIME,
            value=150.5,
            recorded_at=datetime.utcnow(),
        )
        
        assert metric.metric_type == MetricType.PROCESSING_TIME
        assert metric.value == 150.5
    
    def test_metric_types(self):
        """Test different metric types."""
        doc_id = str(uuid4())
        
        metrics = [
            (MetricType.PROCESSING_TIME, 150.5),
            (MetricType.PAGE_COUNT, 10),
            (MetricType.FINDING_COUNT, 5),
            (MetricType.FILE_SIZE, 1024 * 1024),
        ]
        
        for metric_type, value in metrics:
            metric = Metric(
                metric_id=str(uuid4()),
                document_id=doc_id,
                metric_type=metric_type,
                value=value,
                recorded_at=datetime.utcnow(),
            )
            assert metric.metric_type == metric_type
            assert metric.value == value


class TestResponses:
    """Test response models."""
    
    def test_upload_response(self):
        """Test UploadResponse model."""
        response = UploadResponse(
            document_id=str(uuid4()),
            filename="test.pdf",
            status="success",
            findings_count=5,
            page_count=10,
            processing_time_ms=150.5,
            message="File processed successfully",
        )
        
        assert response.status == "success"
        assert response.findings_count == 5
        assert response.message == "File processed successfully"
    
    def test_finding_response(self):
        """Test FindingResponse model."""
        response = FindingResponse(
            finding_id=str(uuid4()),
            finding_type="email",
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
        )
        
        assert response.finding_type == "email"
        assert response.value == "test@example.com"
        assert response.confidence == 0.95
    
    def test_document_with_findings(self):
        """Test DocumentWithFindings model."""
        doc_id = str(uuid4())
        
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
        
        doc_with_findings = DocumentWithFindings(
            document_id=doc_id,
            filename="test.pdf",
            upload_timestamp=datetime.utcnow(),
            page_count=2,
            findings=findings,
            summary={"total": 2, "email": 1, "ssn": 1},
        )
        
        assert len(doc_with_findings.findings) == 2
        assert doc_with_findings.summary["total"] == 2
        assert doc_with_findings.summary["email"] == 1
        assert doc_with_findings.summary["ssn"] == 1
    
    def test_paginated_response(self):
        """Test PaginatedResponse model."""
        findings = [
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
            findings=findings,
        )
        
        assert paginated.total == 100
        assert paginated.page == 2
        assert paginated.page_size == 5
        assert len(paginated.findings) == 5
    
    def test_summary_statistics(self):
        """Test SummaryStatistics model."""
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


class TestModelSerialization:
    """Test model serialization/deserialization."""
    
    def test_document_json_serialization(self):
        """Test Document JSON serialization."""
        doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=5,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=150.5,
            status=ProcessingStatus.SUCCESS,
            error_message=None,
        )
        
        # Serialize to JSON
        json_data = doc.model_dump_json()
        assert isinstance(json_data, str)
        
        # Deserialize from JSON
        doc2 = Document.model_validate_json(json_data)
        assert doc2.document_id == doc.document_id
        assert doc2.filename == doc.filename
        assert doc2.status == doc.status
    
    def test_finding_dict_serialization(self):
        """Test Finding dict serialization."""
        finding = Finding(
            finding_id=str(uuid4()),
            document_id=str(uuid4()),
            finding_type=FindingType.EMAIL,
            value="test@example.com",
            page_number=1,
            confidence=0.95,
            context="Email: test@example.com",
            detected_at=datetime.utcnow(),
        )
        
        # Serialize to dict
        dict_data = finding.model_dump()
        assert isinstance(dict_data, dict)
        assert dict_data["finding_type"] == "email"
        assert dict_data["value"] == "test@example.com"
        
        # Create from dict
        finding2 = Finding.model_validate(dict_data)
        assert finding2.finding_id == finding.finding_id
        assert finding2.value == finding.value


class TestModelDefaults:
    """Test model default values."""
    
    def test_document_defaults(self):
        """Test Document default values."""
        # Status should default to PENDING
        doc = Document(
            document_id=str(uuid4()),
            filename="test.pdf",
            file_size=1024,
            page_count=0,
            upload_timestamp=datetime.utcnow(),
            processing_time_ms=0.0,
        )
        
        assert doc.status == ProcessingStatus.PENDING
        assert doc.error_message is None
    
    def test_metric_defaults(self):
        """Test Metric default values."""
        # recorded_at should default to current time
        metric = Metric(
            metric_id=str(uuid4()),
            document_id=str(uuid4()),
            metric_type=MetricType.PROCESSING_TIME,
            value=150.5,
        )
        
        assert metric.recorded_at is not None
        assert isinstance(metric.recorded_at, datetime)
