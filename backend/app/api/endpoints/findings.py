"""
Findings retrieval endpoint for accessing detected sensitive data.

This module provides endpoints for querying and retrieving findings
from processed PDF documents stored in ClickHouse.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.db.clickhouse import get_db_client

logger = logging.getLogger(__name__)
router = APIRouter()


class FindingResponse(BaseModel):
    """Response model for individual finding."""
    
    finding_id: str = Field(..., description="Unique identifier for the finding")
    document_id: str = Field(..., description="Associated document ID")
    finding_type: str = Field(..., description="Type of finding (email, ssn)")
    value: str = Field(..., description="The detected sensitive value")
    page_number: int = Field(..., description="Page number where finding was detected")
    confidence: float = Field(..., description="Confidence score (0-1)")
    context: Optional[str] = Field(None, description="Surrounding context")
    detected_at: datetime = Field(..., description="Timestamp of detection")


class DocumentFindingsResponse(BaseModel):
    """Response model for document with its findings."""
    
    document_id: str = Field(..., description="Document identifier")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Number of pages")
    upload_timestamp: datetime = Field(..., description="Upload time")
    processing_time_ms: float = Field(..., description="Processing duration")
    status: str = Field(..., description="Processing status")
    findings: List[FindingResponse] = Field(..., description="List of findings")
    summary: Dict[str, int] = Field(..., description="Summary statistics")


class FindingsListResponse(BaseModel):
    """Response model for paginated findings list."""
    
    total: int = Field(..., description="Total number of results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Results per page")
    findings: List[DocumentFindingsResponse] = Field(..., description="List of documents with findings")


def calculate_summary(findings: List[Dict]) -> Dict[str, int]:
    """
    Calculate summary statistics for findings.
    
    Args:
        findings: List of finding dictionaries.
        
    Returns:
        Dictionary with counts by type.
    """
    summary = {"total": len(findings)}
    
    for finding in findings:
        finding_type = finding.get("finding_type", "unknown")
        summary[finding_type] = summary.get(finding_type, 0) + 1
    
    return summary


@router.get("/findings", response_model=FindingsListResponse)
async def get_all_findings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    doc_id: Optional[str] = Query(None, description="Filter by document ID"),
    finding_type: Optional[str] = Query(None, description="Filter by finding type (email, ssn)"),
    start_date: Optional[datetime] = Query(None, description="Filter by upload date (from)"),
    end_date: Optional[datetime] = Query(None, description="Filter by upload date (to)"),
) -> FindingsListResponse:
    """
    Get all findings with optional filtering and pagination.
    
    Args:
        page: Page number (1-based).
        page_size: Number of results per page.
        doc_id: Optional document ID filter.
        finding_type: Optional finding type filter.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        
    Returns:
        Paginated list of documents with findings.
    """
    logger.info(
        f"Getting findings - page: {page}, page_size: {page_size}, "
        f"doc_id: {doc_id}, finding_type: {finding_type}, "
        f"start_date: {start_date}, end_date: {end_date}"
    )
    
    try:
        db_client = get_db_client()

        offset = (page - 1) * page_size
        
        total_count = await db_client.count_documents(
            doc_id=doc_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        documents = await db_client.get_documents(
            limit=page_size,
            offset=offset,
            doc_id=doc_id,
            start_date=start_date,
            end_date=end_date,
        )
        

        results = []
        
        for doc in documents:
            findings = await db_client.get_findings_by_document(
                document_id=doc["document_id"],
                finding_type=finding_type,
            )
            
            # Convert findings to response model
            finding_responses = [
                FindingResponse(
                    finding_id=f["finding_id"],
                    document_id=f["document_id"],
                    finding_type=f["finding_type"],
                    value=f["value"],
                    page_number=f["page_number"],
                    confidence=f["confidence"],
                    context=f.get("context"),
                    detected_at=f["detected_at"],
                )
                for f in findings
            ]
            
            summary = calculate_summary(findings)
            
            # Build document response
            doc_response = DocumentFindingsResponse(
                document_id=doc["document_id"],
                filename=doc["filename"],
                file_size=doc["file_size"],
                page_count=doc["page_count"],
                upload_timestamp=doc["upload_timestamp"],
                processing_time_ms=doc["processing_time_ms"],
                status=doc["status"],
                findings=finding_responses,
                summary=summary,
            )
            
            results.append(doc_response)
        
        return FindingsListResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            findings=results,
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve findings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve findings from database",
        )


@router.get("/findings/{document_id}", response_model=DocumentFindingsResponse)
async def get_document_findings(document_id: str) -> DocumentFindingsResponse:
    """
    Get findings for a specific document.
    
    Args:
        document_id: UUID of the document.
        
    Returns:
        Document with all its findings.
        
    Raises:
        HTTPException: If document not found.
    """
    try:
        db_client = get_db_client()
        
        # Get document metadata
        document = await db_client.get_document(document_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )
        
        findings = await db_client.get_findings_by_document(document_id)
        
        # Convert to response models
        finding_responses = [
            FindingResponse(
                finding_id=f["finding_id"],
                document_id=f["document_id"],
                finding_type=f["finding_type"],
                value=f["value"],
                page_number=f["page_number"],
                confidence=f["confidence"],
                context=f.get("context"),
                detected_at=f["detected_at"],
            )
            for f in findings
        ]

        summary = calculate_summary(findings)
        
        return DocumentFindingsResponse(
            document_id=document["document_id"],
            filename=document["filename"],
            file_size=document["file_size"],
            page_count=document["page_count"],
            upload_timestamp=document["upload_timestamp"],
            processing_time_ms=document["processing_time_ms"],
            status=document["status"],
            findings=finding_responses,
            summary=summary,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve document findings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document findings",
        )


@router.get("/findings/stats/summary")
async def get_findings_summary() -> Dict:
    """
    Get summary statistics for all findings.
    
    Returns:
        Dictionary with overall statistics.
    """
    
    try:
        db_client = get_db_client()
        
        stats = await db_client.get_summary_statistics()
        
        return {
            "total_documents": stats.get("total_documents", 0),
            "total_findings": stats.get("total_findings", 0),
            "findings_by_type": stats.get("findings_by_type", {}),
            "average_processing_time_ms": stats.get("avg_processing_time", 0),
            "total_pages_processed": stats.get("total_pages", 0),
            "documents_with_findings": stats.get("documents_with_findings", 0),
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve summary statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve summary statistics",
        )
