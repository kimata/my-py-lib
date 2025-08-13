#!/usr/bin/env python3
"""SQLiteデータベースのユーティリティ関数"""

import contextlib
import fcntl
import logging
import pathlib
import sqlite3
import time


def init(conn, *, timeout=30.0):
    """
    SQLiteデータベースのテーブル設定を初期化する

    Args:
        conn: SQLiteデータベース接続
        timeout: データベース接続のタイムアウト時間（秒）

    """
    # rook-cephfsに最適化されたPRAGMA設定
    # WALモードでファイルロックの競合を減らす
    conn.execute("PRAGMA journal_mode=WAL")

    # 同期モードをNORMALに設定（FULLより高速で十分な安全性）
    conn.execute("PRAGMA synchronous=NORMAL")

    # ページサイズを大きくしてI/O効率を向上（cephfsのブロックサイズに合わせる）
    conn.execute("PRAGMA page_size=8192")

    # WALの自動チェックポイント間隔を調整（デフォルト1000から）
    conn.execute("PRAGMA wal_autocheckpoint=2000")

    # キャッシュサイズを増やしてディスクI/Oを削減（ページ数で指定）
    conn.execute("PRAGMA cache_size=-64000")  # 約64MB（負値はKB単位）

    # テンポラリストレージをメモリに設定してcephfsへの書き込みを削減
    conn.execute("PRAGMA temp_store=MEMORY")

    # mmapサイズを設定してパフォーマンスを向上
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB

    # ロックタイムアウトを設定
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")

    # 外部キー制約を有効化（データ整合性のため）
    conn.execute("PRAGMA foreign_keys=ON")

    conn.commit()
    logging.info("SQLiteデータベースのテーブル設定を初期化しました")


class DatabaseConnection:
    """SQLite接続をContext Managerとしても通常の関数としても使用可能にするラッパー"""

    def __init__(self, db_path, *, timeout=30.0):
        """
        データベース接続の初期化

        Args:
            db_path: データベースファイルのパス
            timeout: データベース接続のタイムアウト時間（秒）

        """
        self.db_path = pathlib.Path(db_path)
        self.timeout = timeout
        self.conn = None

    def _create_connection(self):
        """実際の接続処理"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # データベースファイルが存在しない場合のみ初期化を実行
        is_new_db = not self.db_path.exists()

        if is_new_db:
            # 新規作成時は排他制御を行う
            lock_path = self.db_path.with_suffix(".lock")
            # ロックファイルを使用して排他制御
            with lock_path.open("w") as lock_file:
                # 排他ロックを取得（他のプロセスがロックを保持している場合は待機）
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    # ロック取得後、再度存在確認（他のプロセスが作成済みの可能性）
                    is_new_db = not self.db_path.exists()

                    self.conn = sqlite3.connect(self.db_path, timeout=self.timeout)

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
        else:
            # 既存のデータベースへの接続は排他制御不要
            self.conn = sqlite3.connect(self.db_path, timeout=self.timeout)
            logging.debug("既存のSQLiteデータベースに接続しました: %s", self.db_path)

        return self.conn

    def __enter__(self):
        """Context Manager として使用する場合のenter"""
        return self._create_connection()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager として使用する場合のexit"""
        if self.conn is not None:
            self.conn.close()

    def get(self):
        """通常の関数として使用する場合（使用後は必ずcloseすること）"""
        return self._create_connection()


def connect(db_path, *, timeout=30.0):
    """
    rook-cephfs環境に適したSQLiteデータベースに接続する

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


def recover(db_path):
    """データベースの復旧を試みる"""
    try:
        # WALファイルのパスを取得
        wal_path = pathlib.Path(str(db_path) + "-wal")
        shm_path = pathlib.Path(str(db_path) + "-shm")

        # WALファイルが存在する場合は削除（最後のチェックポイントまでロールバック）
        if wal_path.exists():
            logging.warning("WALファイル %s を削除してデータベースを復旧します", wal_path)
            wal_path.unlink()

        if shm_path.exists():
            logging.warning("共有メモリファイル %s を削除します", shm_path)
            shm_path.unlink()

        # データベースの整合性チェック
        try:
            conn = sqlite3.connect(db_path, timeout=1.0)
            conn.execute("PRAGMA integrity_check")
            conn.close()
            logging.info("データベースの整合性チェックが成功しました")
        except Exception:
            logging.exception("データベースの整合性チェックに失敗")
            # 最後の手段としてデータベースを再作成
            backup_path = pathlib.Path(str(db_path) + f".backup.{int(time.time())}")
            db_path.rename(backup_path)
            logging.warning("破損したデータベースを %s にバックアップし、新規作成します", backup_path)

    except Exception:
        logging.exception("データベース復旧中にエラーが発生")
