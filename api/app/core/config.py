"""Configuración de la aplicación, leída solo desde variables de entorno."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    app_env: Literal["development", "qa", "production", "test"] = "development"
    app_timezone: str = "America/Santiago"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    db_host: str
    db_port: int = 1433
    db_name: str = "planiq"
    db_user: str
    db_password: SecretStr
    db_odbc_driver: str = "ODBC Driver 18 for SQL Server"
    db_trust_server_certificate: bool = False
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    file_storage_path: str = "/data/storage"
    upload_max_size_mb: int = Field(default=300, ge=1)

    worker_poll_seconds: float = Field(default=2.0, gt=0)
    worker_stale_job_minutes: int = Field(default=15, ge=1)

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    # Los campos obligatorios (DB_HOST, DB_USER, DB_PASSWORD) llegan por variables de entorno.
    return Settings()
