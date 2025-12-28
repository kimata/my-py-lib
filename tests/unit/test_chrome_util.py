#!/usr/bin/env python3
# ruff: noqa: S101
"""chrome_util.py のテスト"""
from __future__ import annotations

import pathlib
import time
import unittest.mock

import pytest

import my_lib.chrome_util


class TestCleanupOldChromeProfiles:
    """cleanup_old_chrome_profiles 関数のテスト"""

    def test_returns_empty_list_when_no_chrome_dir(self, temp_dir):
        """chrome ディレクトリがない場合は空のリストを返す"""
        result = my_lib.chrome_util.cleanup_old_chrome_profiles(temp_dir)
        assert result == []

    def test_returns_empty_list_when_chrome_dir_is_empty(self, temp_dir):
        """chrome ディレクトリが空の場合は空のリストを返す"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()

        result = my_lib.chrome_util.cleanup_old_chrome_profiles(temp_dir)
        assert result == []

    def test_keeps_default_profile(self, temp_dir):
        """Default プロファイルは削除しない"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()
        default_profile = chrome_dir / "Default"
        default_profile.mkdir()

        result = my_lib.chrome_util.cleanup_old_chrome_profiles(temp_dir)
        assert result == []
        assert default_profile.exists()

    def test_removes_old_profiles(self, temp_dir):
        """古いプロファイルを削除する"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()

        old_profile = chrome_dir / "Profile_Old"
        old_profile.mkdir()

        old_time = time.time() - (48 * 3600)
        import os

        os.utime(old_profile, (old_time, old_time))

        result = my_lib.chrome_util.cleanup_old_chrome_profiles(temp_dir, max_age_hours=24, keep_count=0)

        assert len(result) == 1
        assert not old_profile.exists()

    def test_keeps_minimum_profiles_by_count(self, temp_dir):
        """keep_count 以上のプロファイルを削除する"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()

        import time as time_module

        # 5つのプロファイルを作成し、順番に異なる時刻を設定
        for i in range(5):
            profile = chrome_dir / f"Profile_{i}"
            profile.mkdir()
            # 古いものから順に作成時刻を設定
            old_time = time_module.time() - (100 * 3600) + (i * 3600)
            import os

            os.utime(profile, (old_time, old_time))

        # max_age_hours を大きくして、時間による削除を無効化
        # keep_count=3 で、古い順に2つが削除される
        result = my_lib.chrome_util.cleanup_old_chrome_profiles(temp_dir, max_age_hours=1000, keep_count=3)

        remaining = list(chrome_dir.iterdir())
        assert len(remaining) == 3
        assert len(result) == 2

    def test_handles_oserror_on_stat(self, temp_dir):
        """stat でエラーが発生しても続行する"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()

        profile = chrome_dir / "Profile_Test"
        profile.mkdir()

        # プロファイルディレクトリの stat.st_mtime アクセス時にエラーを発生させる
        # is_dir() は正常に動作させる必要がある
        original_stat = pathlib.Path.stat
        call_count = {}

        def mock_stat(self, *args, **kwargs):
            path_str = str(self)
            if "Profile_Test" in path_str:
                # is_dir() で1回目、st_mtime で2回目
                call_count[path_str] = call_count.get(path_str, 0) + 1
                if call_count[path_str] > 1:
                    raise OSError("Mocked OSError")
            return original_stat(self, *args, **kwargs)

        with unittest.mock.patch.object(pathlib.Path, "stat", mock_stat):
            result = my_lib.chrome_util.cleanup_old_chrome_profiles(temp_dir)

        # OSError が発生したプロファイルはスキップされる
        assert result == []


class TestGetChromeProfileStats:
    """get_chrome_profile_stats 関数のテスト"""

    def test_returns_zero_when_no_chrome_dir(self, temp_dir):
        """chrome ディレクトリがない場合はゼロを返す"""
        result = my_lib.chrome_util.get_chrome_profile_stats(temp_dir)

        assert result["total_count"] == 0
        assert result["total_size_mb"] == 0

    def test_counts_profiles(self, temp_dir):
        """プロファイルをカウントする"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()

        for i in range(3):
            profile = chrome_dir / f"Profile_{i}"
            profile.mkdir()

        result = my_lib.chrome_util.get_chrome_profile_stats(temp_dir)

        assert result["total_count"] == 3

    def test_calculates_size(self, temp_dir):
        """サイズを計算する"""
        chrome_dir = temp_dir / "chrome"
        chrome_dir.mkdir()

        profile = chrome_dir / "Profile_Test"
        profile.mkdir()

        # 1MB以上のファイルを作成して、丸め誤差を回避
        test_file = profile / "test.txt"
        test_file.write_text("x" * (1024 * 1024 + 1))

        result = my_lib.chrome_util.get_chrome_profile_stats(temp_dir)

        assert result["total_size_mb"] >= 1.0


class TestCleanupOrphanedChromeProcesses:
    """cleanup_orphaned_chrome_processes 関数のテスト"""

    def test_runs_without_error(self):
        """エラーなく実行できる"""
        # psutil があれば正常に動作することを確認
        my_lib.chrome_util.cleanup_orphaned_chrome_processes()

    def test_handles_import_error(self):
        """ImportError を処理する"""
        # モジュールキャッシュを一時的にクリアして ImportError を発生させる
        import importlib
        import sys

        # psutil を一時的にアンロード
        psutil_backup = sys.modules.get("psutil")
        if "psutil" in sys.modules:
            del sys.modules["psutil"]

        try:
            # builtins.__import__ をモックして ImportError を発生させる
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "psutil":
                    raise ImportError("Mocked: No module named 'psutil'")
                return original_import(name, *args, **kwargs)

            builtins.__import__ = mock_import
            try:
                # ImportError が発生しても例外にならないことを確認
                my_lib.chrome_util.cleanup_orphaned_chrome_processes()
            finally:
                builtins.__import__ = original_import
        finally:
            # psutil を復元
            if psutil_backup is not None:
                sys.modules["psutil"] = psutil_backup

    def test_finds_chrome_processes(self):
        """Chrome プロセスを検出する"""
        import psutil

        mock_proc = unittest.mock.MagicMock()
        mock_proc.info = {
            "pid": 12345,
            "name": "chrome",
            "cmdline": ["chrome"],
            "ppid": 1,
            "status": psutil.STATUS_RUNNING,
        }
        mock_proc.parent.return_value = unittest.mock.MagicMock()
        mock_proc.parent.return_value.is_running.return_value = True

        with unittest.mock.patch("psutil.process_iter", return_value=[mock_proc]):
            my_lib.chrome_util.cleanup_orphaned_chrome_processes()

    def test_terminates_orphaned_processes(self):
        """孤立したプロセスを終了する"""
        import psutil

        mock_proc = unittest.mock.MagicMock()
        mock_proc.info = {
            "pid": 12345,
            "name": "chrome",
            "cmdline": ["chrome"],
            "ppid": 1,
            "status": psutil.STATUS_RUNNING,
        }
        mock_proc.parent.return_value = None

        with unittest.mock.patch("psutil.process_iter", return_value=[mock_proc]):
            with unittest.mock.patch.object(my_lib.chrome_util, "_cleanup_chrome_process_groups"):
                my_lib.chrome_util.cleanup_orphaned_chrome_processes()

        mock_proc.terminate.assert_called_once()


class TestCleanupChromeProcessGroups:
    """_cleanup_chrome_process_groups 関数のテスト"""

    def test_skips_when_pkill_not_available(self):
        """pkill がない場合はスキップする"""
        with unittest.mock.patch("shutil.which", return_value=None):
            my_lib.chrome_util._cleanup_chrome_process_groups()

    def test_runs_pkill_when_available(self):
        """pkill が利用可能な場合は実行する"""
        with unittest.mock.patch("shutil.which", return_value="/usr/bin/pkill"):
            with unittest.mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = unittest.mock.MagicMock(returncode=0)

                my_lib.chrome_util._cleanup_chrome_process_groups()

                assert mock_run.call_count >= 1

    def test_handles_timeout(self):
        """タイムアウトを処理する"""
        import subprocess

        with unittest.mock.patch("shutil.which", return_value="/usr/bin/pkill"):
            with unittest.mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pkill", 5)):
                my_lib.chrome_util._cleanup_chrome_process_groups()

    def test_handles_file_not_found(self):
        """FileNotFoundError を処理する"""
        with unittest.mock.patch("shutil.which", return_value="/usr/bin/pkill"):
            with unittest.mock.patch("subprocess.run", side_effect=FileNotFoundError):
                my_lib.chrome_util._cleanup_chrome_process_groups()

    def test_handles_generic_exception(self):
        """一般的な例外を処理する"""
        with unittest.mock.patch("shutil.which", return_value="/usr/bin/pkill"):
            with unittest.mock.patch("subprocess.run", side_effect=RuntimeError("Test error")):
                my_lib.chrome_util._cleanup_chrome_process_groups()
