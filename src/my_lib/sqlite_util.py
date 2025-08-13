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


@contextlib.contextmanager
def connect(db_path, *, timeout=30.0):
    """
    rook-cephfs環境に適したSQLiteデータベースに接続するContext Manager

    Args:
        db_path: データベースファイルのパス
        timeout: データベース接続のタイムアウト時間（秒）

    Yields:
        sqlite3.Connection: データベース接続

    Usage:
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("SELECT * FROM table")

    """
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # データベースファイルが存在しない場合のみ初期化を実行
    is_new_db = not db_path.exists()

    conn = None
    try:
        if is_new_db:
            # 新規作成時は排他制御を行う
            lock_path = db_path.with_suffix(".lock")
            # ロックファイルを使用して排他制御
            with lock_path.open("w") as lock_file:
                # 排他ロックを取得（他のプロセスがロックを保持している場合は待機）
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    # ロック取得後、再度存在確認（他のプロセスが作成済みの可能性）
                    is_new_db = not db_path.exists()

                    conn = sqlite3.connect(db_path, timeout=timeout)

                    if is_new_db:
                        init(conn, timeout=timeout)
                        logging.info("新規SQLiteデータベースを作成・初期化しました: %s", db_path)
                    else:
                        logging.debug("既存のSQLiteデータベースに接続しました（ロック待機後）: %s", db_path)
                finally:
                    # ロックを解放
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

            # ロックファイルを削除（エラーは無視）
            with contextlib.suppress(Exception):
                lock_path.unlink()
        else:
            # 既存のデータベースへの接続は排他制御不要
            conn = sqlite3.connect(db_path, timeout=timeout)
            logging.debug("既存のSQLiteデータベースに接続しました: %s", db_path)

        yield conn

    finally:
        if conn is not None:
            conn.close()


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
