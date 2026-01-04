#!/usr/bin/env python3
# ruff: noqa: S101
"""plot_util.py のテスト"""

from __future__ import annotations

import pathlib
import unittest.mock

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib_font_manager = pytest.importorskip("matplotlib.font_manager")

import my_lib.plot_util  # noqa: E402


class MockFontConfig:
    """テスト用のフォント設定モック"""

    def __init__(self, path: pathlib.Path, font_map: dict[str, str]):
        self._path = path
        self._map = font_map

    @property
    def path(self) -> pathlib.Path:
        return self._path

    @property
    def map(self) -> dict[str, str]:
        return self._map


class TestGetPlotFont:
    """get_plot_font 関数のテスト"""

    def test_returns_font_properties(self, temp_dir):
        """FontProperties オブジェクトを返す"""
        font_file = temp_dir / "test.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"test": "test.ttf"})

        with unittest.mock.patch.object(
            matplotlib_font_manager.FontProperties,
            "__init__",
            return_value=None,
        ):
            result = my_lib.plot_util.get_plot_font(font_config, "test", 12)
            assert isinstance(result, matplotlib_font_manager.FontProperties)

    def test_uses_correct_font_path(self, temp_dir):
        """正しいフォントパスを使用する"""
        font_file = temp_dir / "my_font.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"jp_bold": "my_font.ttf"})

        with unittest.mock.patch("matplotlib.font_manager.FontProperties") as mock_fp:
            my_lib.plot_util.get_plot_font(font_config, "jp_bold", 16)

            call_args = mock_fp.call_args
            expected_path = str(temp_dir.resolve() / "my_font.ttf")
            assert call_args.kwargs["fname"] == expected_path
            assert call_args.kwargs["size"] == 16

    def test_caches_font_properties(self, temp_dir):
        """フォントプロパティをキャッシュする"""
        font_file = temp_dir / "cached.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"cache_test": "cached.ttf"})

        my_lib.plot_util._get_font_properties.cache_clear()

        with unittest.mock.patch("matplotlib.font_manager.FontProperties") as mock_fp:
            mock_fp.return_value = unittest.mock.MagicMock()

            my_lib.plot_util.get_plot_font(font_config, "cache_test", 14)
            my_lib.plot_util.get_plot_font(font_config, "cache_test", 14)

            assert mock_fp.call_count == 1

    def test_different_sizes_create_different_cache_entries(self, temp_dir):
        """異なるサイズは異なるキャッシュエントリを作成する"""
        font_file = temp_dir / "size_test.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"size_test": "size_test.ttf"})

        my_lib.plot_util._get_font_properties.cache_clear()

        with unittest.mock.patch("matplotlib.font_manager.FontProperties") as mock_fp:
            mock_fp.return_value = unittest.mock.MagicMock()

            my_lib.plot_util.get_plot_font(font_config, "size_test", 10)
            my_lib.plot_util.get_plot_font(font_config, "size_test", 20)

            assert mock_fp.call_count == 2


class TestGetFontPropertiesCache:
    """_get_font_properties キャッシュのテスト"""

    def test_cache_info_available(self):
        """cache_info が利用可能"""
        cache_info = my_lib.plot_util._get_font_properties.cache_info()
        assert hasattr(cache_info, "hits")
        assert hasattr(cache_info, "misses")

    def test_cache_can_be_cleared(self):
        """キャッシュをクリアできる"""
        my_lib.plot_util._get_font_properties.cache_clear()
        cache_info = my_lib.plot_util._get_font_properties.cache_info()
        assert cache_info.hits == 0
        assert cache_info.misses == 0
