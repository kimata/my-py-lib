#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.pytest_util モジュールのユニットテスト
"""

from __future__ import annotations

import pathlib
import unittest.mock


class TestGetWorkerId:
    """get_worker_id 関数のテスト"""

    def test_returns_default_when_env_not_set(self):
        """PYTEST_XDIST_WORKER が未設定の場合、デフォルト値を返す"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            assert my_lib.pytest_util.get_worker_id() == "main"

    def test_returns_custom_default_when_env_not_set(self):
        """PYTEST_XDIST_WORKER が未設定の場合、指定したデフォルト値を返す"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            assert my_lib.pytest_util.get_worker_id("custom") == "custom"

    def test_returns_worker_id_when_env_set(self):
        """PYTEST_XDIST_WORKER が設定されている場合、その値を返す"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {"PYTEST_XDIST_WORKER": "gw0"}):
            assert my_lib.pytest_util.get_worker_id() == "gw0"


class TestGetPath:
    """get_path 関数のテスト"""

    def test_returns_original_path_when_env_not_set(self):
        """PYTEST_XDIST_WORKER が未設定の場合、元のパスをそのまま返す"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            original_path = pathlib.Path("/data/log.db")
            result = my_lib.pytest_util.get_path(original_path)
            assert result == original_path

    def test_returns_original_path_string_when_env_not_set(self):
        """PYTEST_XDIST_WORKER が未設定の場合、文字列パスでも元のパスを返す"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            result = my_lib.pytest_util.get_path("/data/log.db")
            assert result == pathlib.Path("/data/log.db")

    def test_returns_suffixed_path_when_env_set(self):
        """PYTEST_XDIST_WORKER が設定されている場合、suffixが付加されたパスを返す"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {"PYTEST_XDIST_WORKER": "gw0"}):
            original_path = pathlib.Path("/data/log.db")
            result = my_lib.pytest_util.get_path(original_path)
            assert result == pathlib.Path("/data/log.db.gw0")

    def test_returns_suffixed_path_with_different_worker_id(self):
        """異なるワーカーIDでsuffixが正しく付加される"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {"PYTEST_XDIST_WORKER": "gw5"}):
            result = my_lib.pytest_util.get_path("/data/metrics.db")
            assert result == pathlib.Path("/data/metrics.db.gw5")

    def test_preserves_directory_structure(self):
        """ディレクトリ構造が保持される"""
        import my_lib.pytest_util

        with unittest.mock.patch.dict("os.environ", {"PYTEST_XDIST_WORKER": "gw1"}):
            result = my_lib.pytest_util.get_path("/opt/app/data/log.db")
            assert result == pathlib.Path("/opt/app/data/log.db.gw1")
            assert result.parent == pathlib.Path("/opt/app/data")
