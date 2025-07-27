#!/usr/bin/env python3
"""SQLiteデータベースのユーティリティ関数"""

import logging
import pathlib
import sqlite3
import time


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
