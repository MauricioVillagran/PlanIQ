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

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_access_ttl_minutes: int = Field(default=15, ge=1)
    jwt_refresh_ttl_hours: int = Field(default=12, ge=1)
    auth_max_failed_attempts: int = Field(default=5, ge=1)
    # 0 = la cuenta bloqueada solo la desbloquea un administrador.
    auth_auto_unlock_minutes: int = Field(default=0, ge=0)
    auth_password_min_length: int = Field(default=10, ge=8)
    # Formato "<cantidad>/<second|minute|hour>", por IP.
    auth_login_rate_limit: str = Field(default="10/minute", pattern=r"^\d+/(second|minute|hour)$")
    # Vacío = Secure solo fuera de desarrollo y pruebas. Forzar false si QA corre sin HTTPS.
    auth_cookie_secure: bool | None = None

    initial_admin_username: str | None = None
    initial_admin_email: str | None = None
    initial_admin_password: SecretStr | None = None

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def secure_cookies(self) -> bool:
        """Cookies solo por HTTPS fuera de desarrollo y pruebas, salvo que se indique lo contrario."""
        if self.auth_cookie_secure is not None:
            return self.auth_cookie_secure
        return self.app_env not in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    # Los campos obligatorios (DB_HOST, DB_USER, DB_PASSWORD) llegan por variables de entorno.
    return Settings()
