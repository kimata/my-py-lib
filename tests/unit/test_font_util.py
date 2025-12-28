#!/usr/bin/env python3
# ruff: noqa: S101
"""font_util.py のテスト"""
from __future__ import annotations

import pathlib
import unittest.mock

import pytest

pytest.importorskip("matplotlib")

import PIL.ImageFont

import my_lib.font_util


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


class TestBuildPilFaceMap:
    """build_pil_face_map 関数のテスト"""

    def test_builds_font_map(self, temp_dir):
        """フォントマップを構築する"""
        font_file = temp_dir / "test.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"bold": "test.ttf"})
        spec = {"title": ("bold", 24)}

        with unittest.mock.patch("my_lib.pil_util.get_font") as mock_get_font:
            mock_font = unittest.mock.MagicMock(spec=PIL.ImageFont.FreeTypeFont)
            mock_get_font.return_value = mock_font

            result = my_lib.font_util.build_pil_face_map(font_config, spec)

            assert "title" in result
            assert result["title"] is mock_font
            mock_get_font.assert_called_once_with(font_config, "bold", 24)

    def test_builds_multiple_fonts(self, temp_dir):
        """複数のフォントを構築する"""
        font_file = temp_dir / "font.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"regular": "font.ttf", "bold": "font.ttf"})
        spec = {
            "title": ("bold", 24),
            "body": ("regular", 12),
            "caption": ("regular", 10),
        }

        with unittest.mock.patch("my_lib.pil_util.get_font") as mock_get_font:
            mock_get_font.return_value = unittest.mock.MagicMock(spec=PIL.ImageFont.FreeTypeFont)

            result = my_lib.font_util.build_pil_face_map(font_config, spec)

            assert len(result) == 3
            assert "title" in result
            assert "body" in result
            assert "caption" in result

    def test_empty_spec_returns_empty_map(self, temp_dir):
        """空の仕様は空のマップを返す"""
        font_config = MockFontConfig(temp_dir, {})

        result = my_lib.font_util.build_pil_face_map(font_config, {})

        assert result == {}


class TestBuildPilFaceMapNested:
    """build_pil_face_map_nested 関数のテスト"""

    def test_builds_nested_font_map(self, temp_dir):
        """ネストしたフォントマップを構築する"""
        font_file = temp_dir / "test.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"bold": "test.ttf"})
        spec = {
            "header": {"title": ("bold", 24)},
            "footer": {"text": ("bold", 10)},
        }

        with unittest.mock.patch("my_lib.pil_util.get_font") as mock_get_font:
            mock_get_font.return_value = unittest.mock.MagicMock(spec=PIL.ImageFont.FreeTypeFont)

            result = my_lib.font_util.build_pil_face_map_nested(font_config, spec)

            assert "header" in result
            assert "footer" in result
            assert "title" in result["header"]
            assert "text" in result["footer"]

    def test_empty_nested_spec_returns_empty_map(self, temp_dir):
        """空のネスト仕様は空のマップを返す"""
        font_config = MockFontConfig(temp_dir, {})

        result = my_lib.font_util.build_pil_face_map_nested(font_config, {})

        assert result == {}


class TestBuildPlotFaceMap:
    """build_plot_face_map 関数のテスト"""

    def test_builds_plot_font_map(self, temp_dir):
        """matplotlib フォントマップを構築する"""
        font_file = temp_dir / "plot.ttf"
        font_file.touch()

        font_config = MockFontConfig(temp_dir, {"sans": "plot.ttf"})
        spec = {"axis": ("sans", 12)}

        with unittest.mock.patch("my_lib.plot_util.get_plot_font") as mock_get_font:
            mock_font = unittest.mock.MagicMock()
            mock_get_font.return_value = mock_font

            result = my_lib.font_util.build_plot_face_map(font_config, spec)

            assert "axis" in result
            assert result["axis"] is mock_font
            mock_get_font.assert_called_once_with(font_config, "sans", 12)

    def test_builds_multiple_plot_fonts(self, temp_dir):
        """複数の matplotlib フォントを構築する"""
        font_config = MockFontConfig(temp_dir, {"regular": "font.ttf"})
        spec = {
            "title": ("regular", 18),
            "label": ("regular", 12),
        }

        with unittest.mock.patch("my_lib.plot_util.get_plot_font") as mock_get_font:
            mock_get_font.return_value = unittest.mock.MagicMock()

            result = my_lib.font_util.build_plot_face_map(font_config, spec)

            assert len(result) == 2
            assert mock_get_font.call_count == 2


class TestFontSpecTypeAlias:
    """FontSpec 型エイリアスのテスト"""

    def test_font_spec_is_tuple(self):
        """FontSpec は (str, int) のタプル"""
        spec: my_lib.font_util.FontSpec = ("bold", 24)
        assert spec[0] == "bold"
        assert spec[1] == 24
