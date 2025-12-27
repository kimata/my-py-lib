#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.serializer モジュールのユニットテスト
"""
from __future__ import annotations

import pathlib

import pytest


class TestStore:
    """store 関数のテスト"""

    def test_stores_data(self, temp_dir):
        """データを保存する"""
        from my_lib.serializer import load, store

        file_path = temp_dir / "test.pkl"
        data = {"key": "value", "number": 42}

        store(file_path, data)

        assert file_path.exists()

    def test_creates_parent_directories(self, temp_dir):
        """親ディレクトリを作成する"""
        from my_lib.serializer import store

        file_path = temp_dir / "subdir" / "test.pkl"

        store(file_path, {"key": "value"})

        assert file_path.exists()

    def test_creates_backup_on_overwrite(self, temp_dir):
        """上書き時にバックアップを作成する"""
        from my_lib.serializer import store

        file_path = temp_dir / "test.pkl"

        store(file_path, {"first": 1})
        store(file_path, {"second": 2})

        old_path = file_path.with_suffix(".old")
        assert old_path.exists()


class TestLoad:
    """load 関数のテスト"""

    def test_loads_stored_data(self, temp_dir):
        """保存されたデータを読み込む"""
        from my_lib.serializer import load, store

        file_path = temp_dir / "test.pkl"
        data = {"key": "value", "number": 42}

        store(file_path, data)
        result = load(file_path)

        assert result == data

    def test_returns_empty_dict_for_nonexistent_file(self, temp_dir):
        """存在しないファイルは空辞書を返す"""
        from my_lib.serializer import load

        result = load(temp_dir / "nonexistent.pkl")

        assert result == {}

    def test_returns_init_value_for_nonexistent_file(self, temp_dir):
        """存在しないファイルは init_value を返す"""
        from my_lib.serializer import load

        init = {"default": "value"}
        result = load(temp_dir / "nonexistent.pkl", init)

        assert result == init

    def test_merges_dict_with_stored_data(self, temp_dir):
        """辞書の場合は保存データとマージする"""
        from my_lib.serializer import load, store

        file_path = temp_dir / "test.pkl"
        store(file_path, {"stored_key": "stored_value"})

        init = {"default_key": "default_value"}
        result = load(file_path, init)

        assert result["stored_key"] == "stored_value"
        assert result["default_key"] == "default_value"

    def test_loads_non_dict_data(self, temp_dir):
        """辞書以外のデータも読み込める"""
        from my_lib.serializer import load, store

        file_path = temp_dir / "test.pkl"
        data = [1, 2, 3, 4, 5]

        store(file_path, data)
        result: list[int] = load(file_path, [])

        assert result == data


class TestGetSizeStr:
    """get_size_str 関数のテスト"""

    def test_returns_bytes(self, temp_dir):
        """バイト単位を返す"""
        from my_lib.serializer import get_size_str, store

        file_path = temp_dir / "test.pkl"
        store(file_path, "small")

        result = get_size_str(file_path)
        assert "B" in result

    def test_returns_kilobytes(self, temp_dir):
        """キロバイト単位を返す"""
        from my_lib.serializer import get_size_str, store

        file_path = temp_dir / "test.pkl"
        # 大きなデータを作成
        data = "x" * 2000
        store(file_path, data)

        result = get_size_str(file_path)
        assert "KB" in result or "B" in result
