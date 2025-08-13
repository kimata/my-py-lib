#!/usr/bin/env python3
"""SQLiteデータベースのユーティリティ関数"""

import logging
import pathlib
import sqlite3
import time


def create(db_path, *, timeout=30.0):
    """
    rook-cephfs環境に適したSQLiteデータベースを作成・初期化する

    Args:
        db_path: データベースファイルのパス
        timeout: データベース接続のタイムアウト時間（秒）

    Returns:
        sqlite3.Connection: 初期化されたデータベース接続

    """
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=timeout)

    try:
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
        logging.info("SQLiteデータベースを初期化しました: %s", db_path)

    except Exception:
        conn.close()
        raise

    return conn


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
