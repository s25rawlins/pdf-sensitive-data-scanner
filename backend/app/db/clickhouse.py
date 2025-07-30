"""
ClickHouse database client and operations.

This module provides async database operations for storing and retrieving
PDF processing results and findings in ClickHouse Cloud.
"""

import asyncio
import logging
import ssl
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global client instance
_db_client: Optional["ClickHouseClient"] = None


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class ClickHouseClient:
    """
    Async wrapper for ClickHouse database operations.
    
    Supports both ClickHouse Cloud (via clickhouse-connect) and 
    standard ClickHouse (via clickhouse-driver) connections.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str = "",
        secure: bool = True,
        verify: bool = True,
        use_cloud_driver: bool = None,
    ):
        """
        Initialize ClickHouse client.
        
        Args:
            host: ClickHouse host.
            port: ClickHouse port.
            database: Database name.
            user: Username.
            password: Password.
            secure: Use secure connection.
            verify: Verify SSL certificates.
            use_cloud_driver: Force use of cloud driver (auto-detected if None).
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.secure = secure
        self.verify = verify
        
        # Auto-detect cloud driver usage based on port and security
        if use_cloud_driver is None:
            self.use_cloud_driver = (port == 8443 or port == 8123) and secure
        else:
            self.use_cloud_driver = use_cloud_driver
            
        self._client: Optional[Any] = None
        self._initialized = False
        
        logger.info(f"Using {'cloud' if self.use_cloud_driver else 'native'} driver for ClickHouse connection")
    
    def _create_cloud_client(self):
        """Create ClickHouse Cloud client using clickhouse-connect."""
        try:
            import clickhouse_connect
            
            # ClickHouse Cloud connection parameters
            client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.database,
                secure=self.secure,
                verify=self.verify,
                compress=False,  # Disable compression to avoid issues
            )
            
            return client
            
        except ImportError:
            raise DatabaseError("clickhouse-connect is required for ClickHouse Cloud connections")
    
    def _create_native_client(self):
        """Create native ClickHouse client using clickhouse-driver."""
        try:
            from clickhouse_driver import Client
            from clickhouse_driver.errors import Error as ClickHouseError
            
            # Native driver connection parameters
            settings_dict = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'database': self.database,
                'secure': self.secure,
                'verify': self.verify,
                'compression': False,
                'connect_timeout': 10,
                'send_receive_timeout': 300,
                'sync_request_timeout': 5,
            }
            
            if self.secure:
                settings_dict['ca_certs'] = None
                settings_dict['verify'] = self.verify
            
            return Client(**settings_dict)
            
        except ImportError:
            raise DatabaseError("clickhouse-driver is required for native ClickHouse connections")
    
    def _execute_query(self, query: str, params: Any = None) -> Any:
        """Execute a query using the appropriate driver."""
        if self.use_cloud_driver:
            # clickhouse-connect uses different methods for different query types
            if query.strip().upper().startswith(('INSERT', 'CREATE', 'DROP', 'ALTER', 'DELETE', 'UPDATE')):
                return self._client.command(query, parameters=params)
            else:
                result = self._client.query(query, parameters=params)
                return result.result_rows if hasattr(result, 'result_rows') else result
        else:
            # clickhouse-driver
            return self._client.execute(query, params)
    
    def _initialize_sync(self) -> None:
        """Synchronous initialization of database connection and tables."""
        # Create client with appropriate driver
        if self.use_cloud_driver:
            self._client = self._create_cloud_client()
        else:
            self._client = self._create_native_client()
        
        # Test connection
        try:
            result = self._execute_query("SELECT 1")
            logger.info(f"ClickHouse connection test successful: {result}")
        except Exception as e:
            logger.error(f"ClickHouse connection test failed: {e}")
            raise
        
        # Create database if it doesn't exist
        try:
            self._execute_query(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            logger.info(f"Database {self.database} ready")
        except Exception as e:
            logger.warning(f"Could not create database (might already exist): {e}")
        
        # Switch to our database
        self._execute_query(f"USE {self.database}") 
        
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Create required database tables with ClickHouse Cloud compatible schemas."""
        logger.info("Creating database tables...")
        
        # Documents table
        try:
            self._execute_query("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id UUID,
                    filename String,
                    file_size UInt64,
                    page_count UInt32,
                    upload_timestamp DateTime('UTC'),
                    processing_time_ms Float32,
                    status String,
                    error_message Nullable(String),
                    created_at DateTime('UTC') DEFAULT now()
                ) ENGINE = MergeTree()
                ORDER BY (upload_timestamp, document_id)
                SETTINGS index_granularity = 8192
            """)
            logger.info("Documents table created/verified")
        except Exception as e:
            logger.error(f"Error creating documents table: {e}")
            raise
        
        # Findings table
        try:
            self._execute_query("""
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id UUID DEFAULT generateUUIDv4(),
                    document_id UUID,
                    finding_type String,
                    value String,
                    page_number UInt32,
                    confidence Float32,
                    context Nullable(String),
                    detected_at DateTime('UTC') DEFAULT now()
                ) ENGINE = MergeTree()
                ORDER BY (document_id, finding_type, detected_at)
                SETTINGS index_granularity = 8192
            """)
            logger.info("Findings table created/verified")
        except Exception as e:
            logger.error(f"Error creating findings table: {e}")
            raise
        
        # Metrics table with TTL for automatic cleanup
        try:
            self._execute_query("""
                CREATE TABLE IF NOT EXISTS metrics (
                    metric_id UUID DEFAULT generateUUIDv4(),
                    document_id UUID,
                    metric_type String,
                    value Float64,
                    timestamp DateTime('UTC'),
                    created_at DateTime('UTC') DEFAULT now()
                ) ENGINE = MergeTree()
                ORDER BY (timestamp, metric_type)
                TTL created_at + INTERVAL 30 DAY
                SETTINGS index_granularity = 8192
            """)
            logger.info("Metrics table created/verified")
        except Exception as e:
            logger.error(f"Error creating metrics table: {e}")
            raise
    
    async def initialize(self) -> None:
        """
        Initialize database connection and create tables if needed.
        
        Raises:
            DatabaseError: If initialization fails.
        """
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._initialize_sync)
            self._initialized = True
            logger.info("ClickHouse client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ClickHouse: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    async def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            True if healthy, False otherwise.
        """
        if not self._initialized or not self._client:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_query,
                "SELECT 1"
            )
            return len(result) > 0 if result else True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connection and return diagnostic information.
        
        Returns:
            Dictionary with connection test results.
        """
        try:
            loop = asyncio.get_event_loop()
            
            # Test basic connectivity
            version = await loop.run_in_executor(
                None,
                self._execute_query,
                "SELECT version()"
            )
            
            # Check database
            current_db = await loop.run_in_executor(
                None,
                self._execute_query,
                "SELECT currentDatabase()"
            )
            
            # List tables
            tables = await loop.run_in_executor(
                None,
                self._execute_query,
                "SHOW TABLES"
            )
            
            return {
                "status": "connected",
                "version": version[0][0] if version else "unknown",
                "database": current_db[0][0] if current_db else "unknown",
                "tables": [t[0] for t in tables] if tables else [],
                "host": self.host,
                "port": self.port,
                "secure": self.secure,
                "driver": "cloud" if self.use_cloud_driver else "native",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "host": self.host,
                "port": self.port,
                "driver": "cloud" if self.use_cloud_driver else "native",
            }
    
    async def insert_document(
        self,
        document_id: str,
        filename: str,
        file_size: int,
        page_count: int,
        upload_timestamp: datetime,
        processing_time_ms: float,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Insert document metadata into database.
        
        Args:
            document_id: Unique document identifier.
            filename: Original filename.
            file_size: File size in bytes.
            page_count: Number of pages.
            upload_timestamp: Upload time.
            processing_time_ms: Processing duration.
            status: Processing status.
            error_message: Optional error message.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        try:
            loop = asyncio.get_event_loop()
            
            if self.use_cloud_driver:
                # clickhouse-connect style
                await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    INSERT INTO documents (
                        document_id, filename, file_size, page_count,
                        upload_timestamp, processing_time_ms, status, error_message
                    ) VALUES ({document_id:UUID}, {filename:String}, {file_size:UInt64}, 
                             {page_count:UInt32}, {upload_timestamp:DateTime}, 
                             {processing_time_ms:Float32}, {status:String}, {error_message:Nullable(String)})
                    """,
                    {
                        "document_id": document_id,
                        "filename": filename,
                        "file_size": file_size,
                        "page_count": page_count,
                        "upload_timestamp": upload_timestamp,
                        "processing_time_ms": processing_time_ms,
                        "status": status,
                        "error_message": error_message,
                    }
                )
            else:
                # clickhouse-driver style
                await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    INSERT INTO documents (
                        document_id, filename, file_size, page_count,
                        upload_timestamp, processing_time_ms, status, error_message
                    ) VALUES
                    """,
                    [(
                        document_id, filename, file_size, page_count,
                        upload_timestamp, processing_time_ms, status, error_message
                    )]
                )
            
            logger.debug(f"Inserted document {document_id}")
        except Exception as e:
            logger.error(f"Failed to insert document: {e}")
            raise DatabaseError(f"Failed to insert document: {e}")
    
    async def insert_finding(
        self,
        document_id: str,
        finding_type: str,
        value: str,
        page_number: int,
        confidence: float,
        context: Optional[str] = None,
    ) -> None:
        """
        Insert finding into database.
        
        Args:
            document_id: Associated document ID.
            finding_type: Type of finding (email, ssn).
            value: Detected value.
            page_number: Page number.
            confidence: Confidence score.
            context: Optional surrounding context.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        try:
            loop = asyncio.get_event_loop()
            
            if self.use_cloud_driver:
                # clickhouse-connect style
                await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    INSERT INTO findings (
                        document_id, finding_type, value,
                        page_number, confidence, context
                    ) VALUES ({document_id:UUID}, {finding_type:String}, {value:String},
                             {page_number:UInt32}, {confidence:Float32}, {context:Nullable(String)})
                    """,
                    {
                        "document_id": document_id,
                        "finding_type": finding_type,
                        "value": value,
                        "page_number": page_number,
                        "confidence": confidence,
                        "context": context,
                    }
                )
            else:
                # clickhouse-driver style
                await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    INSERT INTO findings (
                        document_id, finding_type, value,
                        page_number, confidence, context
                    ) VALUES
                    """,
                    [(
                        document_id, finding_type, value,
                        page_number, confidence, context
                    )]
                )
            
            logger.debug(f"Inserted finding for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to insert finding: {e}")
            raise DatabaseError(f"Failed to insert finding: {e}")
    
    async def insert_metric(
        self,
        document_id: str,
        metric_type: str,
        value: float,
        timestamp: datetime,
    ) -> None:
        """
        Insert performance metric.
        
        Args:
            document_id: Associated document ID.
            metric_type: Type of metric.
            value: Metric value.
            timestamp: Metric timestamp.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        try:
            loop = asyncio.get_event_loop()
            
            if self.use_cloud_driver:
                # clickhouse-connect style
                await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    INSERT INTO metrics (
                        document_id, metric_type, value, timestamp
                    ) VALUES ({document_id:UUID}, {metric_type:String}, 
                             {value:Float64}, {timestamp:DateTime})
                    """,
                    {
                        "document_id": document_id,
                        "metric_type": metric_type,
                        "value": value,
                        "timestamp": timestamp,
                    }
                )
            else:
                # clickhouse-driver style
                await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    INSERT INTO metrics (
                        document_id, metric_type, value, timestamp
                    ) VALUES
                    """,
                    [(document_id, metric_type, value, timestamp)]
                )
            
            logger.debug(f"Inserted metric for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to insert metric: {e}")
            # Don't raise error for metrics - they're not critical
    
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document metadata by ID.
        
        Args:
            document_id: Document identifier.
            
        Returns:
            Document metadata or None if not found.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        try:
            loop = asyncio.get_event_loop()
            
            if self.use_cloud_driver:
                result = await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    SELECT * FROM documents
                    WHERE document_id = {doc_id:UUID}
                    """,
                    {"doc_id": document_id}
                )
            else:
                result = await loop.run_in_executor(
                    None,
                    self._execute_query,
                    """
                    SELECT * FROM documents
                    WHERE document_id = %(doc_id)s
                    FORMAT JSONEachRow
                    """,
                    {"doc_id": document_id}
                )
            
            if result:
                row = result[0]
                return {
                    "document_id": str(row[0]),
                    "filename": row[1],
                    "file_size": row[2],
                    "page_count": row[3],
                    "upload_timestamp": row[4],
                    "processing_time_ms": row[5],
                    "status": row[6],
                    "error_message": row[7],
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            raise DatabaseError(f"Failed to get document: {e}")
    
    async def get_documents(
        self,
        limit: int = 20,
        offset: int = 0,
        doc_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get documents with pagination and filtering.
        
        Args:
            limit: Maximum results.
            offset: Results offset.
            doc_id: Optional document ID filter.
            start_date: Optional start date filter.
            end_date: Optional end date filter.
            
        Returns:
            List of document metadata.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        query = "SELECT * FROM documents WHERE 1=1"
        params = {}
        
        if doc_id:
            if self.use_cloud_driver:
                query += " AND document_id = {doc_id:UUID}"
            else:
                query += " AND document_id = %(doc_id)s"
            params["doc_id"] = doc_id
        
        if start_date:
            if self.use_cloud_driver:
                query += " AND upload_timestamp >= {start_date:DateTime}"
            else:
                query += " AND upload_timestamp >= %(start_date)s"
            params["start_date"] = start_date
        
        if end_date:
            if self.use_cloud_driver:
                query += " AND upload_timestamp <= {end_date:DateTime}"
            else:
                query += " AND upload_timestamp <= %(end_date)s"
            params["end_date"] = end_date
        
        if self.use_cloud_driver:
            query += " ORDER BY upload_timestamp DESC LIMIT {limit:UInt32} OFFSET {offset:UInt32}"
        else:
            query += " ORDER BY upload_timestamp DESC LIMIT %(limit)s OFFSET %(offset)s"
        params["limit"] = limit
        params["offset"] = offset
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_query,
                query,
                params
            )
            
            documents = []
            for row in result:
                documents.append({
                    "document_id": str(row[0]),
                    "filename": row[1],
                    "file_size": row[2],
                    "page_count": row[3],
                    "upload_timestamp": row[4],
                    "processing_time_ms": row[5],
                    "status": row[6],
                    "error_message": row[7],
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            raise DatabaseError(f"Failed to get documents: {e}")
    
    async def count_documents(
        self,
        doc_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count documents with optional filtering.
        
        Args:
            doc_id: Optional document ID filter.
            start_date: Optional start date filter.
            end_date: Optional end date filter.
            
        Returns:
            Total count.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        query = "SELECT COUNT(*) FROM documents WHERE 1=1"
        params = {}
        
        if doc_id:
            if self.use_cloud_driver:
                query += " AND document_id = {doc_id:UUID}"
            else:
                query += " AND document_id = %(doc_id)s"
            params["doc_id"] = doc_id
        
        if start_date:
            if self.use_cloud_driver:
                query += " AND upload_timestamp >= {start_date:DateTime}"
            else:
                query += " AND upload_timestamp >= %(start_date)s"
            params["start_date"] = start_date
        
        if end_date:
            if self.use_cloud_driver:
                query += " AND upload_timestamp <= {end_date:DateTime}"
            else:
                query += " AND upload_timestamp <= %(end_date)s"
            params["end_date"] = end_date
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_query,
                query,
                params
            )
            
            return result[0][0] if result else 0
            
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            raise DatabaseError(f"Failed to count documents: {e}")
    
    async def get_findings_by_document(
        self,
        document_id: str,
        finding_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get findings for a specific document.
        
        Args:
            document_id: Document identifier.
            finding_type: Optional finding type filter.
            
        Returns:
            List of findings.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        if self.use_cloud_driver:
            query = """
                SELECT finding_id, document_id, finding_type, value,
                       page_number, confidence, context, detected_at
                FROM findings
                WHERE document_id = {doc_id:UUID}
            """
        else:
            query = """
                SELECT finding_id, document_id, finding_type, value,
                       page_number, confidence, context, detected_at
                FROM findings
                WHERE document_id = %(doc_id)s
            """
        params = {"doc_id": document_id}
        
        if finding_type:
            if self.use_cloud_driver:
                query += " AND finding_type = {finding_type:String}"
            else:
                query += " AND finding_type = %(finding_type)s"
            params["finding_type"] = finding_type
        
        query += " ORDER BY page_number, detected_at"
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_query,
                query,
                params
            )
            
            findings = []
            for row in result:
                findings.append({
                    "finding_id": str(row[0]),
                    "document_id": str(row[1]),
                    "finding_type": row[2],
                    "value": row[3],
                    "page_number": row[4],
                    "confidence": row[5],
                    "context": row[6],
                    "detected_at": row[7],
                })
            
            return findings
            
        except Exception as e:
            logger.error(f"Failed to get findings: {e}")
            raise DatabaseError(f"Failed to get findings: {e}")
    
    async def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get overall summary statistics.
        
        Returns:
            Dictionary with various statistics.
        """
        if not self._initialized:
            raise DatabaseError("Client not initialized")
        
        try:
            loop = asyncio.get_event_loop()
            
            # Get document stats
            doc_stats = await loop.run_in_executor(
                None,
                self._execute_query,
                """
                SELECT
                    COUNT(*) as total_documents,
                    SUM(page_count) as total_pages,
                    AVG(processing_time_ms) as avg_processing_time,
                    COUNT(DISTINCT document_id) as unique_documents
                FROM documents
                WHERE status = 'success'
                """
            )
            
            # Get findings stats
            findings_stats = await loop.run_in_executor(
                None,
                self._execute_query,
                """
                SELECT
                    finding_type,
                    COUNT(*) as count
                FROM findings
                GROUP BY finding_type
                """
            )
            
            # Get documents with findings
            docs_with_findings = await loop.run_in_executor(
                None,
                self._execute_query,
                """
                SELECT COUNT(DISTINCT document_id)
                FROM findings
                """
            )
            
            # Build response
            stats = {
                "total_documents": doc_stats[0][0] if doc_stats else 0,
                "total_pages": doc_stats[0][1] if doc_stats else 0,
                "avg_processing_time": doc_stats[0][2] if doc_stats else 0,
                "documents_with_findings": docs_with_findings[0][0] if docs_with_findings else 0,
                "findings_by_type": {},
                "total_findings": 0,
            }
            
            for row in findings_stats:
                stats["findings_by_type"][row[0]] = row[1]
                stats["total_findings"] += row[1]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get summary statistics: {e}")
            raise DatabaseError(f"Failed to get summary statistics: {e}")
    
    async def close(self) -> None:
        """Close database connection."""
        if self._client:
            try:
                loop = asyncio.get_event_loop()
                if self.use_cloud_driver:
                    # clickhouse-connect doesn't have a disconnect method
                    pass
                else:
                    await loop.run_in_executor(None, self._client.disconnect)
                logger.info("ClickHouse connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


def create_clickhouse_client() -> ClickHouseClient:
    """
    Factory function to create ClickHouse client.
    
    Returns:
        Configured ClickHouseClient instance.
    """
    # Get fresh settings instead of using module-level cached settings
    current_settings = get_settings()
    return ClickHouseClient(
        host=current_settings.clickhouse_host,
        port=current_settings.clickhouse_port,
        database=current_settings.clickhouse_database,
        user=current_settings.clickhouse_user,
        password=current_settings.clickhouse_password,
        secure=current_settings.clickhouse_secure,
        verify=current_settings.clickhouse_verify,
    )


def get_db_client() -> ClickHouseClient:
    """
    Get the global database client instance.
    
    Returns:
        ClickHouseClient instance.
        
    Raises:
        DatabaseError: If client not initialized.
    """
    global _db_client
    
    if not _db_client:
        # Import here to avoid circular import
        from app.main import db_client
        _db_client = db_client
    
    if not _db_client:
        raise DatabaseError("Database client not initialized")
    
    return _db_client
