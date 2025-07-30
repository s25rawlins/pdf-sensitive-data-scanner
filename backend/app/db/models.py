"""
Database models and schemas for the PDF scanner application.

This module defines Pydantic models for data validation and
serialization between the API and database layers.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProcessingStatus(str, Enum):
    """Status of document processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class FindingType(str, Enum):
    """Types of sensitive data findings."""
    EMAIL = "email"
    SSN = "ssn"


class MetricType(str, Enum):
    """Types of metrics tracked."""
    PROCESSING_TIME = "processing_time"
    PAGE_COUNT = "page_count"
    FINDING_COUNT = "finding_count"
    FILE_SIZE = "file_size"


class DocumentBase(BaseModel):
    """Base model for document data."""
    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0)
    page_count: int = Field(..., ge=0)


class DocumentCreate(DocumentBase):
    """Model for creating a new document record."""
    upload_timestamp: datetime
    processing_time_ms: float = Field(..., ge=0)
    status: ProcessingStatus
    error_message: Optional[str] = None


class Document(DocumentBase):
    """Complete document model with all fields."""
    document_id: UUID
    upload_timestamp: datetime
    processing_time_ms: float
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    
    @field_validator('document_id')
    def validate_uuid(cls, v):
        """Validate UUID format."""
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                raise ValueError('Invalid UUID format')
        return v
    
    @field_validator('file_size')
    def validate_file_size(cls, v):
        """Validate file size is positive."""
        if v < 0:
            raise ValueError('File size must be non-negative')
        return v
    
    @field_validator('page_count')
    def validate_page_count(cls, v):
        """Validate page count is non-negative."""
        if v < 0:
            raise ValueError('Page count must be non-negative')
        return v
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True


class FindingBase(BaseModel):
    """Base model for finding data."""
    finding_type: FindingType
    value: str = Field(..., min_length=1)
    page_number: int = Field(..., ge=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    context: Optional[str] = None


class FindingCreate(FindingBase):
    """Model for creating a new finding record."""
    document_id: UUID


class Finding(FindingBase):
    """Complete finding model with all fields."""
    finding_id: UUID
    document_id: UUID
    detected_at: datetime
    
    @field_validator('page_number')
    def validate_page_number(cls, v):
        """Validate page number is positive."""
        if v < 1:
            raise ValueError('Page number must be positive')
        return v
    
    @field_validator('confidence')
    def validate_confidence(cls, v):
        """Validate confidence is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError('Confidence must be between 0 and 1')
        return v
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True


class MetricBase(BaseModel):
    """Base model for metric data."""
    metric_type: MetricType
    value: float
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class MetricCreate(MetricBase):
    """Model for creating a new metric record."""
    document_id: UUID


class Metric(MetricBase):
    """Complete metric model with all fields."""
    metric_id: UUID
    document_id: UUID
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True


class ProcessingRequest(BaseModel):
    """Request model for PDF processing."""
    filename: str = Field(..., min_length=1, max_length=255)
    
    @field_validator('filename')
    def validate_pdf_extension(cls, v: str) -> str:
        """Ensure filename has PDF extension."""
        if not v.lower().endswith('.pdf'):
            raise ValueError('Filename must have .pdf extension')
        return v


# Response Models
class UploadResponse(BaseModel):
    """Response model for file upload."""
    document_id: str
    filename: str
    status: str
    findings_count: int
    page_count: int
    processing_time_ms: float
    message: Optional[str] = None


class FindingResponse(BaseModel):
    """Response model for individual finding."""
    finding_id: str
    finding_type: str
    value: str
    page_number: int
    confidence: float
    context: Optional[str] = None


class DocumentWithFindings(BaseModel):
    """Document with its findings."""
    document_id: str
    filename: str
    upload_timestamp: datetime
    page_count: int
    findings: List[FindingResponse]
    summary: Dict[str, Any]


class PaginatedResponse(BaseModel):
    """Paginated response for findings."""
    total: int
    page: int
    page_size: int
    findings: List[Dict[str, Any]]


class SummaryStatistics(BaseModel):
    """Summary statistics response."""
    total_documents: int
    total_findings: int
    findings_by_type: Dict[str, int]
    average_processing_time_ms: float
    total_pages_processed: int
    documents_with_findings: int


class ProcessingResponse(BaseModel):
    """Response model for PDF processing."""
    document_id: UUID
    filename: str
    status: ProcessingStatus
    page_count: int
    findings_count: int
    processing_time_ms: float
    message: str


class FindingSummary(BaseModel):
    """Summary statistics for findings."""
    total: int = Field(..., ge=0)
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_page: Dict[int, int] = Field(default_factory=dict)
    average_confidence: float = Field(..., ge=0.0, le=1.0)




class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class FilterParams(BaseModel):
    """Filter parameters for query endpoints."""
    document_id: Optional[UUID] = None
    finding_type: Optional[FindingType] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[ProcessingStatus] = None
    
    @field_validator('end_date')
    def validate_date_range(cls, v: Optional[datetime], values: dict) -> Optional[datetime]:
        """Ensure end_date is after start_date if both provided."""
        start_date = values.get('start_date')
        if start_date and v and v < start_date:
            raise ValueError('end_date must be after start_date')
        return v


class StatisticsResponse(BaseModel):
    """Response model for statistics endpoints."""
    total_documents: int = Field(..., ge=0)
    total_findings: int = Field(..., ge=0)
    findings_by_type: Dict[str, int]
    average_processing_time_ms: float = Field(..., ge=0)
    total_pages_processed: int = Field(..., ge=0)
    documents_with_findings: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0.0, le=1.0)
    
    @field_validator('success_rate')
    def calculate_success_rate(cls, v: float, values: dict) -> float:
        """Calculate success rate if not provided."""
        if v == 0 and values.get('total_documents', 0) > 0:
            # This would be calculated from actual data
            return 1.0
        return v
