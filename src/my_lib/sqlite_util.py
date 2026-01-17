#!/usr/bin/env python3
"""SQLiteデータベースのユーティリティ関数

CephFS/NFS/Kubernetes manual storage class環境に最適化。
WALモード + 排他ロック + mmap無効化により、分散ファイルシステムでも安全に動作。

環境変数による設定:
    SQLITE_JOURNAL_MODE: ジャーナルモード (WAL/DELETE/TRUNCATE/PERSIST) デフォルト: WAL
    SQLITE_MMAP_SIZE: mmapサイズ（バイト単位、0で無効化）デフォルト: 0
    SQLITE_LOCKING_MODE: ロックモード (NORMAL/EXCLUSIVE) デフォルト: EXCLUSIVE
    SQLITE_LOCK_MODE: fcntlロックモード (BLOCK/NONBLOCK) デフォルト: BLOCK
    SQLITE_CHECKPOINT_DIR: WALチェックポイント用ディレクトリ
"""

from __future__ import annotations

import contextlib
import fcntl
import logging
import os
import pathlib
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal

# sqlite3.connect の isolation_level パラメータの型
IsolationLevel = Literal["DEFERRED", "EXCLUSIVE", "IMMEDIATE"] | None


@dataclass(frozen=True)
class SQLiteConnectionParams:
    """SQLite接続パラメータを保持するデータクラス"""

    timeout: float
    check_same_thread: bool
    isolation_level: IsolationLevel


def init_persistent(conn: sqlite3.Connection) -> None:
    """
    DBファイルに永続化されるPRAGMA設定を行う（新規作成時のみ）

    Args:
        conn: SQLiteデータベース接続
    """
    # ジャーナルモード: WALモードはNFSでも動作するが、DELETEモードの方が安全な場合もある
    journal_mode = os.environ.get("SQLITE_JOURNAL_MODE", "WAL")
    conn.execute(f"PRAGMA journal_mode={journal_mode}")

    # ページサイズ: 標準的な4096バイトを使用
    conn.execute("PRAGMA page_size=4096")

    conn.commit()
    logging.info("SQLiteデータベースの永続設定を初期化しました")


def init_connection(conn: sqlite3.Connection, *, timeout: float = 60.0) -> None:
    """
    接続ごとに必要なPRAGMA設定を行う（毎回の接続時に呼ぶ）

    Args:
        conn: SQLiteデータベース接続
        timeout: データベース接続のタイムアウト時間（秒）
    """
    # 同期モード: NFSやローカルストレージではFULLが最も安全
    conn.execute("PRAGMA synchronous=FULL")

    # WALモード使用時の設定
    journal_mode = os.environ.get("SQLITE_JOURNAL_MODE", "WAL")
    if journal_mode == "WAL":
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        conn.execute("PRAGMA journal_size_limit=67108864")  # 64MB

    # キャッシュサイズ: 控えめに設定（Pod のメモリ制限を考慮）
    conn.execute("PRAGMA cache_size=-32000")  # 約32MB

    # テンポラリストレージをメモリに設定
    conn.execute("PRAGMA temp_store=MEMORY")

    # mmapサイズ: NFSでは無効化（0で無効化）
    mmap_size = int(os.environ.get("SQLITE_MMAP_SIZE", "0"))
    conn.execute(f"PRAGMA mmap_size={mmap_size}")

    # ロックタイムアウト（NFSレイテンシを考慮）
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")

    # 外部キー制約を有効化
    conn.execute("PRAGMA foreign_keys=ON")

    # ロックモード: CephFS/NFSでは排他ロックモードが必要
    locking_mode = os.environ.get("SQLITE_LOCKING_MODE", "EXCLUSIVE")
    conn.execute(f"PRAGMA locking_mode={locking_mode}")

    conn.commit()
    logging.debug("SQLiteデータベースの接続設定を適用しました")


def cleanup_stale_files(db_path: pathlib.Path) -> None:
    """
    CephFS/NFS環境で残存するWAL/SHMファイルを削除する

    Podクラッシュ後などにこれらのファイルが残っていると
    「locking protocol」エラーが発生するため、接続前に削除する。

    Args:
        db_path: データベースファイルのパス
    """
    wal_path = db_path.with_suffix(db_path.suffix + "-wal")
    shm_path = db_path.with_suffix(db_path.suffix + "-shm")

    if wal_path.exists() or shm_path.exists():
        logging.warning("残存するWAL/SHMファイルを削除します: %s", db_path)
        with contextlib.suppress(Exception):
            wal_path.unlink(missing_ok=True)
        with contextlib.suppress(Exception):
            shm_path.unlink(missing_ok=True)


class DatabaseConnection:
    """SQLite接続をContext Managerとしても通常の関数としても使用可能にするラッパー"""

    def __init__(self, db_path: str | pathlib.Path, *, timeout: float = 60.0) -> None:
        """
        データベース接続の初期化

        Args:
            db_path: データベースファイルのパス
            timeout: データベース接続のタイムアウト時間（秒）
        """
        self.db_path = pathlib.Path(db_path)
        self.timeout = timeout
        self.conn: sqlite3.Connection | None = None

    def _acquire_lock(self, lock_file: Any) -> bool:
        """ロックの取得を試みる"""
        if os.environ.get("SQLITE_LOCK_MODE") == "NONBLOCK":
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                return False
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            return True

    def _get_connection_params(self) -> SQLiteConnectionParams:
        """SQLite接続パラメータを取得"""
        checkpoint_dir = os.environ.get("SQLITE_CHECKPOINT_DIR")
        if checkpoint_dir:
            pathlib.Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

        return SQLiteConnectionParams(
            timeout=self.timeout,
            check_same_thread=False,
            isolation_level="DEFERRED",
        )

    def _create_connection(self) -> sqlite3.Connection:
        """実際の接続処理"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        is_new_db = not self.db_path.exists()

        if is_new_db:
            # 新規作成時は排他制御を行う
            lock_path = self.db_path.with_suffix(".lock")
            max_retries = 5
            retry_count = 0

            while retry_count < max_retries:
                try:
                    with lock_path.open("w") as lock_file:
                        if not self._acquire_lock(lock_file):
                            retry_count += 1
                            time.sleep(0.1 * retry_count)
                            continue

                        try:
                            is_new_db = not self.db_path.exists()
                            params = self._get_connection_params()
                            self.conn = sqlite3.connect(
                                self.db_path,
                                timeout=params.timeout,
                                check_same_thread=params.check_same_thread,
                                isolation_level=params.isolation_level,
                            )

                            if is_new_db:
                                init_persistent(self.conn)
                                logging.info("新規SQLiteデータベースを作成しました: %s", self.db_path)
                            init_connection(self.conn, timeout=self.timeout)
                        finally:
                            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

                    with contextlib.suppress(Exception):
                        lock_path.unlink()
                    break

                except Exception:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logging.exception("データベース作成時のロック取得に失敗しました")
                        raise
                    time.sleep(0.1 * retry_count)
        else:
            # 既存のデータベースへの接続
            cleanup_stale_files(self.db_path)
            params = self._get_connection_params()
            self.conn = sqlite3.connect(
                self.db_path,
                timeout=params.timeout,
                check_same_thread=params.check_same_thread,
                isolation_level=params.isolation_level,
            )
            init_connection(self.conn, timeout=self.timeout)
            logging.debug("既存のSQLiteデータベースに接続しました: %s", self.db_path)

        assert self.conn is not None  # noqa: S101
        return self.conn

    def __enter__(self) -> sqlite3.Connection:
        """Context Manager として使用する場合のenter"""
        return self._create_connection()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> None:
        """Context Manager として使用する場合のexit"""
        if self.conn is not None:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def get(self) -> sqlite3.Connection:
        """通常の関数として使用する場合（使用後は必ずcloseすること）"""
        return self._create_connection()


def connect(db_path: str | pathlib.Path, *, timeout: float = 60.0) -> DatabaseConnection:
    """
    Kubernetes manual storage class環境に適したSQLiteデータベースに接続する

    Context Managerとしても通常の関数としても使用可能

    Args:
        db_path: データベースファイルのパス
        timeout: データベース接続のタイムアウト時間（秒）

    Returns:
        DatabaseConnection: Context Managerとしても通常の接続取得にも使用可能

    Usage:
        # Context Manager として使用
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("SELECT * FROM table")

        # 通常の関数として使用
        db_conn = my_lib.sqlite_util.connect(db_path)
        conn = db_conn.get()
        try:
            conn.execute("SELECT * FROM table")
        finally:
            conn.close()
    """
    return DatabaseConnection(db_path, timeout=timeout)


def recover(db_path: str | pathlib.Path) -> None:
    """データベースの復旧を試みる"""
    try:
        db_path = pathlib.Path(db_path)

        journal_mode = os.environ.get("SQLITE_JOURNAL_MODE", "WAL")

        if journal_mode == "WAL":
            wal_path = db_path.with_suffix(db_path.suffix + "-wal")
            shm_path = db_path.with_suffix(db_path.suffix + "-shm")

            if wal_path.exists():
                logging.warning("WALファイル %s を削除してデータベースを復旧します", wal_path)
                wal_path.unlink()

            if shm_path.exists():
                logging.warning("共有メモリファイル %s を削除します", shm_path)
                shm_path.unlink()
        else:
            journal_path = db_path.with_suffix(db_path.suffix + "-journal")
            if journal_path.exists():
                logging.warning("ジャーナルファイル %s を削除してデータベースを復旧します", journal_path)
                journal_path.unlink()

        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                raise sqlite3.DatabaseError(f"整合性チェック失敗: {result[0]}")

            conn.execute("PRAGMA quick_check")

            if os.environ.get("SQLITE_AUTO_VACUUM") == "1":
                logging.info("データベースのVACUUMを実行します")
                conn.execute("VACUUM")

            conn.close()
            logging.info("データベースの整合性チェックが成功しました")

        except sqlite3.Error:
            logging.exception("データベースの整合性チェックに失敗")
            backup_path = db_path.with_suffix(f".backup.{int(time.time())}")
            db_path.rename(backup_path)
            logging.warning("破損したデータベースを %s にバックアップし、新規作成します", backup_path)

    except OSError:
        logging.exception("データベース復旧中にエラーが発生")
