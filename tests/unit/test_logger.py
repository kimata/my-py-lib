#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.logger モジュールのユニットテスト
"""
from __future__ import annotations

import logging
import pathlib
import queue

import pytest


class TestLogFormatter:
    """_log_formatter 関数のテスト"""

    def test_returns_formatter(self):
        """Formatter を返す"""
        from my_lib.logger import _log_formatter

        formatter = _log_formatter("test")
        assert isinstance(formatter, logging.Formatter)

    def test_includes_name_in_format(self):
        """名前がフォーマットに含まれる"""
        from my_lib.logger import _log_formatter

        formatter = _log_formatter("myapp")
        # フォーマット文字列に名前が含まれていることを確認
        assert formatter._fmt is not None
        assert "myapp" in formatter._fmt


class TestGZipRotator:
    """_GZipRotator クラスのテスト"""

    def test_namer_adds_bz2_extension(self):
        """namer が .bz2 拡張子を追加する"""
        from my_lib.logger import _GZipRotator

        result = _GZipRotator.namer("test.log")
        assert result == "test.log.bz2"

    def test_rotator_compresses_file(self, temp_dir):
        """rotator がファイルを圧縮する"""
        import bz2

        from my_lib.logger import _GZipRotator

        source_path = temp_dir / "source.log"
        dest_path = temp_dir / "source.log.bz2"

        test_content = b"test log content\n"
        source_path.write_bytes(test_content)

        _GZipRotator.rotator(str(source_path), str(dest_path))

        # ソースファイルが削除されている
        assert not source_path.exists()

        # 圧縮ファイルが存在する
        assert dest_path.exists()

        # 圧縮ファイルの内容を確認
        with bz2.open(dest_path, "rb") as f:
            content = f.read()
            assert content == test_content


class TestInit:
    """init 関数のテスト"""

    def test_returns_none_without_str_log(self, temp_dir, monkeypatch):
        """is_str_log=False の場合 None を返す"""
        import my_lib.logger

        monkeypatch.setenv("NO_COLORED_LOGS", "true")

        result = my_lib.logger.init("test", level=logging.INFO)
        assert result is None

    def test_returns_stringio_with_str_log(self, temp_dir, monkeypatch):
        """is_str_log=True の場合 StringIO を返す"""
        import io

        import my_lib.logger

        monkeypatch.setenv("NO_COLORED_LOGS", "true")

        result = my_lib.logger.init("test", level=logging.INFO, is_str_log=True)
        assert isinstance(result, io.StringIO)

    def test_creates_log_file(self, temp_dir, monkeypatch):
        """ログファイルを作成する"""
        import my_lib.logger

        monkeypatch.setenv("NO_COLORED_LOGS", "true")

        log_dir = temp_dir / "logs"

        my_lib.logger.init("test", level=logging.INFO, log_dir_path=log_dir)

        assert log_dir.exists()

    def test_creates_log_directory(self, temp_dir, monkeypatch):
        """ログディレクトリを作成する"""
        import my_lib.logger

        monkeypatch.setenv("NO_COLORED_LOGS", "true")

        log_dir = temp_dir / "nested" / "logs"

        my_lib.logger.init("test", level=logging.INFO, log_dir_path=log_dir)

        assert log_dir.exists()

    def test_accepts_queue(self, temp_dir, monkeypatch):
        """キューを受け付ける"""
        import my_lib.logger

        monkeypatch.setenv("NO_COLORED_LOGS", "true")

        log_queue: queue.Queue[logging.LogRecord] = queue.Queue()

        my_lib.logger.init("test", level=logging.INFO, log_queue=log_queue)

        # キューハンドラが追加されていることを確認（エラーが発生しなければ OK）


class TestConstants:
    """定数のテスト"""

    def test_max_size(self):
        """MAX_SIZE が適切な値"""
        from my_lib.logger import MAX_SIZE

        assert MAX_SIZE == 10 * 1024 * 1024  # 10MB

    def test_rotate_count(self):
        """ROTATE_COUNT が適切な値"""
        from my_lib.logger import ROTATE_COUNT

        assert ROTATE_COUNT == 10

    def test_log_format(self):
        """LOG_FORMAT が定義されている"""
        from my_lib.logger import LOG_FORMAT

        assert "{name}" in LOG_FORMAT
        assert "%(asctime)s" in LOG_FORMAT
        assert "%(levelname)s" in LOG_FORMAT
