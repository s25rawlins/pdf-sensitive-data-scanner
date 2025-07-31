# PDF Sensitive Data Scanner

A web application that scans PDF files for sensitive data (emails, SSNs) with automatic redaction capabilities. Built with FastAPI, Next.js, and ClickHouse.

## Overview

The PDF Sensitive Data Scanner provides a secure, high-performance solution for identifying personally identifiable information (PII) in PDF documents. The system uses regex-based pattern matching to detect sensitive data types and stores findings in a ClickHouse database for fast retrieval and analytics.

## Features

- Web-based interface with drag-and-drop PDF upload
- Real-time detection of email addresses and Social Security Numbers
- High-performance data storage using ClickHouse
- RESTful API with comprehensive documentation
- Concurrent upload handling with rate limiting
- Robust error handling for corrupted or oversized files
- Performance metrics tracking and analytics

## Technology Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn
- **Frontend**: Next.js 14, React 18, TypeScript
- **Database**: ClickHouse
- **PDF Processing**: PyPDF2, pdfplumber
- **Containerization**: Docker, Docker Compose
- **Reverse Proxy**: Nginx

## Architecture

The application uses a microservices architecture with three main components:

1. **Frontend Service**: Next.js application serving the user interface
2. **Backend Service**: FastAPI application handling PDF processing and data management
3. **Nginx Service**: Reverse proxy routing traffic between frontend and backend

All services are containerized and orchestrated using Docker Compose.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Docker Deployment (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/pdf-sensitive-data-scanner.git
cd pdf-sensitive-data-scanner

# Create environment file for backend
cp backend/.env.example backend/.env
# Edit backend/.env with your ClickHouse credentials

# Option 1: Use the startup script
./startup-docker.sh

# Option 2: Use docker-compose directly
docker-compose up -d
```

#### Accessing the Application

When running with Docker, the application is accessible at:
- **Main Application**: http://localhost (port 80)
- **Backend API**: http://localhost/api
- **API Documentation**: http://localhost/api/docs
- **Direct Backend Access**: http://localhost:8000 (if needed)
- **Direct Frontend Access**: http://localhost:3000 (if needed)

The nginx reverse proxy handles routing:
- All requests to `/api/*` are forwarded to the backend service
- All other requests are forwarded to the frontend service

#### Managing Docker Services

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Rebuild services after code changes
docker-compose up -d --build
```

### Alternative Deployment Methods

#### Using Startup Scripts

For production deployment without Docker, use the provided startup scripts:

```bash
# Start the application
./startup.sh

# The script will:
# - Check and free required ports (3000, 8000)
# - Create Python virtual environment if needed
# - Install dependencies
# - Build frontend for production
# - Start backend with 4 Uvicorn workers
# - Start frontend Next.js server
# - Display service URLs and health status

# Stop the application gracefully
./shutdown.sh
```

#### Manual Local Development

##### Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload --port 8000
```

##### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.local.example .env.local
# Edit .env.local if needed

# Start development server
npm run dev
```

##### ClickHouse Setup

For local development, you can run ClickHouse using Docker:

```bash
docker run -d \
  --name clickhouse \
  -p 8123:8123 \
  -p 9000:9000 \
  -e CLICKHOUSE_DB=pdf_scanner \
  -e CLICKHOUSE_USER=default \
  -e CLICKHOUSE_PASSWORD=your_password \
  clickhouse/clickhouse-server
```

## API Documentation

### Endpoints

#### Upload PDF
- **POST** `/api/upload`
- Accepts PDF file via multipart/form-data
- Returns document ID and processing status
- Maximum file size: 50MB

Example response:
```json
{
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "filename": "document.pdf",
  "status": "completed",
  "findings_count": 5,
  "processing_time": 1.23
}
```

#### Get All Findings
- **GET** `/api/findings`
- Query parameters:
  - `page`: Page number (default: 1)
  - `page_size`: Results per page (default: 20, max: 100)
  - `doc_id`: Filter by document ID
  - `finding_type`: Filter by type (email, ssn)

Example response:
```json
{
  "findings": [
    {
      "finding_id": "456e7890-e89b-12d3-a456-426614174000",
      "document_id": "123e4567-e89b-12d3-a456-426614174000",
      "finding_type": "email",
      "value": "user@example.com",
      "page_number": 1,
      "confidence": 1.0,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

#### Get Document Findings
- **GET** `/api/findings/{document_id}`
- Returns all findings for a specific document

#### Health Check
- **GET** `/api/health`
- Returns service health status including database connectivity

## Configuration

### Environment Variables

#### Backend (.env)
```
# ClickHouse Configuration
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_password
CLICKHOUSE_DATABASE=pdf_scanner

# Application Settings
MAX_FILE_SIZE_MB=50
MAX_CONCURRENT_UPLOADS=10
ENV=production
```

#### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## Testing

The project includes comprehensive test coverage:

```bash
# Run all backend tests
cd backend
pytest

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_detector.py -v

# Run frontend tests
cd frontend
npm test
```

## Performance Characteristics

- Typical PDF processing time: < 2 seconds for documents under 10MB
- Concurrent upload support: Up to 10 simultaneous uploads
- P95 latency: < 3 seconds for standard documents
- Database query performance: < 100ms for finding retrieval

## Security Considerations

- File validation: Extension, size, and content verification
- Path traversal protection: Filename sanitization
- Rate limiting: Concurrent upload restrictions
- No persistent file storage: PDFs processed in memory only
- CORS configuration: Restricted to allowed origins
- Input validation: All user inputs sanitized

## Project Structure

```
pdf-sensitive-data-scanner/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Core business logic
│   │   ├── db/           # Database models and client
│   │   ├── services/     # Service layer
│   │   └── utils/        # Utility functions
│   ├── tests/            # Test suite
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── app/              # Next.js app directory
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom React hooks
│   │   ├── services/     # API client services
│   │   └── types/        # TypeScript definitions
│   └── package.json      # Node dependencies
├── docker-compose.yml    # Docker orchestration
├── nginx.conf           # Nginx configuration
└── README.md            # This file
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: If ports 80, 3000, or 8000 are in use, stop conflicting services or modify the port configuration in docker-compose.yml

2. **ClickHouse connection errors**: Verify your ClickHouse credentials in backend/.env and ensure the database service is running

3. **PDF processing failures**: Check that the PDF is not corrupted and is under the 50MB size limit

4. **Docker build failures**: Ensure Docker daemon is running and you have sufficient disk space

### Logs

View service logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```