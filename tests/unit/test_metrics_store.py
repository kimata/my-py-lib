#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.metrics.store モジュールのユニットテスト
"""

from __future__ import annotations

import sqlite3

import pytest

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value REAL NOT NULL
);
"""


@pytest.fixture
def schema_path(temp_dir):
    path = temp_dir / "metrics.schema"
    path.write_text(SCHEMA)
    return path


@pytest.fixture
def db_path(temp_dir):
    return temp_dir / "data" / "metrics.db"


class TestSQLiteStoreBase:
    """SQLiteStoreBase のテスト"""

    def test_initialize_creates_db_and_schema(self, db_path, schema_path):
        """初期化で DB とテーブルが作成される"""
        import my_lib.metrics.store

        store = my_lib.metrics.store.SQLiteStoreBase(db_path=db_path, schema_path=schema_path)

        assert db_path.exists()
        with store.connection() as conn:
            conn.execute("INSERT INTO metrics (value) VALUES (1.5)")
            conn.commit()
            row = conn.execute("SELECT value FROM metrics").fetchone()
            assert row["value"] == 1.5  # row_factory = sqlite3.Row

    def test_missing_schema_raises(self, db_path, temp_dir):
        """スキーマファイルが無いと FileNotFoundError"""
        import my_lib.metrics.store

        with pytest.raises(FileNotFoundError):
            my_lib.metrics.store.SQLiteStoreBase(db_path=db_path, schema_path=temp_dir / "missing.schema")

    def test_schema_metadata_recorded(self, db_path, schema_path):
        """スキーマメタデータ (名前と SHA-256) が記録される"""
        import my_lib.metrics.store

        store = my_lib.metrics.store.SQLiteStoreBase(db_path=db_path, schema_path=schema_path)

        with store.connection() as conn:
            rows = dict(
                conn.execute("SELECT key, value FROM schema_metadata").fetchall()  # type: ignore[arg-type]
            )
        assert rows["schema_name"] == "metrics.schema"
        assert len(rows["schema_sha256"]) == 64

    def test_schema_name_mismatch_raises(self, db_path, schema_path, temp_dir):
        """別名のスキーマで再初期化すると整合性エラー"""
        import my_lib.metrics.store

        my_lib.metrics.store.SQLiteStoreBase(db_path=db_path, schema_path=schema_path)

        other_schema = temp_dir / "other.schema"
        other_schema.write_text(SCHEMA)
        with pytest.raises(RuntimeError, match="Schema metadata mismatch"):
            my_lib.metrics.store.SQLiteStoreBase(db_path=db_path, schema_path=other_schema)


class TestMigrations:
    """マイグレーションのテスト"""

    def test_migration_applied_once(self, db_path, schema_path):
        """マイグレーションは1回だけ適用される"""
        import my_lib.metrics.store

        calls: list[str] = []

        def add_column(conn: sqlite3.Connection) -> None:
            calls.append("add_column")
            conn.execute("ALTER TABLE metrics ADD COLUMN label TEXT")

        migrations = (my_lib.metrics.store.Migration(name="add_label", apply=add_column),)

        store = my_lib.metrics.store.SQLiteStoreBase(
            db_path=db_path, schema_path=schema_path, migrations=migrations
        )
        assert calls == ["add_column"]
        assert store.pending_migrations() == ()

        # 再初期化しても再適用されない
        my_lib.metrics.store.SQLiteStoreBase(db_path=db_path, schema_path=schema_path, migrations=migrations)
        assert calls == ["add_column"]

    def test_pending_migrations_before_creation(self, db_path, schema_path):
        """DB 未作成時は全マイグレーションが pending"""
        import my_lib.metrics.store

        migrations = (my_lib.metrics.store.Migration(name="m1", apply=lambda conn: None),)
        store = my_lib.metrics.store.SQLiteStoreBase(
            db_path=db_path,
            schema_path=schema_path,
            migrations=migrations,
            auto_initialize=False,
        )
        assert store.pending_migrations() == ("m1",)


class TestCalculateBoxplotStats:
    """calculate_boxplot_stats のテスト"""

    def test_empty_returns_none(self):
        import my_lib.metrics.store

        assert my_lib.metrics.store.calculate_boxplot_stats([]) is None

    def test_single_value(self):
        import my_lib.metrics.store

        stats = my_lib.metrics.store.calculate_boxplot_stats([5.0])
        assert stats is not None
        assert stats.min == stats.max == stats.median == 5.0
        assert stats.count == 1

    def test_percentile_matches_numpy_semantics(self):
        """パーセンタイルが numpy.percentile (線形補間) と一致する"""
        import my_lib.metrics.store

        # numpy.percentile([1..10], [25, 50, 75]) == [3.25, 5.5, 7.75]
        stats = my_lib.metrics.store.calculate_boxplot_stats(list(range(1, 11)))
        assert stats is not None
        assert stats.q1 == 3.25
        assert stats.median == 5.5
        assert stats.q3 == 7.75
        assert stats.min == 1.0
        assert stats.max == 10.0
        assert stats.count == 10

    def test_outliers_detected(self):
        """1.5 IQR を超える値が外れ値になる"""
        import my_lib.metrics.store

        values = [10.0] * 10 + [100.0]
        stats = my_lib.metrics.store.calculate_boxplot_stats(values)
        assert stats is not None
        assert stats.outliers == (100.0,)

    def test_outliers_limited(self):
        """外れ値は上限件数までに制限される"""
        import my_lib.metrics.store

        values = [10.0] * 100 + [1000.0 + i for i in range(30)]
        stats = my_lib.metrics.store.calculate_boxplot_stats(values)
        assert stats is not None
        assert len(stats.outliers) == my_lib.metrics.store.BOXPLOT_MAX_OUTLIERS
