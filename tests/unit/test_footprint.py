#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.footprint モジュールのユニットテスト
"""

from __future__ import annotations

import time


class TestExists:
    """exists 関数のテスト"""

    def test_returns_false_for_nonexistent_file(self, temp_dir):
        """存在しないファイルに対して False を返す"""
        import my_lib.footprint

        path = temp_dir / "nonexistent"
        assert not my_lib.footprint.exists(path)

    def test_returns_true_for_existing_file(self, temp_dir):
        """存在するファイルに対して True を返す"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        my_lib.footprint.update(path)
        assert my_lib.footprint.exists(path)


class TestUpdate:
    """update 関数のテスト"""

    def test_creates_file(self, temp_dir):
        """ファイルを作成する"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        assert not my_lib.footprint.exists(path)

        my_lib.footprint.update(path)
        assert my_lib.footprint.exists(path)

    def test_creates_parent_directories(self, temp_dir):
        """親ディレクトリも作成する"""
        import my_lib.footprint

        path = temp_dir / "subdir" / "footprint"
        my_lib.footprint.update(path)
        assert my_lib.footprint.exists(path)

    def test_updates_mtime(self, temp_dir):
        """mtime を更新する"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        test_time = 1234567890.0

        my_lib.footprint.update(path, mtime=test_time)
        assert my_lib.footprint.mtime(path) == test_time

    def test_uses_current_time_when_mtime_not_specified(self, temp_dir):
        """mtime が指定されていない場合は現在時刻を使用"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        before = time.time()
        my_lib.footprint.update(path)
        after = time.time()

        mtime = my_lib.footprint.mtime(path)
        assert before <= mtime <= after


class TestMtime:
    """mtime 関数のテスト"""

    def test_returns_stored_time(self, temp_dir):
        """保存された時刻を返す"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        expected_time = 1609459200.0  # 2021-01-01 00:00:00 UTC

        my_lib.footprint.update(path, mtime=expected_time)
        assert my_lib.footprint.mtime(path) == expected_time


class TestElapsed:
    """elapsed 関数のテスト"""

    def test_returns_large_value_for_nonexistent_file(self, temp_dir):
        """存在しないファイルに対して大きな値を返す"""
        import my_lib.footprint

        path = temp_dir / "nonexistent"
        elapsed = my_lib.footprint.elapsed(path)
        assert elapsed > 10000

    def test_returns_elapsed_seconds(self, temp_dir):
        """経過秒数を返す"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        my_lib.footprint.update(path)

        time.sleep(0.1)
        elapsed = my_lib.footprint.elapsed(path)
        assert 0.1 <= elapsed < 1.0


class TestCompare:
    """compare 関数のテスト"""

    def test_returns_true_when_a_is_newer(self, temp_dir):
        """a が新しい場合 True を返す"""
        import my_lib.footprint

        path_a = temp_dir / "a"
        path_b = temp_dir / "b"

        my_lib.footprint.update(path_b, mtime=1000.0)
        my_lib.footprint.update(path_a, mtime=2000.0)

        assert my_lib.footprint.compare(path_a, path_b)

    def test_returns_false_when_b_is_newer(self, temp_dir):
        """b が新しい場合 False を返す"""
        import my_lib.footprint

        path_a = temp_dir / "a"
        path_b = temp_dir / "b"

        my_lib.footprint.update(path_a, mtime=1000.0)
        my_lib.footprint.update(path_b, mtime=2000.0)

        assert not my_lib.footprint.compare(path_a, path_b)


class TestClear:
    """clear 関数のテスト"""

    def test_removes_file(self, temp_dir):
        """ファイルを削除する"""
        import my_lib.footprint

        path = temp_dir / "footprint"
        my_lib.footprint.update(path)
        assert my_lib.footprint.exists(path)

        my_lib.footprint.clear(path)
        assert not my_lib.footprint.exists(path)

    def test_does_not_raise_for_nonexistent_file(self, temp_dir):
        """存在しないファイルに対してエラーを発生させない"""
        import my_lib.footprint

        path = temp_dir / "nonexistent"
        # Should not raise
        my_lib.footprint.clear(path)
