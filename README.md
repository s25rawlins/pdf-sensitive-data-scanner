# PDF Sensitive Data Scanner

A web application that scans PDF files for sensitive data (emails, SSNs) with automatic redaction capabilities. Built with FastAPI, React, and ClickHouse.

## Features

- Single-page web interface for PDF uploads
- Detects email addresses and Social Security Numbers using hybrid regex/AI approach
- Stores findings in ClickHouse for fast retrieval
- RESTful API with `/findings` endpoint
- Supports PDF redaction (bonus feature)
- Handles corrupted/oversized files gracefully
- Performance metrics tracking

## Technology Stack

- **Backend**: Python 3.10+, FastAPI
- **Frontend**: React 18
- **Database**: ClickHouse
- **PDF Processing**: PyPDF2, pdfplumber, spaCy
- **Deployment**: Docker, Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+ (for local development)
- Node.js 18+ (for local development)

### Running with Docker

```bash
# Clone the repository
git clone https://github.com/yourusername/pdf-sensitive-data-scanner.git
cd pdf-sensitive-data-scanner

# Start all services
docker-compose up -d

# Application will be available at http://localhost:3000
```

### Running with Startup Scripts

The project includes convenient startup and shutdown scripts for production deployment:

```bash
# Start the application
./startup.sh

# The script will:
# - Check and free required ports (3000, 8000)
# - Build the frontend for production
# - Start backend with 4 Uvicorn workers
# - Start frontend Next.js server
# - Display service URLs and status

# Stop the application gracefully
./shutdown.sh

# The shutdown script will:
# - Send SIGTERM for graceful shutdown
# - Wait for processes to terminate
# - Force kill if necessary
# - Verify ports are freed
```

### Local Development

#### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup

```bash
cd frontend
npm install
npm start
```

#### ClickHouse Setup

```bash
# Using Docker for ClickHouse
docker run -d \
  --name clickhouse \
  -p 8123:8123 \
  -p 9000:9000 \
  clickhouse/clickhouse-server
```

## API Documentation

### Upload PDF
- **POST** `/api/upload`
- Accepts PDF file via multipart/form-data
- Returns document ID and processing status

### Get Findings
- **GET** `/api/findings`
- Returns all document findings in JSON format
- Supports filtering by document ID: `/api/findings?doc_id=123`

### Get Specific Document
- **GET** `/api/findings/{document_id}`
- Returns findings for a specific document

## Architecture

The application follows a modular architecture:

1. **Frontend**: React SPA with drag-and-drop file upload
2. **API Layer**: FastAPI handling HTTP requests
3. **Processing Layer**: PDF text extraction and sensitive data detection
4. **Data Layer**: ClickHouse for storing findings

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
pytest backend/tests/test_detector.py
```

## Performance

- Processes typical PDFs (< 10MB) in under 2 seconds
- Supports concurrent uploads
- P95 latency: < 3 seconds for standard documents

## Security Considerations

- File size limits: 50MB max
- File type validation (PDF only)
- No sensitive data stored in logs
- Redacted PDFs use industry-standard techniques
