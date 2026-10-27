"""Conexión ODBC mínima a la base propia.

Esqueleto de F0.2: F0.3 lo reemplaza por la configuración con pydantic-settings y el engine de SQLAlchemy.
"""

import os

import pyodbc


def connection_string() -> str:
    return (
        f"DRIVER={{{os.environ.get('DB_ODBC_DRIVER', 'ODBC Driver 18 for SQL Server')}}};"
        f"SERVER={os.environ['DB_HOST']},{os.environ.get('DB_PORT', '1433')};"
        f"DATABASE={os.environ['DB_NAME']};"
        f"UID={os.environ['DB_USER']};"
        f"PWD={os.environ['DB_PASSWORD']};"
        "Encrypt=yes;"
        f"TrustServerCertificate={os.environ.get('DB_TRUST_SERVER_CERTIFICATE', 'no')};"
    )


def ping(timeout_seconds: int = 5) -> str:
    """Abre una conexión, ejecuta una consulta trivial y devuelve la versión del servidor."""
    with pyodbc.connect(connection_string(), timeout=timeout_seconds) as conn:
        row = conn.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(32))").fetchone()
        return str(row[0])
