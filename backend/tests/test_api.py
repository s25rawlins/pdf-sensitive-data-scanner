"""
API endpoint tests for the PDF scanner application.

Tests cover upload functionality, findings retrieval, and error handling
for the FastAPI endpoints.
"""

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.main import app


class TestAPIEndpoints:
    """Test suite for API endpoints."""
    
    
    @pytest.fixture
    def valid_pdf_bytes(self) -> bytes:
        """Create a valid PDF for testing."""
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
        pdf_canvas.drawString(100, 750, "Test PDF Document")
        pdf_canvas.drawString(100, 700, "Email: test@example.com")
        pdf_canvas.drawString(100, 650, "SSN: 123-45-6789")
        pdf_canvas.save()
        buffer.seek(0)
        return buffer.read()
    
    @pytest.fixture
    def invalid_pdf_bytes(self) -> bytes:
        """Create invalid PDF data."""
        return b"This is not a valid PDF file"
    
    def test_health_check(self, test_client: TestClient):
        """Test root health check endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_api_health_check(self, test_client: TestClient):
        """Test detailed API health check."""
        with patch("app.main.db_client") as mock_db:
            mock_db.health_check = AsyncMock(return_value=True)
            
            response = test_client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_upload_valid_pdf(self, test_client: TestClient, valid_pdf_bytes: bytes):
        """Test uploading a valid PDF file."""
        with patch("app.api.endpoints.upload.get_db_client") as mock_get_db:
            # Mock database client
            mock_db = AsyncMock()
            mock_db.insert_document = AsyncMock()
            mock_db.insert_finding = AsyncMock()
            mock_db.insert_metric = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # Create file upload
            files = {"file": ("test.pdf", valid_pdf_bytes, "application/pdf")}
            
            response = test_client.post("/api/upload", files=files)
            
            assert response.status_code == 201
            data = response.json()
            
            assert "document_id" in data
            assert data["filename"] == "test.pdf"
            assert data["status"] == "success"
            assert data["findings_count"] == 2  # 1 email + 1 SSN
            assert data["page_count"] == 1
    
    def test_upload_invalid_file_type(self, test_client: TestClient):
        """Test uploading non-PDF file."""
        files = {"file": ("test.txt", b"Not a PDF", "text/plain")}
        
        response = test_client.post("/api/upload", files=files)
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]
    
    def test_upload_oversized_file(self, test_client: TestClient):
        """Test uploading file exceeding size limit."""
        # Create large content
        large_content = b"PDF" + b"x" * (51 * 1024 * 1024)  # 51MB
        files = {"file": ("large.pdf", large_content, "application/pdf")}
        
        response = test_client.post("/api/upload", files=files)
        
        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"]
    
    def test_upload_corrupted_pdf(self, test_client: TestClient, invalid_pdf_bytes: bytes):
        """Test uploading corrupted PDF."""
        with patch("app.api.endpoints.upload.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.insert_document = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # Add PDF header to make it pass initial validation
            corrupted_pdf = b"%PDF-1.4\n" + invalid_pdf_bytes + b"\n%%EOF"
            files = {"file": ("corrupted.pdf", corrupted_pdf, "application/pdf")}
            
            response = test_client.post("/api/upload", files=files)
            
            assert response.status_code == 422
            assert "corrupted" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_all_findings(self, test_client: TestClient):
        """Test retrieving all findings."""
        with patch("app.api.endpoints.findings.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            
            # Mock data
            mock_documents = [{
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "test.pdf",
                "file_size": 1024,
                "page_count": 2,
                "upload_timestamp": datetime.now(timezone.utc),
                "processing_time_ms": 150.5,
                "status": "success",
                "error_message": None,
            }]
            
            mock_findings = [{
                "finding_id": "456e7890-e89b-12d3-a456-426614174000",
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "finding_type": "email",
                "value": "test@example.com",
                "page_number": 1,
                "confidence": 1.0,
                "context": "Email: test@example.com",
                "detected_at": datetime.now(timezone.utc),
            }]
            
            mock_db.count_documents = AsyncMock(return_value=1)
            mock_db.get_documents = AsyncMock(return_value=mock_documents)
            mock_db.get_findings_by_document = AsyncMock(return_value=mock_findings)
            mock_get_db.return_value = mock_db
            
            response = test_client.get("/api/findings")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["page_size"] == 20
            assert len(data["findings"]) == 1
            assert data["findings"][0]["document_id"] == "123e4567-e89b-12d3-a456-426614174000"
    
    @pytest.mark.asyncio
    async def test_get_findings_with_filters(self, test_client: TestClient):
        """Test retrieving findings with filters."""
        with patch("app.api.endpoints.findings.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.count_documents = AsyncMock(return_value=0)
            mock_db.get_documents = AsyncMock(return_value=[])
            mock_get_db.return_value = mock_db
            
            # Test with filters
            response = test_client.get(
                "/api/findings",
                params={
                    "finding_type": "email",
                    "page": 1,
                    "page_size": 10,
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["page"] == 1
            assert data["page_size"] == 10
    
    @pytest.mark.asyncio
    async def test_get_document_findings(self, test_client: TestClient):
        """Test retrieving findings for specific document."""
        document_id = "123e4567-e89b-12d3-a456-426614174000"
        
        with patch("app.api.endpoints.findings.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            
            mock_document = {
                "document_id": document_id,
                "filename": "test.pdf",
                "file_size": 1024,
                "page_count": 1,
                "upload_timestamp": datetime.now(timezone.utc),
                "processing_time_ms": 100.0,
                "status": "success",
                "error_message": None,
            }
            
            mock_findings = [
                {
                    "finding_id": "456e7890-e89b-12d3-a456-426614174000",
                    "document_id": document_id,
                    "finding_type": "email",
                    "value": "test@example.com",
                    "page_number": 1,
                    "confidence": 1.0,
                    "context": "Email: test@example.com",
                    "detected_at": datetime.now(timezone.utc),
                },
                {
                    "finding_id": "789e0123-e89b-12d3-a456-426614174000",
                    "document_id": document_id,
                    "finding_type": "ssn",
                    "value": "123-45-6789",
                    "page_number": 1,
                    "confidence": 0.95,
                    "context": "SSN: 123-45-6789",
                    "detected_at": datetime.now(timezone.utc),
                }
            ]
            
            mock_db.get_document = AsyncMock(return_value=mock_document)
            mock_db.get_findings_by_document = AsyncMock(return_value=mock_findings)
            mock_get_db.return_value = mock_db
            
            response = test_client.get(f"/api/findings/{document_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["document_id"] == document_id
            assert data["filename"] == "test.pdf"
            assert len(data["findings"]) == 2
            assert data["summary"]["total"] == 2
            assert data["summary"]["email"] == 1
            assert data["summary"]["ssn"] == 1
    
    def test_get_nonexistent_document(self, test_client: TestClient):
        """Test retrieving findings for non-existent document."""
        with patch("app.api.endpoints.findings.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.get_document = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db
            
            response = test_client.get("/api/findings/nonexistent-id")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_summary_statistics(self, test_client: TestClient):
        """Test retrieving summary statistics."""
        with patch("app.api.endpoints.findings.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            
            mock_stats = {
                "total_documents": 100,
                "total_findings": 250,
                "findings_by_type": {"email": 150, "ssn": 100},
                "avg_processing_time": 125.5,
                "total_pages": 500,
                "documents_with_findings": 80,
            }
            
            mock_db.get_summary_statistics = AsyncMock(return_value=mock_stats)
            mock_get_db.return_value = mock_db
            
            response = test_client.get("/api/findings/stats/summary")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["total_documents"] == 100
            assert data["total_findings"] == 250
            assert data["findings_by_type"]["email"] == 150
            assert data["findings_by_type"]["ssn"] == 100
            assert data["average_processing_time_ms"] == 125.5
    
    def test_upload_no_file(self, test_client: TestClient):
        """Test upload endpoint without file."""
        response = test_client.post("/api/upload")
        
        assert response.status_code == 422
        assert "field required" in str(response.json()["detail"]).lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, test_client: TestClient, valid_pdf_bytes: bytes):
        """Test handling concurrent uploads."""
        with patch("app.api.endpoints.upload.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.insert_document = AsyncMock()
            mock_db.insert_finding = AsyncMock()
            mock_db.insert_metric = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # Simulate multiple uploads
            files1 = {"file": ("test1.pdf", valid_pdf_bytes, "application/pdf")}
            files2 = {"file": ("test2.pdf", valid_pdf_bytes, "application/pdf")}
            
            response1 = test_client.post("/api/upload", files=files1)
            response2 = test_client.post("/api/upload", files=files2)
            
            assert response1.status_code == 201
            assert response2.status_code == 201
            
            # Ensure different document IDs
            assert response1.json()["document_id"] != response2.json()["document_id"]
    
    def test_pagination_parameters(self, test_client: TestClient):
        """Test pagination parameter validation."""
        with patch("app.api.endpoints.findings.get_db_client") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.count_documents = AsyncMock(return_value=0)
            mock_db.get_documents = AsyncMock(return_value=[])
            mock_get_db.return_value = mock_db
            
            # Test invalid page number
            response = test_client.get("/api/findings?page=0")
            assert response.status_code == 422
            
            # Test invalid page size
            response = test_client.get("/api/findings?page_size=200")
            assert response.status_code == 422
            
            # Test valid parameters
            response = test_client.get("/api/findings?page=2&page_size=50")
            assert response.status_code == 200


@pytest.mark.integration
class TestIntegrationAPI:
    """Integration tests requiring actual services."""
    
    
    @pytest.mark.skipif(
        not Path(".env").exists(),
        reason="Integration tests require .env configuration"
    )
    def test_real_pdf_upload(self, test_client: TestClient):
        """Test with real PDF upload and ClickHouse."""
        # This would test with actual ClickHouse connection
        pass
