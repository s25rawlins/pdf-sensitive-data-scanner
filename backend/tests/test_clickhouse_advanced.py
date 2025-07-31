"""
Advanced tests for ClickHouse database client.

This module provides comprehensive tests for the ClickHouse client,
focusing on edge cases, error handling, and achieving high code coverage.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from clickhouse_driver.errors import Error as ClickHouseError

from app.db.clickhouse import (
    ClickHouseClient,
    DatabaseError,
    create_clickhouse_client,
    get_db_client,
)


class TestClickHouseClientInitialization:
    """Test suite for ClickHouse client initialization and configuration."""

    def test_client_auto_detect_cloud_driver(self) -> None:
        """Test automatic detection of cloud driver based on port and security."""
        # Cloud port with secure connection should use cloud driver
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            secure=True,
        )
        assert client.use_cloud_driver is True

        # Standard port with secure connection should use cloud driver
        client = ClickHouseClient(
            host="localhost",
            port=8123,
            database="test",
            user="default",
            secure=True,
        )
        assert client.use_cloud_driver is True

        # Non-cloud port should use native driver
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            secure=False,
        )
        assert client.use_cloud_driver is False

    def test_client_force_driver_selection(self) -> None:
        """Test forcing specific driver selection."""
        # Force cloud driver
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        assert client.use_cloud_driver is True

        # Force native driver
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            secure=True,
            use_cloud_driver=False,
        )
        assert client.use_cloud_driver is False

    @patch("app.db.clickhouse.logger")
    def test_client_initialization_logging(self, mock_logger: Mock) -> None:
        """Test that initialization logs the correct driver type."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            secure=True,
        )
        mock_logger.info.assert_called_with(
            "Using cloud driver for ClickHouse connection"
        )


class TestClickHouseClientDriverCreation:
    """Test suite for driver creation methods."""

    def test_create_cloud_client_success(self) -> None:
        """Test successful creation of cloud client."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            password="password",
            secure=True,
            verify=True,
        )

        with patch("clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            result = client._create_cloud_client()

            mock_get_client.assert_called_once_with(
                host="localhost",
                port=8443,
                username="default",
                password="password",
                database="test",
                secure=True,
                verify=True,
                compress=False,
            )
            assert result == mock_client

    def test_create_cloud_client_import_error(self) -> None:
        """Test cloud client creation when clickhouse-connect is not installed."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
        )

        with patch("builtins.__import__", side_effect=ImportError):
            with pytest.raises(DatabaseError) as exc_info:
                client._create_cloud_client()
            assert "clickhouse-connect is required" in str(exc_info.value)

    def test_create_native_client_success(self) -> None:
        """Test successful creation of native client."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            password="password",
            secure=False,
            verify=False,
        )

        with patch("clickhouse_driver.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = client._create_native_client()

            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args[1]
            assert call_args["host"] == "localhost"
            assert call_args["port"] == 9000
            assert call_args["user"] == "default"
            assert call_args["password"] == "password"
            assert call_args["database"] == "test"
            assert call_args["secure"] is False
            assert result == mock_client

    def test_create_native_client_with_ssl(self) -> None:
        """Test native client creation with SSL settings."""
        client = ClickHouseClient(
            host="localhost",
            port=9440,
            database="test",
            user="default",
            secure=True,
            verify=True,
        )

        with patch("clickhouse_driver.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = client._create_native_client()

            call_args = mock_client_class.call_args[1]
            assert call_args["secure"] is True
            assert call_args["verify"] is True
            assert "ca_certs" in call_args

    def test_create_native_client_import_error(self) -> None:
        """Test native client creation when clickhouse-driver is not installed."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )

        with patch("builtins.__import__", side_effect=ImportError):
            with pytest.raises(DatabaseError) as exc_info:
                client._create_native_client()
            assert "clickhouse-driver is required" in str(exc_info.value)


class TestClickHouseClientQueryExecution:
    """Test suite for query execution methods."""

    def test_execute_query_cloud_driver_command(self) -> None:
        """Test query execution with cloud driver for command queries."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._client = MagicMock()

        # Test INSERT query
        client._execute_query("INSERT INTO test VALUES", {"value": 1})
        client._client.command.assert_called_once_with(
            "INSERT INTO test VALUES", parameters={"value": 1}
        )

        # Test CREATE query
        client._client.reset_mock()
        client._execute_query("CREATE TABLE test (id Int32)")
        client._client.command.assert_called_once_with(
            "CREATE TABLE test (id Int32)", parameters=None
        )

    def test_execute_query_cloud_driver_select(self) -> None:
        """Test query execution with cloud driver for SELECT queries."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._client = MagicMock()

        # Mock query result
        mock_result = MagicMock()
        mock_result.result_rows = [(1, "test")]
        client._client.query.return_value = mock_result

        result = client._execute_query("SELECT * FROM test")
        client._client.query.assert_called_once_with(
            "SELECT * FROM test", parameters=None
        )
        assert result == [(1, "test")]

    def test_execute_query_native_driver(self) -> None:
        """Test query execution with native driver."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._client = MagicMock()
        client._client.execute.return_value = [(1, "test")]

        result = client._execute_query("SELECT * FROM test", {"param": "value"})
        client._client.execute.assert_called_once_with(
            "SELECT * FROM test", {"param": "value"}
        )
        assert result == [(1, "test")]


class TestClickHouseClientInitializationSync:
    """Test suite for synchronous initialization methods."""

    @patch("app.db.clickhouse.logger")
    def test_initialize_sync_cloud_success(self, mock_logger: Mock) -> None:
        """Test successful synchronous initialization with cloud driver."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test_db",
            user="default",
            use_cloud_driver=True,
        )

        with patch.object(client, "_create_cloud_client") as mock_create:
            with patch.object(client, "_execute_query") as mock_execute:
                with patch.object(client, "_create_tables") as mock_create_tables:
                    mock_client = MagicMock()
                    mock_create.return_value = mock_client
                    mock_execute.return_value = [(1,)]

                    client._initialize_sync()

                    mock_create.assert_called_once()
                    assert client._client == mock_client
                    
                    # Verify connection test
                    assert mock_execute.call_args_list[0][0][0] == "SELECT 1"
                    
                    # Verify database creation
                    assert "CREATE DATABASE IF NOT EXISTS test_db" in str(mock_execute.call_args_list[1])
                    
                    # Verify USE database
                    assert mock_execute.call_args_list[2][0][0] == "USE test_db"
                    
                    mock_create_tables.assert_called_once()

    def test_initialize_sync_connection_failure(self) -> None:
        """Test initialization failure during connection test."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )

        with patch.object(client, "_create_native_client") as mock_create:
            with patch.object(client, "_execute_query") as mock_execute:
                mock_client = MagicMock()
                mock_create.return_value = mock_client
                mock_execute.side_effect = Exception("Connection failed")

                with pytest.raises(Exception) as exc_info:
                    client._initialize_sync()
                assert "Connection failed" in str(exc_info.value)

    @patch("app.db.clickhouse.logger")
    def test_initialize_sync_database_creation_warning(self, mock_logger: Mock) -> None:
        """Test initialization with database creation warning."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )

        with patch.object(client, "_create_native_client") as mock_create:
            with patch.object(client, "_execute_query") as mock_execute:
                with patch.object(client, "_create_tables"):
                    mock_client = MagicMock()
                    mock_create.return_value = mock_client
                    
                    # Connection test succeeds
                    mock_execute.side_effect = [
                        [(1,)],  # SELECT 1
                        Exception("Database already exists"),  # CREATE DATABASE
                        None,  # USE database
                    ]

                    client._initialize_sync()
                    
                    mock_logger.warning.assert_called()
                    assert "might already exist" in str(mock_logger.warning.call_args)


class TestClickHouseClientTableCreation:
    """Test suite for table creation methods."""

    @patch("app.db.clickhouse.logger")
    def test_create_tables_success(self, mock_logger: Mock) -> None:
        """Test successful table creation."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            client._create_tables()

            # Verify all three tables are created
            assert mock_execute.call_count == 3
            
            # Check documents table
            documents_query = mock_execute.call_args_list[0][0][0]
            assert "CREATE TABLE IF NOT EXISTS documents" in documents_query
            assert "document_id UUID" in documents_query
            
            # Check findings table
            findings_query = mock_execute.call_args_list[1][0][0]
            assert "CREATE TABLE IF NOT EXISTS findings" in findings_query
            assert "finding_id UUID DEFAULT generateUUIDv4()" in findings_query
            
            # Check metrics table
            metrics_query = mock_execute.call_args_list[2][0][0]
            assert "CREATE TABLE IF NOT EXISTS metrics" in metrics_query
            assert "TTL created_at + INTERVAL 30 DAY" in metrics_query

    @patch("app.db.clickhouse.logger")
    def test_create_tables_failure(self, mock_logger: Mock) -> None:
        """Test table creation failure handling."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Table creation failed")

            with pytest.raises(Exception) as exc_info:
                client._create_tables()
            
            assert "Table creation failed" in str(exc_info.value)
            mock_logger.error.assert_called()


class TestClickHouseClientAsyncMethods:
    """Test suite for async methods."""

    @pytest.mark.asyncio
    async def test_initialize_success(self) -> None:
        """Test successful async initialization."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )

        with patch.object(client, "_initialize_sync") as mock_init:
            await client.initialize()
            
            mock_init.assert_called_once()
            assert client._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_failure(self) -> None:
        """Test async initialization failure."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )

        with patch.object(client, "_initialize_sync") as mock_init:
            mock_init.side_effect = Exception("Init failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.initialize()
            
            assert "Database initialization failed" in str(exc_info.value)
            assert client._initialized is False

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self) -> None:
        """Test health check when client is not initialized."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        
        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_no_client(self) -> None:
        """Test health check when client is None."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = None
        
        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        """Test successful connection test."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test_db",
            user="default",
            secure=True,
        )
        client._client = MagicMock()
        client.use_cloud_driver = True

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                [("8.0.0",)],  # version
                [("test_db",)],  # currentDatabase
                [("documents",), ("findings",), ("metrics",)],  # SHOW TABLES
            ]

            result = await client.test_connection()

            assert result["status"] == "connected"
            assert result["version"] == "8.0.0"
            assert result["database"] == "test_db"
            assert result["tables"] == ["documents", "findings", "metrics"]
            assert result["host"] == "localhost"
            assert result["port"] == 8443
            assert result["secure"] is True
            assert result["driver"] == "cloud"

    @pytest.mark.asyncio
    async def test_test_connection_failure(self) -> None:
        """Test connection test failure."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            secure=False,
        )
        client._client = MagicMock()
        client.use_cloud_driver = False

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Connection error")

            result = await client.test_connection()

            assert result["status"] == "error"
            assert "Connection error" in result["error"]
            assert result["host"] == "localhost"
            assert result["port"] == 9000
            assert result["driver"] == "native"

    @pytest.mark.asyncio
    async def test_insert_document_not_initialized(self) -> None:
        """Test insert document when client is not initialized."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )

        with pytest.raises(DatabaseError) as exc_info:
            await client.insert_document(
                document_id=str(uuid4()),
                filename="test.pdf",
                file_size=1024,
                page_count=1,
                upload_timestamp=datetime.now(timezone.utc),
                processing_time_ms=100.0,
                status="success",
            )
        assert "Client not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_insert_finding_cloud_driver(self) -> None:
        """Test insert finding with cloud driver."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            await client.insert_finding(
                document_id=str(uuid4()),
                finding_type="email",
                value="test@example.com",
                page_number=1,
                confidence=0.95,
                context="Found email: test@example.com",
            )

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "INSERT INTO findings" in query
            assert "{document_id:UUID}" in query

    @pytest.mark.asyncio
    async def test_insert_metric_error_handling(self) -> None:
        """Test insert metric error handling (should not raise)."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            with patch("app.db.clickhouse.logger") as mock_logger:
                mock_execute.side_effect = Exception("Metric insert failed")

                # Should not raise exception
                await client.insert_metric(
                    document_id=str(uuid4()),
                    metric_type="processing_time",
                    value=100.0,
                    timestamp=datetime.now(timezone.utc),
                )

                mock_logger.error.assert_called()
                assert "Failed to insert metric" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_get_document_not_found(self) -> None:
        """Test get document when not found."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = []

            result = await client.get_document(str(uuid4()))
            assert result is None

    @pytest.mark.asyncio
    async def test_get_documents_with_all_filters(self) -> None:
        """Test get documents with all filters applied."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._initialized = True
        client._client = MagicMock()

        doc_id = str(uuid4())
        start_date = datetime.now(timezone.utc)
        end_date = datetime.now(timezone.utc)

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = []

            await client.get_documents(
                limit=10,
                offset=20,
                doc_id=doc_id,
                start_date=start_date,
                end_date=end_date,
            )

            query = mock_execute.call_args[0][0]
            assert "document_id = {doc_id:UUID}" in query
            assert "upload_timestamp >= {start_date:DateTime}" in query
            assert "upload_timestamp <= {end_date:DateTime}" in query
            assert "LIMIT {limit:UInt32} OFFSET {offset:UInt32}" in query

    @pytest.mark.asyncio
    async def test_count_documents_with_filters_native(self) -> None:
        """Test count documents with filters using native driver."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = [(42,)]

            count = await client.count_documents(
                doc_id=str(uuid4()),
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
            )

            assert count == 42
            query = mock_execute.call_args[0][0]
            assert "document_id = %(doc_id)s" in query
            assert "upload_timestamp >= %(start_date)s" in query
            assert "upload_timestamp <= %(end_date)s" in query

    @pytest.mark.asyncio
    async def test_get_findings_by_document_with_type_filter(self) -> None:
        """Test get findings with finding type filter."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = []

            await client.get_findings_by_document(
                document_id=str(uuid4()),
                finding_type="email",
            )

            query = mock_execute.call_args[0][0]
            assert "finding_type = %(finding_type)s" in query

    @pytest.mark.asyncio
    async def test_get_summary_statistics_empty_results(self) -> None:
        """Test get summary statistics with empty results."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                [],  # doc_stats
                [],  # findings_stats
                [],  # docs_with_findings
            ]

            stats = await client.get_summary_statistics()

            assert stats["total_documents"] == 0
            assert stats["total_pages"] == 0
            assert stats["avg_processing_time"] == 0
            assert stats["documents_with_findings"] == 0
            assert stats["findings_by_type"] == {}
            assert stats["total_findings"] == 0

    @pytest.mark.asyncio
    async def test_close_native_driver(self) -> None:
        """Test closing connection with native driver."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._client = MagicMock()

        await client.close()
        client._client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_cloud_driver(self) -> None:
        """Test closing connection with cloud driver (no-op)."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._client = MagicMock()

        await client.close()
        # Cloud driver doesn't have disconnect method
        assert not hasattr(client._client, "disconnect") or not client._client.disconnect.called

    @pytest.mark.asyncio
    async def test_close_error_handling(self) -> None:
        """Test error handling during connection close."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._client = MagicMock()
        client._client.disconnect.side_effect = Exception("Close failed")

        with patch("app.db.clickhouse.logger") as mock_logger:
            await client.close()
            mock_logger.error.assert_called()
            assert "Error closing connection" in str(mock_logger.error.call_args)


class TestClickHouseFactoryFunctions:
    """Test suite for factory functions."""

    def test_create_clickhouse_client(self) -> None:
        """Test create_clickhouse_client factory function."""
        with patch("app.db.clickhouse.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.clickhouse_host = "test-host"
            mock_settings.clickhouse_port = 8443
            mock_settings.clickhouse_database = "test-db"
            mock_settings.clickhouse_user = "test-user"
            mock_settings.clickhouse_password = "test-pass"
            mock_settings.clickhouse_secure = True
            mock_settings.clickhouse_verify = True
            mock_get_settings.return_value = mock_settings

            client = create_clickhouse_client()

            assert isinstance(client, ClickHouseClient)
            assert client.host == "test-host"
            assert client.port == 8443
            assert client.database == "test-db"
            assert client.user == "test-user"
            assert client.password == "test-pass"
            assert client.secure is True
            assert client.verify is True

    def test_get_db_client_initialized(self) -> None:
        """Test get_db_client when client is already initialized."""
        mock_client = MagicMock(spec=ClickHouseClient)
        
        with patch("app.db.clickhouse._db_client", mock_client):
            result = get_db_client()
            assert result == mock_client

    def test_get_db_client_from_main(self) -> None:
        """Test get_db_client when it needs to import from main."""
        mock_client = MagicMock(spec=ClickHouseClient)
        
        with patch("app.db.clickhouse._db_client", None):
            with patch("app.main.db_client", mock_client):
                result = get_db_client()
                assert result == mock_client

    def test_get_db_client_not_initialized(self) -> None:
        """Test get_db_client when no client is available."""
        with patch("app.db.clickhouse._db_client", None):
            with patch("app.main.db_client", None):
                with pytest.raises(DatabaseError) as exc_info:
                    get_db_client()
                assert "Database client not initialized" in str(exc_info.value)


class TestClickHouseClientErrorScenarios:
    """Test suite for various error scenarios."""

    @pytest.mark.asyncio
    async def test_insert_document_error_handling(self) -> None:
        """Test error handling in insert_document."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Insert failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.insert_document(
                    document_id=str(uuid4()),
                    filename="test.pdf",
                    file_size=1024,
                    page_count=1,
                    upload_timestamp=datetime.now(timezone.utc),
                    processing_time_ms=100.0,
                    status="success",
                )
            assert "Failed to insert document" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_documents_error_handling(self) -> None:
        """Test error handling in get_documents."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Query failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.get_documents()
            assert "Failed to get documents" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_count_documents_error_handling(self) -> None:
        """Test error handling in count_documents."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Count failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.count_documents()
            assert "Failed to count documents" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_findings_error_handling(self) -> None:
        """Test error handling in get_findings_by_document."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Findings query failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.get_findings_by_document(str(uuid4()))
            assert "Failed to get findings" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_summary_statistics_error_handling(self) -> None:
        """Test error handling in get_summary_statistics."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Stats query failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.get_summary_statistics()
            assert "Failed to get summary statistics" in str(exc_info.value)


class TestClickHouseClientEdgeCases:
    """Test suite for edge cases and additional coverage."""

    @pytest.mark.asyncio
    async def test_insert_document_native_driver(self) -> None:
        """Test insert document with native driver."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._initialized = True
        client._client = MagicMock()

        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with patch.object(client, "_execute_query") as mock_execute:
            await client.insert_document(
                document_id=doc_id,
                filename="test.pdf",
                file_size=1024,
                page_count=5,
                upload_timestamp=timestamp,
                processing_time_ms=100.0,
                status="success",
                error_message="Some error",
            )

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "INSERT INTO documents" in query
            params = mock_execute.call_args[0][1]
            assert params[0][0] == doc_id
            assert params[0][7] == "Some error"

    @pytest.mark.asyncio
    async def test_insert_finding_native_driver(self) -> None:
        """Test insert finding with native driver."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._initialized = True
        client._client = MagicMock()

        doc_id = str(uuid4())

        with patch.object(client, "_execute_query") as mock_execute:
            await client.insert_finding(
                document_id=doc_id,
                finding_type="ssn",
                value="123-45-6789",
                page_number=2,
                confidence=0.85,
                context=None,
            )

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "INSERT INTO findings" in query
            params = mock_execute.call_args[0][1]
            assert params[0][0] == doc_id
            assert params[0][5] is None  # context

    @pytest.mark.asyncio
    async def test_insert_metric_native_driver(self) -> None:
        """Test insert metric with native driver."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._initialized = True
        client._client = MagicMock()

        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with patch.object(client, "_execute_query") as mock_execute:
            await client.insert_metric(
                document_id=doc_id,
                metric_type="file_size",
                value=1024.0,
                timestamp=timestamp,
            )

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "INSERT INTO metrics" in query
            params = mock_execute.call_args[0][1]
            assert params[0][0] == doc_id

    @pytest.mark.asyncio
    async def test_get_document_cloud_driver(self) -> None:
        """Test get document with cloud driver."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._initialized = True
        client._client = MagicMock()

        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = [(
                doc_id,
                "test.pdf",
                1024,
                5,
                timestamp,
                100.0,
                "success",
                None,
            )]

            result = await client.get_document(doc_id)

            assert result is not None
            assert result["document_id"] == doc_id
            assert result["filename"] == "test.pdf"
            assert result["file_size"] == 1024
            assert result["page_count"] == 5
            assert result["status"] == "success"
            assert result["error_message"] is None

            query = mock_execute.call_args[0][0]
            assert "{doc_id:UUID}" in query

    @pytest.mark.asyncio
    async def test_get_documents_native_driver_no_filters(self) -> None:
        """Test get documents with native driver and no filters."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
            use_cloud_driver=False,
        )
        client._initialized = True
        client._client = MagicMock()

        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = [(
                doc_id,
                "test.pdf",
                1024,
                5,
                timestamp,
                100.0,
                "success",
                None,
            )]

            result = await client.get_documents()

            assert len(result) == 1
            assert result[0]["document_id"] == doc_id

            query = mock_execute.call_args[0][0]
            assert "LIMIT %(limit)s OFFSET %(offset)s" in query

    @pytest.mark.asyncio
    async def test_count_documents_no_results(self) -> None:
        """Test count documents with no results."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = []

            count = await client.count_documents()
            assert count == 0

    @pytest.mark.asyncio
    async def test_get_findings_cloud_driver(self) -> None:
        """Test get findings with cloud driver."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._initialized = True
        client._client = MagicMock()

        finding_id = str(uuid4())
        doc_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = [(
                finding_id,
                doc_id,
                "email",
                "test@example.com",
                1,
                0.95,
                "Email found",
                timestamp,
            )]

            result = await client.get_findings_by_document(doc_id)

            assert len(result) == 1
            assert result[0]["finding_id"] == finding_id
            assert result[0]["document_id"] == doc_id
            assert result[0]["finding_type"] == "email"
            assert result[0]["value"] == "test@example.com"

            query = mock_execute.call_args[0][0]
            assert "{doc_id:UUID}" in query

    @pytest.mark.asyncio
    async def test_get_summary_statistics_with_data(self) -> None:
        """Test get summary statistics with actual data."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                [(10, 50, 125.5, 10)],  # doc_stats
                [("email", 15), ("ssn", 8)],  # findings_stats
                [(7,)],  # docs_with_findings
            ]

            stats = await client.get_summary_statistics()

            assert stats["total_documents"] == 10
            assert stats["total_pages"] == 50
            assert stats["avg_processing_time"] == 125.5
            assert stats["documents_with_findings"] == 7
            assert stats["findings_by_type"]["email"] == 15
            assert stats["findings_by_type"]["ssn"] == 8
            assert stats["total_findings"] == 23

    @pytest.mark.asyncio
    async def test_health_check_success_with_result(self) -> None:
        """Test health check with successful result."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = [(1,)]

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_success_with_none(self) -> None:
        """Test health check with None result (treated as success)."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.return_value = None

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_close_no_client(self) -> None:
        """Test close when client is None."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._client = None

        # Should not raise
        await client.close()

    def test_execute_query_cloud_driver_no_result_rows(self) -> None:
        """Test execute query with cloud driver when result has no result_rows attribute."""
        client = ClickHouseClient(
            host="localhost",
            port=8443,
            database="test",
            user="default",
            use_cloud_driver=True,
        )
        client._client = MagicMock()

        # Mock query result without result_rows attribute
        mock_result = MagicMock()
        del mock_result.result_rows  # Remove the attribute
        client._client.query.return_value = mock_result

        result = client._execute_query("SELECT * FROM test")
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_insert_finding_error_handling(self) -> None:
        """Test error handling in insert_finding."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Finding insert failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.insert_finding(
                    document_id=str(uuid4()),
                    finding_type="email",
                    value="test@example.com",
                    page_number=1,
                    confidence=0.95,
                )
            assert "Failed to insert finding" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_document_error_handling(self) -> None:
        """Test error handling in get_document."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._initialized = True
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = Exception("Document query failed")

            with pytest.raises(DatabaseError) as exc_info:
                await client.get_document(str(uuid4()))
            assert "Failed to get document" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_test_connection_empty_results(self) -> None:
        """Test connection test with empty results."""
        client = ClickHouseClient(
            host="localhost",
            port=9000,
            database="test",
            user="default",
        )
        client._client = MagicMock()

        with patch.object(client, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                [],  # version
                [],  # currentDatabase
                [],  # SHOW TABLES
            ]

            result = await client.test_connection()

            assert result["status"] == "connected"
            assert result["version"] == "unknown"
            assert result["database"] == "unknown"
            assert result["tables"] == []
