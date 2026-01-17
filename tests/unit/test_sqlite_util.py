#!/usr/bin/env python3
# ruff: noqa: S101, SIM117
"""
my_lib.sqlite_util モジュールのユニットテスト
"""

from __future__ import annotations

import pathlib
import sqlite3
import threading

import pytest


class TestConnect:
    """connect 関数のテスト"""

    def test_creates_database_file(self, temp_dir):
        """データベースファイルを作成する"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"
        assert not db_path.exists()

        db_conn = my_lib.sqlite_util.connect(db_path)
        conn = db_conn.get()
        conn.close()

        assert db_path.exists()

    def test_returns_database_connection_object(self, temp_dir):
        """DatabaseConnection オブジェクトを返す"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"
        result = my_lib.sqlite_util.connect(db_path)

        assert isinstance(result, my_lib.sqlite_util.DatabaseConnection)

    def test_can_use_as_context_manager(self, temp_dir):
        """コンテキストマネージャとして使用できる"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"

        with my_lib.sqlite_util.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_can_use_get_method(self, temp_dir):
        """get メソッドで接続を取得できる"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"
        db_conn = my_lib.sqlite_util.connect(db_path)
        conn = db_conn.get()

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
        finally:
            conn.close()


class TestDatabaseConnection:
    """DatabaseConnection クラスのテスト"""

    def test_creates_parent_directories(self, temp_dir):
        """親ディレクトリを作成する"""
        import my_lib.sqlite_util

        db_path = temp_dir / "subdir" / "test.db"
        db_conn = my_lib.sqlite_util.connect(db_path)
        conn = db_conn.get()
        conn.close()

        assert db_path.exists()

    def test_commits_on_successful_exit(self, temp_dir):
        """正常終了時にコミットする"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"

        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

        # 再接続してデータが存在することを確認
        with my_lib.sqlite_util.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_rollbacks_on_exception(self, temp_dir):
        """例外発生時にロールバックする"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"

        # まずテーブルを作成
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")

        # 例外を発生させる
        try:
            with my_lib.sqlite_util.connect(db_path) as conn:
                conn.execute("INSERT INTO test VALUES (1)")
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # データがロールバックされていることを確認
        with my_lib.sqlite_util.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test")
            result = cursor.fetchone()
            assert result[0] == 0


class TestConcurrentAccess:
    """並行アクセスのテスト"""

    def test_multiple_threads_can_connect(self, temp_dir):
        """複数スレッドから接続できる"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"
        results = {}

        def worker(worker_id: int) -> None:
            try:
                db_conn = my_lib.sqlite_util.connect(db_path)
                conn = db_conn.get()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                conn.close()
                results[worker_id] = {"success": True, "value": result[0]}
            except Exception as e:
                results[worker_id] = {"success": False, "error": str(e)}

        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # 全てのスレッドが成功したことを確認
        for worker_id, result in results.items():
            assert result["success"], f"Worker {worker_id} failed: {result.get('error')}"


class TestInit:
    """init 関数のテスト"""

    def test_sets_pragmas(self, temp_dir):
        """PRAGMA 設定を行う"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test.db"
        conn = sqlite3.connect(db_path)
        my_lib.sqlite_util.init_connection(conn)

        # synchronous が FULL に設定されていることを確認
        cursor = conn.cursor()
        cursor.execute("PRAGMA synchronous")
        result = cursor.fetchone()
        # FULL = 2
        assert result[0] == 2

        conn.close()

    def test_wal_mode_settings(self, temp_dir, monkeypatch):
        """WALモード時の設定"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_JOURNAL_MODE", "WAL")

        db_path = temp_dir / "test_wal.db"
        conn = sqlite3.connect(db_path)
        my_lib.sqlite_util.init_persistent(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        assert result[0].upper() == "WAL"

        conn.close()

    def test_delete_mode_settings(self, temp_dir, monkeypatch):
        """DELETEモード時の設定（WAL以外）"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_JOURNAL_MODE", "DELETE")

        db_path = temp_dir / "test_delete.db"
        conn = sqlite3.connect(db_path)
        my_lib.sqlite_util.init_persistent(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        assert result[0].upper() == "DELETE"

        conn.close()

    def test_exclusive_locking_mode(self, temp_dir, monkeypatch):
        """排他ロックモードの設定"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_LOCKING_MODE", "EXCLUSIVE")

        db_path = temp_dir / "test_exclusive.db"
        conn = sqlite3.connect(db_path)
        my_lib.sqlite_util.init_connection(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA locking_mode")
        result = cursor.fetchone()
        assert result[0].upper() == "EXCLUSIVE"

        conn.close()

    def test_mmap_size_setting(self, temp_dir, monkeypatch):
        """mmapサイズの設定"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_MMAP_SIZE", "1048576")  # 1MB

        db_path = temp_dir / "test_mmap.db"
        conn = sqlite3.connect(db_path)
        my_lib.sqlite_util.init_connection(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA mmap_size")
        result = cursor.fetchone()
        assert result[0] == 1048576

        conn.close()


class TestConnectionParams:
    """接続パラメータのテスト"""

    def test_checkpoint_dir_creates_directory(self, temp_dir, monkeypatch):
        """SQLITE_CHECKPOINT_DIR が設定されている場合ディレクトリを作成"""
        import my_lib.sqlite_util

        checkpoint_dir = temp_dir / "checkpoint"
        monkeypatch.setenv("SQLITE_CHECKPOINT_DIR", str(checkpoint_dir))

        db_path = temp_dir / "test.db"
        db_conn = my_lib.sqlite_util.DatabaseConnection(db_path)
        params = db_conn._get_connection_params()

        assert checkpoint_dir.exists()
        assert "timeout" in params


class TestNonBlockLocking:
    """NONBLOCKロックモードのテスト"""

    def test_nonblock_lock_mode_success(self, temp_dir, monkeypatch):
        """NONBLOCKモードでロック成功"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_LOCK_MODE", "NONBLOCK")

        db_path = temp_dir / "test_nonblock.db"
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("SELECT 1")

        assert db_path.exists()

    def test_nonblock_lock_retry(self, temp_dir, monkeypatch, mocker):
        """NONBLOCKモードでロック失敗時のリトライ"""
        import fcntl

        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_LOCK_MODE", "NONBLOCK")

        db_path = temp_dir / "test_nonblock_retry.db"

        # 最初の2回はBlockingIOError、3回目は成功
        call_count = [0]
        original_flock = fcntl.flock

        def mock_flock(fd, op):
            call_count[0] += 1
            if call_count[0] <= 2 and (op & fcntl.LOCK_NB):
                raise BlockingIOError("Resource temporarily unavailable")
            return original_flock(fd, op)

        mocker.patch("fcntl.flock", side_effect=mock_flock)

        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("SELECT 1")

        assert call_count[0] >= 2


class TestLockingExceptionHandling:
    """ロック取得時の例外ハンドリングのテスト"""

    def test_lock_exception_retry(self, temp_dir, mocker):
        """ロック取得時に例外が発生した場合のリトライ"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test_exception.db"

        # open をモックして例外を発生させる
        call_count = [0]
        original_open = pathlib.Path.open

        def mock_open(self, *args, **kwargs):
            if str(self).endswith(".lock"):
                call_count[0] += 1
                if call_count[0] <= 2:
                    raise OSError("Mock lock error")
            return original_open(self, *args, **kwargs)

        mocker.patch.object(pathlib.Path, "open", mock_open)

        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("SELECT 1")

        assert call_count[0] >= 2


class TestRecover:
    """recover 関数のテスト"""

    def test_recover_wal_mode(self, temp_dir, monkeypatch):
        """WALモードでの復旧"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_JOURNAL_MODE", "WAL")

        # データベースを作成
        db_path = temp_dir / "test_recover_wal.db"
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

        # WALファイルを手動で作成（テスト用）
        wal_path = db_path.with_suffix(db_path.suffix + "-wal")
        shm_path = db_path.with_suffix(db_path.suffix + "-shm")
        wal_path.touch()
        shm_path.touch()

        # 復旧を実行
        my_lib.sqlite_util.recover(db_path)

        # WAL/SHMファイルが削除されていることを確認
        assert not wal_path.exists()
        assert not shm_path.exists()

    def test_recover_delete_mode(self, temp_dir, monkeypatch):
        """DELETEモードでの復旧"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_JOURNAL_MODE", "DELETE")

        # データベースを作成
        db_path = temp_dir / "test_recover_delete.db"
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")

        # ジャーナルファイルを手動で作成（テスト用）
        journal_path = db_path.with_suffix(db_path.suffix + "-journal")
        journal_path.touch()

        # 復旧を実行
        my_lib.sqlite_util.recover(db_path)

        # ジャーナルファイルが削除されていることを確認
        assert not journal_path.exists()

    def test_recover_with_vacuum(self, temp_dir, monkeypatch):
        """VACUUM実行付きの復旧"""
        import my_lib.sqlite_util

        monkeypatch.setenv("SQLITE_AUTO_VACUUM", "1")

        # データベースを作成
        db_path = temp_dir / "test_recover_vacuum.db"
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

        # 復旧を実行
        my_lib.sqlite_util.recover(db_path)

        # データベースが正常に動作することを確認
        with my_lib.sqlite_util.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_recover_corrupted_database(self, temp_dir, mocker):
        """破損したデータベースの復旧"""
        import my_lib.sqlite_util

        # データベースを作成
        db_path = temp_dir / "test_corrupted.db"
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")

        # integrity_check を失敗させる
        mocker.patch("sqlite3.connect", side_effect=sqlite3.DatabaseError("database is corrupted"))

        # 復旧を実行（例外をキャッチして backup が作成される）
        my_lib.sqlite_util.recover(db_path)

        # バックアップファイルが作成されていることを確認
        backup_files = list(temp_dir.glob("*.backup.*"))
        assert len(backup_files) == 1

    def test_recover_general_exception(self, temp_dir, mocker):
        """復旧中の一般的な例外ハンドリング"""
        import my_lib.sqlite_util

        # 存在しないパスで復旧を実行
        db_path = temp_dir / "nonexistent" / "test.db"

        # 例外が発生しても処理が継続することを確認
        my_lib.sqlite_util.recover(db_path)


class TestExistingDatabaseReconnection:
    """既存データベースへの再接続テスト"""

    def test_reconnect_to_existing_db(self, temp_dir):
        """既存のデータベースに再接続"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test_reconnect.db"

        # 最初の接続でデータベースを作成
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (42)")

        # 2回目の接続（既存データベースへの接続）
        with my_lib.sqlite_util.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test")
            result = cursor.fetchone()
            assert result[0] == 42


class TestMaxRetriesExceeded:
    """最大リトライ回数超過のテスト"""

    def test_lock_max_retries_exceeded(self, temp_dir, mocker):
        """最大リトライ回数を超えた場合の例外"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test_max_retries.db"

        # 常に例外を発生させる
        mocker.patch.object(pathlib.Path, "open", side_effect=OSError("Mock lock error"))

        # リトライ上限を超えると例外が発生
        with pytest.raises(OSError, match="Mock lock error"):
            with my_lib.sqlite_util.connect(db_path) as conn:
                conn.execute("SELECT 1")


class TestIntegrityCheckFailure:
    """整合性チェック失敗のテスト"""

    def test_integrity_check_not_ok(self, temp_dir, mocker):
        """整合性チェックが "ok" 以外を返す場合"""
        import my_lib.sqlite_util

        # データベースを作成
        db_path = temp_dir / "test_integrity.db"
        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")

        # integrity_check が "ok" 以外を返すようにモック
        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = ("data corruption detected",)
        mock_conn.execute.return_value = mock_cursor

        mocker.patch("sqlite3.connect", return_value=mock_conn)

        # 復旧を実行（整合性チェック失敗でバックアップ作成）
        my_lib.sqlite_util.recover(db_path)

        # バックアップファイルが作成されていることを確認
        backup_files = list(temp_dir.glob("*.backup.*"))
        assert len(backup_files) == 1


class TestExitMethod:
    """__exit__ メソッドのテスト"""

    def test_exit_with_none_connection(self, temp_dir):
        """conn が None の場合の __exit__"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test_exit_none.db"
        db_conn = my_lib.sqlite_util.DatabaseConnection(db_path)

        # conn が None の状態で __exit__ を呼ぶ
        db_conn.__exit__(None, None, None)  # エラーにならない

    def test_exit_with_connection(self, temp_dir):
        """conn がある場合の __exit__"""
        import my_lib.sqlite_util

        db_path = temp_dir / "test_exit_conn.db"

        with my_lib.sqlite_util.connect(db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            # context manager の __exit__ が呼ばれる
