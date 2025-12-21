#!/usr/bin/env python3
"""SQLiteデータベースのユーティリティ関数

Kubernetes manual storage class（ローカルストレージ/NFS）環境に最適化。

環境変数による設定:
    SQLITE_JOURNAL_MODE: ジャーナルモード (WAL/DELETE/TRUNCATE/PERSIST) デフォルト: WAL
    SQLITE_MMAP_SIZE: mmapサイズ（バイト単位、0で無効化）デフォルト: 0
    SQLITE_LOCKING_MODE: ロックモード (NORMAL/EXCLUSIVE) デフォルト: NORMAL
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
from typing import Any


def init(conn: sqlite3.Connection, *, timeout: float = 60.0) -> None:
    """
    SQLiteデータベースのテーブル設定を初期化する

    Args:
        conn: SQLiteデータベース接続
        timeout: データベース接続のタイムアウト時間（秒）

    """
    # Kubernetes manual storage class（ローカルストレージ/NFS）に最適化されたPRAGMA設定

    # ジャーナルモード: WALモードはNFSでも動作するが、DELETEモードの方が安全な場合もある
    # NFSでのファイルロック問題を回避するため、環境に応じて選択可能にする
    journal_mode = os.environ.get("SQLITE_JOURNAL_MODE", "WAL")
    conn.execute(f"PRAGMA journal_mode={journal_mode}")

    # 同期モード: NFSやローカルストレージではFULLが最も安全
    # データ整合性を優先（特にNFSの場合）
    conn.execute("PRAGMA synchronous=FULL")

    # ページサイズ: 標準的な4096バイトを使用（ほとんどのファイルシステムで最適）
    conn.execute("PRAGMA page_size=4096")

    # WALモード使用時の設定
    if journal_mode == "WAL":
        # WALの自動チェックポイント間隔（デフォルト1000）
        conn.execute("PRAGMA wal_autocheckpoint=1000")

        # WALファイルの最大サイズを制限（NFSでの巨大ファイル転送を避ける）
        conn.execute("PRAGMA journal_size_limit=67108864")  # 64MB

    # キャッシュサイズ: 控えめに設定（Pod のメモリ制限を考慮）
    conn.execute("PRAGMA cache_size=-32000")  # 約32MB（負値はKB単位）

    # テンポラリストレージをメモリに設定（ディスクI/Oを削減）
    conn.execute("PRAGMA temp_store=MEMORY")

    # mmapサイズ: NFSでは無効化または小さく設定（0で無効化）
    # NFSでのmmapは問題を起こす可能性があるため
    mmap_size = int(os.environ.get("SQLITE_MMAP_SIZE", "0"))
    conn.execute(f"PRAGMA mmap_size={mmap_size}")

    # ロックタイムアウトを長めに設定（NFSレイテンシを考慮）
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")

    # 外部キー制約を有効化（データ整合性のため）
    conn.execute("PRAGMA foreign_keys=ON")

    # ロックモード: NFSでは排他ロックモードが推奨される場合がある
    locking_mode = os.environ.get("SQLITE_LOCKING_MODE", "NORMAL")
    if locking_mode == "EXCLUSIVE":
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")

    conn.commit()
    logging.info("SQLiteデータベースのテーブル設定を初期化しました")


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
            # 通常の排他ロック（ブロッキング）
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            return True

    def _get_connection_params(self) -> dict[str, Any]:
        """SQLite接続パラメータを取得"""
        params: dict[str, Any] = {
            "timeout": self.timeout,
            "check_same_thread": False,
            "isolation_level": "DEFERRED",
        }

        # NFSキャッシュ対策: checkpointディレクトリが使われる場合の設定
        checkpoint_dir = os.environ.get("SQLITE_CHECKPOINT_DIR")
        if checkpoint_dir:
            pathlib.Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

        return params

    def _create_connection(self) -> sqlite3.Connection:
        """実際の接続処理"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # データベースファイルが存在しない場合のみ初期化を実行
        is_new_db = not self.db_path.exists()

        if is_new_db:
            # 新規作成時は排他制御を行う
            lock_path = self.db_path.with_suffix(".lock")
            max_retries = 5
            retry_count = 0

            while retry_count < max_retries:
                try:
                    # ロックファイルを使用して排他制御
                    with lock_path.open("w") as lock_file:
                        if not self._acquire_lock(lock_file):
                            retry_count += 1
                            time.sleep(0.1 * retry_count)  # 指数バックオフ
                            continue

                        try:
                            # ロック取得後、再度存在確認（他のプロセスが作成済みの可能性）
                            is_new_db = not self.db_path.exists()
                            self.conn = sqlite3.connect(self.db_path, **self._get_connection_params())

                            if is_new_db:
                                init(self.conn, timeout=self.timeout)
                                logging.info("新規SQLiteデータベースを作成・初期化しました: %s", self.db_path)
                            else:
                                logging.debug(
                                    "既存のSQLiteデータベースに接続しました（ロック待機後）: %s", self.db_path
                                )
                        finally:
                            # ロックを解放
                            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

                    # ロックファイルを削除（エラーは無視）
                    with contextlib.suppress(Exception):
                        lock_path.unlink()
                    break  # 成功したらループを抜ける

                except Exception:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logging.exception("データベース作成時のロック取得に失敗しました")
                        raise
                    time.sleep(0.1 * retry_count)
        else:
            # 既存のデータベースへの接続
            self.conn = sqlite3.connect(self.db_path, **self._get_connection_params())
            logging.debug("既存のSQLiteデータベースに接続しました: %s", self.db_path)

        assert self.conn is not None
        return self.conn

    def __enter__(self) -> sqlite3.Connection:
        """Context Manager として使用する場合のenter"""
        return self._create_connection()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context Manager として使用する場合のexit"""
        if self.conn is not None:
            if exc_type is None:
                self.conn.commit()  # 正常終了時はコミット
            else:
                self.conn.rollback()  # 例外発生時はロールバック
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

        # ジャーナルファイルのパスを取得
        journal_mode = os.environ.get("SQLITE_JOURNAL_MODE", "WAL")

        if journal_mode == "WAL":
            # WALモードの場合
            wal_path = db_path.with_suffix(db_path.suffix + "-wal")
            shm_path = db_path.with_suffix(db_path.suffix + "-shm")

            if wal_path.exists():
                logging.warning("WALファイル %s を削除してデータベースを復旧します", wal_path)
                wal_path.unlink()

            if shm_path.exists():
                logging.warning("共有メモリファイル %s を削除します", shm_path)
                shm_path.unlink()
        else:
            # その他のジャーナルモードの場合
            journal_path = db_path.with_suffix(db_path.suffix + "-journal")
            if journal_path.exists():
                logging.warning("ジャーナルファイル %s を削除してデータベースを復旧します", journal_path)
                journal_path.unlink()

        # データベースの整合性チェック
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                raise sqlite3.DatabaseError(f"整合性チェック失敗: {result[0]}")

            # 追加のチェック: quick_check（より高速）
            conn.execute("PRAGMA quick_check")

            # VACUUM実行（データベースの最適化と修復）
            if os.environ.get("SQLITE_AUTO_VACUUM") == "1":
                logging.info("データベースのVACUUMを実行します")
                conn.execute("VACUUM")

            conn.close()
            logging.info("データベースの整合性チェックが成功しました")

        except Exception:
            logging.exception("データベースの整合性チェックに失敗")
            # 最後の手段としてデータベースを再作成
            backup_path = db_path.with_suffix(f".backup.{int(time.time())}")
            db_path.rename(backup_path)
            logging.warning("破損したデータベースを %s にバックアップし、新規作成します", backup_path)

    except Exception:
        logging.exception("データベース復旧中にエラーが発生")
