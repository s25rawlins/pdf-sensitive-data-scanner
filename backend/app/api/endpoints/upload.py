"""
PDF upload endpoint for processing and analyzing documents.

This module handles file uploads, validation, processing, and
storage of results in ClickHouse.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.db.clickhouse import get_db_client
from app.services.pdf_processor import (
    CorruptedPDFError,
    PDFProcessingError,
    PDFSizeLimitError,
    create_pdf_processor,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

# Semaphore for concurrent upload limiting
upload_semaphore = asyncio.Semaphore(settings.max_concurrent_uploads)


def validate_file_extension(filename: str) -> None:
    """
    Validate that uploaded file has allowed extension.
    
    Args:
        filename: Name of the uploaded file.
        
    Raises:
        HTTPException: If file extension is not allowed.
    """
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in settings.allowed_file_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed types: {settings.allowed_file_extensions}",
        )


def validate_file_size(file_size: int) -> None:
    """
    Validate that uploaded file doesn't exceed size limit.
    
    Args:
        file_size: Size of the uploaded file in bytes.
        
    Raises:
        HTTPException: If file size exceeds limit.
    """
    if file_size > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {file_size} bytes exceeds maximum {settings.max_upload_size} bytes",
        )


async def process_pdf_async(pdf_data: bytes, filename: str) -> Dict:
    """
    Process PDF in background thread to avoid blocking.
    
    Args:
        pdf_data: Raw PDF file data.
        filename: Name of the PDF file.
        
    Returns:
        Processing result dictionary.
        
    Raises:
        Various PDF processing exceptions.
    """
    loop = asyncio.get_event_loop()
    processor = create_pdf_processor()
    
    # Run PDF processing in a separate thread from the async event loop.
    # This prevents blocking other async tasks, even though CPU work still runs one at a time due to Python's GIL.
    result = await loop.run_in_executor(
        None,
        processor.process_pdf,
        pdf_data,
        filename
    )
    
    return result


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_pdf(file: UploadFile = File(...)) -> Dict:
    """
    Upload and process a PDF file for sensitive data detection.
    
    Args:
        file: Uploaded PDF file.
        
    Returns:
        Dictionary containing document ID and processing status.
        
    Raises:
        HTTPException: For various error conditions.
    """

    validate_file_extension(file.filename)
    
    try:
        pdf_data = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file",
        )
    
    validate_file_size(len(pdf_data))
    
    document_id = str(uuid.uuid4())
    upload_timestamp = datetime.utcnow()
    
    # Acquire semaphore for concurrent upload limiting
    async with upload_semaphore:
        # Get database client early so it's available in exception handlers
        db_client = get_db_client()
        
        try:
            logger.info(f"Processing PDF: {file.filename} (ID: {document_id})")
            result = await process_pdf_async(pdf_data, file.filename)
            
            # Store document metadata
            await db_client.insert_document(
                document_id=document_id,
                filename=file.filename,
                file_size=result.file_size,
                page_count=result.page_count,
                upload_timestamp=upload_timestamp,
                processing_time_ms=result.processing_time_ms,
                status=result.status,
            )
            
            # Store findings
            for finding in result.findings:
                try:
                    await db_client.insert_finding(
                        document_id=document_id,
                        finding_type=finding.type.value,
                        value=finding.value,
                        page_number=getattr(finding, 'page_number', 1),
                        confidence=finding.confidence,
                        context=finding.context,
                    )
                except Exception as e:
                    # Log error but continue processing other findings
                    logger.error(f"Failed to insert finding: {e}")
            
            # Store metrics if enabled
            if settings.enable_metrics:
                try:
                    # Insert processing time metric
                    await db_client.insert_metric(
                        document_id=document_id,
                        metric_type="processing_time",
                        value=result.processing_time_ms,
                        timestamp=upload_timestamp,
                    )
                    
                    # Insert page count metric
                    await db_client.insert_metric(
                        document_id=document_id,
                        metric_type="page_count",
                        value=float(result.page_count),
                        timestamp=upload_timestamp,
                    )
                    
                    # Insert file size metric
                    await db_client.insert_metric(
                        document_id=document_id,
                        metric_type="file_size",
                        value=float(result.file_size),
                        timestamp=upload_timestamp,
                    )
                except Exception as e:
                    # Log metric insertion error but don't fail the request
                    logger.error(f"Failed to insert metric: {e}")
            
            logger.info(f"Successfully processed {file.filename} with {len(result.findings)} findings")
            
            return {
                "document_id": document_id,
                "filename": file.filename,
                "status": "success",
                "page_count": result.page_count,
                "findings_count": len(result.findings),
                "processing_time_ms": result.processing_time_ms,
                "message": f"PDF processed successfully with {len(result.findings)} findings",
            }
            
        except PDFSizeLimitError as e:
            logger.warning(f"PDF size limit exceeded: {e}")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(e),
            )
            
        except CorruptedPDFError as e:
            logger.warning(f"Corrupted PDF uploaded: {e}")
            
            # Store failed processing attempt
            await db_client.insert_document(
                document_id=document_id,
                filename=file.filename,
                file_size=len(pdf_data),
                page_count=0,
                upload_timestamp=upload_timestamp,
                processing_time_ms=0,
                status="failed",
                error_message=str(e),
            )
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"PDF file is corrupted or unreadable: {str(e)}",
            )
            
        except PDFProcessingError as e:
            logger.error(f"PDF processing failed: {e}")
            
            # Store failed processing attempt
            await db_client.insert_document(
                document_id=document_id,
                filename=file.filename,
                file_size=len(pdf_data),
                page_count=0,
                upload_timestamp=upload_timestamp,
                processing_time_ms=0,
                status="failed",
                error_message=str(e),
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process PDF: {str(e)}",
            )
            
        except Exception as e:
            logger.error(f"Unexpected error processing PDF: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while processing the PDF",
            )
