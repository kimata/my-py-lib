#!/usr/bin/env python3
"""メトリクス用 SQLite ストアの共通基盤

各アプリの metrics collector が個別に持っていた SQLite の初期化・スキーマ管理・
マイグレーション・統計計算を共通化する (price_platform.sqlite_store の昇格)。

- Migration / MigrationRunner: 名前つきマイグレーションを DB ごとに1回だけ適用
- SQLiteBootstrapper: スキーマファイルからの初期化 + マイグレーション +
  スキーマメタデータ (SHA-256) の記録
- SQLiteStoreBase: 上記を束ねたストア基底クラス (connection() コンテキスト付き)
- calculate_boxplot_stats: 箱ヒゲ図統計量 (numpy 非依存)
"""

from __future__ import annotations

import collections.abc
import hashlib
import logging
import math
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import my_lib.sqlite_util
import my_lib.time

MigrationFn: TypeAlias = Callable[[sqlite3.Connection], None]

# 外れ値としてレスポンスに含める最大件数
BOXPLOT_MAX_OUTLIERS = 20


@dataclass(frozen=True)
class Migration:
    """名前つきマイグレーション

    Attributes:
        name: 一意なマイグレーション名 (適用済み管理のキー)
        apply: マイグレーション本体

    """

    name: str
    apply: MigrationFn


class MigrationRunner:
    """名前つき SQLite マイグレーションを DB ごとに1回だけ適用する"""

    def __init__(self, migrations: Sequence[Migration]):
        self._migrations = tuple(migrations)

    def planned_names(self) -> tuple[str, ...]:
        return tuple(migration.name for migration in self._migrations)

    def pending_names(self, conn: sqlite3.Connection) -> tuple[str, ...]:
        self._ensure_tracking_table(conn)
        applied = {row[0] for row in conn.execute("SELECT name FROM schema_migrations").fetchall()}
        return tuple(migration.name for migration in self._migrations if migration.name not in applied)

    def apply(self, conn: sqlite3.Connection) -> tuple[str, ...]:
        self._ensure_tracking_table(conn)
        applied = {row[0] for row in conn.execute("SELECT name FROM schema_migrations").fetchall()}
        applied_now: list[str] = []
        for migration in self._migrations:
            if migration.name in applied:
                continue
            migration.apply(conn)
            conn.execute(
                "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                (migration.name, my_lib.time.now().isoformat()),
            )
            logging.info("Applied migration %s", migration.name)
            applied_now.append(migration.name)
        return tuple(applied_now)

    @staticmethod
    def _ensure_tracking_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )


@dataclass(frozen=True)
class SchemaMetadata:
    """スキーマファイルの識別情報"""

    name: str
    source_path: Path

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.source_path.read_bytes()).hexdigest()


class SQLiteBootstrapper:
    """スキーマとマイグレーションを適用して SQLite DB を利用可能にする"""

    def __init__(
        self,
        *,
        db_path: Path,
        schema_path: Path,
        locking_mode: my_lib.sqlite_util.LockingMode = "NORMAL",
        migrations: Sequence[Migration] = (),
    ) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._locking_mode: my_lib.sqlite_util.LockingMode = locking_mode
        self._migration_runner = MigrationRunner(migrations)
        self._schema_metadata = SchemaMetadata(name=schema_path.name, source_path=schema_path)

    def ensure_ready(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self._schema_path}")
        my_lib.sqlite_util.init_schema_from_file(
            self._db_path,
            self._schema_path,
            locking_mode=self._locking_mode,
        )
        with my_lib.sqlite_util.connect(self._db_path, locking_mode=self._locking_mode) as conn:
            conn.row_factory = sqlite3.Row
            # マイグレーション適用後にメタデータを記録する。
            # 逆順だと DDL が未反映のまま新スキーマの SHA-256 が記録され、
            # 整合性メタデータが実態と乖離する。
            self._migration_runner.apply(conn)
            self._record_schema_metadata(conn)

    @property
    def schema_metadata(self) -> SchemaMetadata:
        return self._schema_metadata

    @property
    def db_path(self) -> Path:
        return self._db_path

    def pending_migrations(self) -> tuple[str, ...]:
        if not self._db_path.exists():
            return self._migration_runner.planned_names()
        with my_lib.sqlite_util.connect(self._db_path, locking_mode=self._locking_mode) as conn:
            return self._migration_runner.pending_names(conn)

    def _record_schema_metadata(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        existing_name = conn.execute("SELECT value FROM schema_metadata WHERE key = 'schema_name'").fetchone()
        if existing_name is not None and existing_name[0] != self._schema_metadata.name:
            raise RuntimeError(
                f"Schema metadata mismatch: existing={existing_name[0]} current={self._schema_metadata.name}"
            )

        for key, value in (
            ("schema_name", self._schema_metadata.name),
            ("schema_sha256", self._schema_metadata.sha256),
            ("schema_path", str(self._schema_metadata.source_path)),
        ):
            conn.execute(
                """
                INSERT INTO schema_metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
        conn.commit()


class SQLiteStoreBase:
    """SQLite ベースのメトリクスストアの基底クラス"""

    def __init__(
        self,
        *,
        db_path: Path,
        schema_path: Path,
        locking_mode: my_lib.sqlite_util.LockingMode = "NORMAL",
        migrations: Sequence[Migration] = (),
        auto_initialize: bool = True,
    ) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._locking_mode: my_lib.sqlite_util.LockingMode = locking_mode
        self._bootstrapper = SQLiteBootstrapper(
            db_path=db_path,
            schema_path=schema_path,
            locking_mode=locking_mode,
            migrations=migrations,
        )
        if auto_initialize:
            self.initialize()

    def initialize(self) -> None:
        self._bootstrapper.ensure_ready()

    def pending_migrations(self) -> tuple[str, ...]:
        return self._bootstrapper.pending_migrations()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def connection(self) -> collections.abc.Iterator[sqlite3.Connection]:
        with my_lib.sqlite_util.connect(self._db_path, locking_mode=self._locking_mode) as conn:
            conn.row_factory = sqlite3.Row
            yield conn


@dataclass(frozen=True)
class BoxplotStats:
    """箱ヒゲ図の統計量"""

    min: float
    q1: float
    median: float
    q3: float
    max: float
    outliers: tuple[float, ...]
    count: int


def _percentile(sorted_values: list[float], percent: float) -> float:
    """線形補間つきパーセンタイル (numpy.percentile の既定と同じ挙動)"""
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * percent / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[lower]
    fraction = rank - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def calculate_boxplot_stats(values: Sequence[float]) -> BoxplotStats | None:
    """箱ヒゲ図の統計量を計算する

    Args:
        values: 数値データ

    Returns:
        統計量。データが空の場合は None。
        外れ値 (Q1 - 1.5*IQR 未満または Q3 + 1.5*IQR 超) は昇順で
        最大 BOXPLOT_MAX_OUTLIERS 件に制限して返す。

    """
    if not values:
        return None

    sorted_values = sorted(float(v) for v in values)
    q1 = _percentile(sorted_values, 25)
    median = _percentile(sorted_values, 50)
    q3 = _percentile(sorted_values, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = tuple(v for v in sorted_values if v < lower_bound or v > upper_bound)[:BOXPLOT_MAX_OUTLIERS]

    return BoxplotStats(
        min=sorted_values[0],
        q1=q1,
        median=median,
        q3=q3,
        max=sorted_values[-1],
        outliers=outliers,
        count=len(sorted_values),
    )
