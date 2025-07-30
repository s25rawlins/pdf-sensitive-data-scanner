"""
Application configuration and settings management.

This module handles all configuration settings using Pydantic Settings
for type safety and environment variable support.
"""

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    All settings can be overridden using environment variables
    with the same name in uppercase.
    """
    
    # Application settings
    app_name: str = "PDF Sensitive Data Scanner"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Security settings
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    allowed_hosts: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]
    
    # File upload settings
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_file_extensions: List[str] = [".pdf"]
    upload_folder: str = "uploads"
    
    # ClickHouse settings
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_database: str = "default"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_secure: bool = False
    clickhouse_verify: bool = True
    
    # Performance settings
    max_concurrent_uploads: int = 10
    processing_timeout: int = 300  # 5 minutes
    
    # Metrics settings
    enable_metrics: bool = True
    metrics_retention_days: int = 30
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    def get_clickhouse_url(self) -> str:
        """
        Construct ClickHouse connection URL.
        
        Returns:
            ClickHouse connection string.
        """
        protocol = "clickhouse+https" if self.clickhouse_secure else "clickhouse"
        auth = f"{self.clickhouse_user}:{self.clickhouse_password}@" if self.clickhouse_password else ""
        return f"{protocol}://{auth}{self.clickhouse_host}:{self.clickhouse_port}/{self.clickhouse_database}"
    
    def validate_settings(self) -> None:
        """
        Validate critical settings on startup.
        
        Raises:
            ValueError: If any critical setting is invalid.
        """
        if self.max_upload_size <= 0:
            raise ValueError("max_upload_size must be positive")
        
        if not self.allowed_file_extensions:
            raise ValueError("At least one file extension must be allowed")
        
        if self.processing_timeout <= 0:
            raise ValueError("processing_timeout must be positive")
        
        logger.info("Settings validation passed")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Singleton Settings instance.
    """
    settings = Settings()
    settings.validate_settings()
    return settings