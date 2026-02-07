#!/usr/bin/env python3
"""DuckDB database utility functions.

Provides thread-safe connection pooling and common utilities for DuckDB.
Separates read-only and read-write connections for optimal performance.

Key features:
- Thread-safe connection pool (one connection per database path per mode)
- Read-only vs read-write connection separation
- sqlite_util-like API for easy migration
- Schema management utilities

Usage:
    # Using connection pool (recommended for web apps)
    with my_lib.duckdb_util.connect(db_path, read_only=True) as conn:
        result = conn.execute("SELECT * FROM table").fetchall()

    # Without pool (for one-off scripts)
    with my_lib.duckdb_util.connect(db_path, use_pool=False) as conn:
        conn.execute("INSERT INTO table VALUES (?)", [value])

    # Close all connections on shutdown
    my_lib.duckdb_util.close_all_connections()
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import pathlib
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

try:
    import duckdb
except ImportError as e:
    raise ImportError("duckdb is required for duckdb_util. Install it with: pip install duckdb") from e

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConnectionKey:
    """Key for connection pool lookup."""

    db_path: pathlib.Path
    read_only: bool


class ConnectionPool:
    """Thread-safe DuckDB connection pool.

    Maintains one connection per database path per mode (read-only/read-write).
    Connections are reused to avoid the overhead of repeated connection establishment.

    Thread safety:
    - Uses threading.Lock for connection creation/access
    - DuckDB connections themselves are thread-safe for concurrent reads
    - For writes, external synchronization may be needed depending on use case
    """

    def __init__(self) -> None:
        """Initialize the connection pool."""
        self._connections: dict[ConnectionKey, duckdb.DuckDBPyConnection] = {}
        self._lock = threading.Lock()

    def get_connection(
        self,
        db_path: pathlib.Path,
        read_only: bool = False,
    ) -> duckdb.DuckDBPyConnection:
        """Get a connection from the pool, creating one if necessary.

        Args:
            db_path: Path to the DuckDB database file
            read_only: If True, open in read-only mode

        Returns:
            DuckDB connection (reused from pool if available)
        """
        key = ConnectionKey(db_path=db_path.resolve(), read_only=read_only)

        with self._lock:
            if key not in self._connections:
                # Ensure parent directory exists for new databases
                if not read_only:
                    db_path.parent.mkdir(parents=True, exist_ok=True)

                conn = duckdb.connect(str(db_path), read_only=read_only)
                self._connections[key] = conn
                logger.debug(
                    "Created new DuckDB connection: %s (read_only=%s)",
                    db_path,
                    read_only,
                )

            return self._connections[key]

    def close_connection(
        self,
        db_path: pathlib.Path,
        read_only: bool = False,
    ) -> bool:
        """Close a specific connection and remove it from the pool.

        Args:
            db_path: Path to the DuckDB database file
            read_only: Connection mode to close

        Returns:
            True if connection was found and closed, False otherwise
        """
        key = ConnectionKey(db_path=db_path.resolve(), read_only=read_only)

        with self._lock:
            if key in self._connections:
                try:
                    self._connections[key].close()
                except Exception:
                    logger.exception("Error closing connection: %s", db_path)
                del self._connections[key]
                logger.debug(
                    "Closed DuckDB connection: %s (read_only=%s)",
                    db_path,
                    read_only,
                )
                return True
            return False

    def close_all(self) -> int:
        """Close all connections in the pool.

        Returns:
            Number of connections closed
        """
        with self._lock:
            count = len(self._connections)
            for key, conn in list(self._connections.items()):
                try:
                    conn.close()
                    logger.debug(
                        "Closed DuckDB connection: %s (read_only=%s)",
                        key.db_path,
                        key.read_only,
                    )
                except Exception:
                    logger.exception("Error closing connection: %s", key.db_path)
            self._connections.clear()
            if count > 0:
                logger.info("Closed %d DuckDB connections", count)
            return count

    def get_pool_stats(self) -> dict[str, int]:
        """Get statistics about the connection pool.

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            read_only_count = sum(1 for k in self._connections if k.read_only)
            read_write_count = len(self._connections) - read_only_count
            return {
                "total": len(self._connections),
                "read_only": read_only_count,
                "read_write": read_write_count,
            }


# Global connection pool
_pool = ConnectionPool()


# Register cleanup on interpreter shutdown
@atexit.register
def _cleanup_pool() -> None:
    """Clean up connection pool on shutdown."""
    _pool.close_all()


def get_pool() -> ConnectionPool:
    """Get the global connection pool.

    Returns:
        The global ConnectionPool instance
    """
    return _pool


def close_all_connections() -> int:
    """Close all connections in the global pool.

    Call this on application shutdown or when connections need to be reset.

    Returns:
        Number of connections closed
    """
    return _pool.close_all()


@contextmanager
def connect(
    db_path: pathlib.Path,
    read_only: bool = False,
    use_pool: bool = True,
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Connect to a DuckDB database.

    Args:
        db_path: Path to the DuckDB database file
        read_only: If True, open in read-only mode (better for concurrent reads)
        use_pool: If True, use the connection pool (recommended for web apps).
                  If False, create a new connection that is closed on exit.

    Yields:
        DuckDB connection

    Example:
        # Read-only query (uses pooled connection)
        with connect(Path("data/db.duckdb"), read_only=True) as conn:
            result = conn.execute("SELECT * FROM table").fetchall()

        # Write operation
        with connect(Path("data/db.duckdb")) as conn:
            conn.execute("INSERT INTO table VALUES (?)", [value])
    """
    if use_pool:
        # Get connection from pool (connection is NOT closed on exit)
        conn = _pool.get_connection(db_path, read_only=read_only)
        try:
            yield conn
        except Exception:
            # DuckDB auto-rolls back on exception
            raise
    else:
        # Create new connection (closed on exit)
        if not read_only:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(db_path), read_only=read_only)
        try:
            yield conn
        finally:
            conn.close()


def init_schema(db_path: pathlib.Path, schema_path: pathlib.Path) -> None:
    """Initialize database schema from a schema file.

    Reads a SQLite-compatible schema file and creates tables in DuckDB.
    Most SQLite DDL is compatible with DuckDB.

    Args:
        db_path: Path to the DuckDB database file
        schema_path: Path to the schema file (SQL DDL statements)
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = schema_path.read_text()
    schema_sql = _convert_sqlite_to_duckdb_schema(schema_sql)

    # Use non-pooled connection for schema initialization
    with connect(db_path, use_pool=False) as conn:
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                # Table/index may already exist
                with contextlib.suppress(duckdb.CatalogException):
                    conn.execute(statement)


def _convert_sqlite_to_duckdb_schema(schema_sql: str) -> str:
    """Convert SQLite schema to DuckDB-compatible schema.

    Most SQLite DDL is compatible, but some adjustments may be needed.

    Args:
        schema_sql: Original SQLite schema

    Returns:
        DuckDB-compatible schema
    """
    # AUTOINCREMENT is not supported in DuckDB the same way
    schema_sql = schema_sql.replace("AUTOINCREMENT", "")
    return schema_sql


def table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Check if a table exists in the database.

    Args:
        conn: DuckDB connection
        table_name: Name of the table to check

    Returns:
        True if table exists
    """
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()
    return result is not None and result[0] > 0


def get_table_row_count(conn: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Get the number of rows in a table.

    Args:
        conn: DuckDB connection
        table_name: Name of the table

    Returns:
        Number of rows
    """
    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()  # noqa: S608
    return result[0] if result else 0


def checkpoint(db_path: pathlib.Path) -> None:
    """Force a checkpoint to write changes to disk.

    DuckDB's CHECKPOINT command ensures all changes are persisted.

    Args:
        db_path: Path to the DuckDB database file
    """
    with connect(db_path) as conn:
        conn.execute("CHECKPOINT")


def vacuum(db_path: pathlib.Path) -> None:
    """Optimize the database by reclaiming space.

    Note: DuckDB automatically manages storage, so this is rarely needed.

    Args:
        db_path: Path to the DuckDB database file
    """
    with connect(db_path) as conn:
        conn.execute("VACUUM")


def export_to_parquet(
    db_path: pathlib.Path,
    table_name: str,
    parquet_path: pathlib.Path,
    compression: str = "zstd",
) -> None:
    """Export a table to Parquet format.

    Parquet is highly compressed and efficient for archival or data exchange.

    Args:
        db_path: Path to the DuckDB database file
        table_name: Name of the table to export
        parquet_path: Destination Parquet file path
        compression: Compression algorithm (zstd, snappy, gzip, none)
    """
    with connect(db_path, read_only=True) as conn:
        conn.execute(
            f"COPY {table_name} TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION {compression.upper()})"
        )


def import_from_sqlite(
    duckdb_path: pathlib.Path,
    sqlite_path: pathlib.Path,
    tables: list[str],
) -> dict[str, int]:
    """Import tables from SQLite database to DuckDB.

    Args:
        duckdb_path: Path to the DuckDB database file
        sqlite_path: Path to the SQLite database file
        tables: List of table names to import

    Returns:
        Dictionary mapping table names to row counts imported
    """
    results = {}

    with connect(duckdb_path, use_pool=False) as conn:
        # Install and load SQLite extension
        conn.execute("INSTALL sqlite")
        conn.execute("LOAD sqlite")

        # Attach SQLite database
        conn.execute(f"ATTACH '{sqlite_path}' AS sqlite_db (TYPE SQLITE, READ_ONLY)")

        for table in tables:
            # Drop existing table if exists
            conn.execute(f"DROP TABLE IF EXISTS {table}")

            # Create table from SQLite
            conn.execute(f"CREATE TABLE {table} AS SELECT * FROM sqlite_db.{table}")  # noqa: S608

            # Get row count
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
            results[table] = result[0] if result else 0

        conn.execute("DETACH sqlite_db")

    return results


def fetchall_as_dict(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: list | tuple | None = None,
) -> list[dict]:
    """Execute query and return results as list of dictionaries.

    Args:
        conn: DuckDB connection
        query: SQL query
        params: Query parameters

    Returns:
        List of dictionaries with column names as keys
    """
    result = conn.execute(query, params) if params else conn.execute(query)
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]


def fetchone_as_dict(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: list | tuple | None = None,
) -> dict | None:
    """Execute query and return first result as dictionary.

    Args:
        conn: DuckDB connection
        query: SQL query
        params: Query parameters

    Returns:
        Dictionary with column names as keys, or None if no results
    """
    result = conn.execute(query, params) if params else conn.execute(query)
    columns = [desc[0] for desc in result.description]
    row = result.fetchone()
    return dict(zip(columns, row, strict=False)) if row else None


def get_next_id(conn: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Get the next available ID for a table.

    This is a common pattern for tables using manual ID management.

    Args:
        conn: DuckDB connection
        table_name: Name of the table

    Returns:
        Next available ID (max(id) + 1, or 1 if table is empty)
    """
    result = conn.execute(
        f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table_name}"  # noqa: S608
    ).fetchone()
    return result[0] if result else 1
