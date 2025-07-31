# PDF Sensitive Data Scanner - Backend Architecture Walkthrough

## Table of Contents
1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Design Principles & Decisions](#design-principles--decisions)
4. [Core Components](#core-components)
5. [Data Flow](#data-flow)
6. [Implementation Details](#implementation-details)
7. [Trade-offs & Considerations](#trade-offs--considerations)

## Overview

The PDF Sensitive Data Scanner backend is a FastAPI-based microservice designed to process PDF documents and detect sensitive information (PII) such as email addresses and Social Security Numbers (SSNs). The system emphasizes scalability, reliability, and performance while maintaining clean architecture principles.

### Key Features
- Asynchronous PDF processing with concurrent upload limiting
- Regex-based sensitive data detection with confidence scoring
- ClickHouse database for high-performance data storage and analytics
- Comprehensive validation and error handling
- RESTful API with automatic documentation
- Modular architecture with clear separation of concerns

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client (Frontend)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP/HTTPS
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Application                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          Middleware Layer                            │   │
│  │  • CORS Middleware                                                  │   │
│  │  • Trusted Host Middleware                                          │   │
│  │  • Request/Response Logging                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                        │                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           API Endpoints                              │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │   │
│  │  │  Upload Router  │    │ Findings Router │    │  Health Check   │ │   │
│  │  │   /api/upload   │    │  /api/findings  │    │    /health      │ │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                        │                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          Service Layer                               │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │   │
│  │  │  PDF Processor  │    │    Detector     │    │   Validators    │ │   │
│  │  │                 │◄───│                 │    │                 │ │   │
│  │  │ • Text Extract  │    │ • Email Regex  │    │ • File Valid    │ │   │
│  │  │ • Page Parse    │    │ • SSN Regex    │    │ • Size Check    │ │   │
│  │  │ • Error Handle  │    │ • Confidence   │    │ • Type Check    │ │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                        │                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Database Layer                               │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │   │
│  │  │ClickHouse Client│    │     Models      │    │   Migrations    │ │   │
│  │  │                 │◄───│                 │    │                 │ │   │
│  │  │ • Async Ops     │    │ • Documents    │    │ • Table Create  │ │   │
│  │  │ • Connection    │    │ • Findings     │    │ • Index Setup   │ │   │
│  │  │ • Query Builder │    │ • Metrics      │    │ • TTL Config    │ │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ TCP/Native Protocol
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ClickHouse Database                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   Documents     │    │    Findings     │    │     Metrics     │        │
│  │                 │    │                 │    │                 │        │
│  │ • document_id   │    │ • finding_id    │    │ • metric_id     │        │
│  │ • filename      │    │ • document_id   │    │ • document_id   │        │
│  │ • file_size     │    │ • finding_type  │    │ • metric_type   │        │
│  │ • page_count    │    │ • value         │    │ • value         │        │
│  │ • status        │    │ • confidence    │    │ • timestamp     │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Design Principles & Decisions

### 1. **Asynchronous Architecture**
- **Decision**: Use FastAPI with async/await throughout
- **Rationale**: 
  - Non-blocking I/O for database operations
  - Better resource utilization for concurrent requests
  - Natural fit for PDF processing workloads
- **Implementation**: All database operations, file I/O, and CPU-intensive tasks run in thread pools

### 2. **Layered Architecture**
- **Decision**: Strict separation between API, Service, and Data layers
- **Rationale**:
  - Maintainability and testability
  - Clear boundaries and responsibilities
  - Easy to mock dependencies for testing
- **Implementation**: 
  - API layer handles HTTP concerns
  - Service layer contains business logic
  - Data layer manages persistence

### 3. **ClickHouse for Analytics**
- **Decision**: Use ClickHouse instead of traditional RDBMS
- **Rationale**:
  - Optimized for analytical queries (finding statistics)
  - Excellent compression for large datasets
  - Fast aggregations and time-series queries
- **Trade-off**: More complex setup vs. superior query performance

### 4. **Regex-based Detection**
- **Decision**: Use compiled regex patterns for PII detection
- **Rationale**:
  - Fast and predictable performance
  - No external dependencies or API calls
  - Easy to extend with new patterns
- **Trade-off**: Less sophisticated than ML models but more reliable

## Core Components

### 1. **Main Application (main.py)**
```python
# Key responsibilities:
- FastAPI app initialization
- Middleware configuration
- Router registration
- Lifecycle management (startup/shutdown)
- Global database client management
```

**Design Decisions:**
- Uses lifespan context manager for clean startup/shutdown
- Global database client for connection pooling
- Comprehensive health checks including database status

### 2. **Configuration Management (core/config.py)**
```python
# Key features:
- Environment variable support via Pydantic Settings
- Type-safe configuration
- Validation on startup
- Cached singleton pattern
```

**Design Decisions:**
- All settings centralized in one place
- Validation prevents runtime configuration errors
- LRU cache prevents repeated file reads

### 3. **PDF Processing Service (services/pdf_processor.py)**
```python
# Processing pipeline:
1. File size validation
2. PDF signature verification
3. Text extraction (dual-method approach)
4. Page-by-page processing
5. Sensitive data detection
6. Result aggregation
```

**Key Design Decisions:**
- **Dual extraction methods**: Uses both pdfplumber (better for complex layouts) and pypdf (fallback)
- **Page-level tracking**: Each finding includes page number for precise location
- **Memory efficiency**: Processes pages sequentially to avoid loading entire PDF
- **Error recovery**: Graceful degradation when individual pages fail

### 4. **Sensitive Data Detector (core/detector.py)**
```python
# Detection strategy:
1. Compiled regex patterns for performance
2. Context-aware confidence scoring
3. Validation to reduce false positives
4. Extensible pattern system
```

**Email Detection:**
- RFC 5322 simplified pattern
- Always 100% confidence (clear pattern match)

**SSN Detection:**
- Multiple format support (dashed, continuous, spaced)
- Context-based confidence (0.8-1.0)
- Invalid SSN filtering (000, 666, 900-999 prefixes)
- Keyword proximity checking

### 5. **Database Client (db/clickhouse.py)**
```python
# Architecture:
- Dual-driver support (cloud vs native)
- Async wrapper over sync drivers
- Automatic table creation
- Connection pooling
```

**Design Decisions:**
- **Driver abstraction**: Supports both ClickHouse Cloud and self-hosted
- **Async execution**: Runs sync operations in thread pool
- **Schema management**: Tables created on startup
- **TTL for metrics**: Automatic data cleanup after 30 days

### 6. **API Endpoints**

#### Upload Endpoint (api/endpoints/upload.py)
```python
# Flow:
1. File validation (extension, size, content)
2. Concurrent upload limiting (semaphore)
3. Async PDF processing
4. Database persistence
5. Response generation
```

**Key Features:**
- Semaphore-based concurrency control
- Comprehensive error handling with status tracking
- Failed uploads recorded for debugging

#### Findings Endpoint (api/endpoints/findings.py)
```python
# Features:
- Paginated results
- Multiple filter options
- Summary statistics
- Document-specific queries
```

**Design Decisions:**
- Response models for type safety
- Efficient aggregation queries
- Flexible filtering system

## Data Flow

### Upload Flow
```
1. Client uploads PDF file
   ↓
2. FastAPI validates file (extension, size, magic bytes)
   ↓
3. Acquire upload semaphore (concurrency control)
   ↓
4. Generate unique document ID (UUID)
   ↓
5. Process PDF in thread pool:
   a. Extract text from each page
   b. Detect sensitive data per page
   c. Calculate confidence scores
   ↓
6. Store in ClickHouse:
   a. Document metadata
   b. Individual findings
   c. Performance metrics
   ↓
7. Return response with document ID and summary
```

### Query Flow
```
1. Client requests findings (with optional filters)
   ↓
2. Validate pagination and filter parameters
   ↓
3. Build optimized ClickHouse query
   ↓
4. Execute async database query
   ↓
5. Transform results to response models
   ↓
6. Calculate summary statistics
   ↓
7. Return paginated response
```

## Implementation Details

### 1. **Concurrency Control**
```python
upload_semaphore = asyncio.Semaphore(settings.max_concurrent_uploads)
```
- Prevents system overload
- Configurable limit (default: 10)
- Fair queuing for uploads

### 2. **Error Handling Strategy**
```python
# Hierarchical exception handling:
PDFProcessingError (base)
├── CorruptedPDFError (422 response)
├── PDFSizeLimitError (413 response)
└── General errors (500 response)
```

### 3. **Database Schema**
```sql
-- Documents table (MergeTree engine)
- Optimized for time-series queries
- Indexed by upload_timestamp and document_id

-- Findings table (MergeTree engine)
- Optimized for document-based queries
- Indexed by document_id and finding_type

-- Metrics table (MergeTree with TTL)
- Automatic cleanup after 30 days
- Optimized for aggregations
```

### 4. **Validation Pipeline**
```python
# Multi-stage validation:
1. File extension check
2. File size validation
3. PDF signature verification
4. Content integrity check (%%EOF marker)
5. Filename sanitization
```

### 5. **Performance Optimizations**
- **Compiled regex patterns**: Initialized once, reused for all detections
- **Thread pool execution**: CPU-intensive tasks don't block event loop
- **Streaming processing**: Pages processed sequentially, not all at once
- **Database batching**: Multiple findings inserted in single query
- **Connection pooling**: Reused database connections

## Trade-offs & Considerations

### 1. **Regex vs. ML for Detection**
**Choice**: Regex patterns
- ✅ Predictable performance
- ✅ No external dependencies
- ✅ Easy to understand and debug
- ❌ Less sophisticated detection
- ❌ May miss obfuscated data

### 2. **ClickHouse vs. PostgreSQL**
**Choice**: ClickHouse
- ✅ Superior analytical query performance
- ✅ Built-in data compression
- ✅ Excellent for time-series data
- ❌ More complex setup
- ❌ Limited transaction support

### 3. **Async vs. Sync Processing**
**Choice**: Async with thread pool for CPU tasks
- ✅ Better resource utilization
- ✅ Non-blocking I/O
- ✅ Natural fit for web services
- ❌ More complex error handling
- ❌ Debugging can be challenging

### 4. **File Processing Approach**
**Choice**: In-memory processing
- ✅ Fast processing
- ✅ No disk I/O overhead
- ❌ Memory constraints for large files
- ❌ No resume capability for failures

### 5. **Security Considerations**
- **File validation**: Multiple checks prevent malicious uploads
- **Path traversal**: Filename sanitization prevents directory attacks
- **Size limits**: Prevents DoS through large file uploads
- **CORS configuration**: Restricts API access to allowed origins
- **No file persistence**: Processed files not stored on disk

## Future Enhancements

1. **Enhanced Detection**
   - Add more PII types (phone numbers, addresses)
   - Implement ML-based detection for complex patterns
   - Support for international formats

2. **Performance Improvements**
   - Implement caching for frequently accessed data
   - Add Redis for session management
   - Optimize PDF processing with GPU acceleration

3. **Scalability**
   - Kubernetes deployment configurations
   - Horizontal scaling with message queues
   - Distributed processing with Celery

4. **Monitoring & Observability**
   - Prometheus metrics integration
   - Distributed tracing with OpenTelemetry
   - Enhanced logging with correlation IDs

5. **Additional Features**
   - Batch upload support
   - Real-time processing status via WebSockets
   - PDF redaction service
   - Export functionality for findings

## Conclusion

The PDF Sensitive Data Scanner backend demonstrates a well-architected system that balances performance, reliability, and maintainability. The modular design allows for easy extension and modification, while the async architecture ensures efficient resource utilization. The choice of ClickHouse for analytics provides excellent query performance for finding analysis and reporting.

The system successfully addresses the core requirements of PDF processing and sensitive data detection while maintaining clean code principles and comprehensive error handling. The architecture is production-ready and can scale to handle significant workloads with minimal modifications.
