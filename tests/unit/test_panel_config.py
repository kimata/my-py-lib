#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.panel_config モジュールのユニットテスト
"""
from __future__ import annotations

import pathlib

import pytest


class TestFontConfig:
    """FontConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.panel_config import FontConfig

        config = FontConfig(
            path=pathlib.Path("/fonts"),
            map={"jp_bold": "NotoSansJP-Bold.ttf"},
        )

        assert config.path == pathlib.Path("/fonts")
        assert config.map == {"jp_bold": "NotoSansJP-Bold.ttf"}

    def test_is_frozen(self):
        """変更不可である"""
        from my_lib.panel_config import FontConfig

        config = FontConfig(path=pathlib.Path("/fonts"), map={})

        with pytest.raises(AttributeError):
            config.path = pathlib.Path("/other")  # type: ignore[misc]

    def test_default_map(self):
        """map のデフォルトは空辞書"""
        from my_lib.panel_config import FontConfig

        config = FontConfig(path=pathlib.Path("/fonts"))
        assert config.map == {}


class TestPanelGeometry:
    """PanelGeometry データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.panel_config import PanelGeometry

        geometry = PanelGeometry(width=800, height=600, offset_x=10, offset_y=20)

        assert geometry.width == 800
        assert geometry.height == 600
        assert geometry.offset_x == 10
        assert geometry.offset_y == 20

    def test_default_offsets(self):
        """オフセットのデフォルトは 0"""
        from my_lib.panel_config import PanelGeometry

        geometry = PanelGeometry(width=800, height=600)

        assert geometry.offset_x == 0
        assert geometry.offset_y == 0

    def test_is_frozen(self):
        """変更不可である"""
        from my_lib.panel_config import PanelGeometry

        geometry = PanelGeometry(width=800, height=600)

        with pytest.raises(AttributeError):
            geometry.width = 1024  # type: ignore[misc]


class TestIconConfig:
    """IconConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.panel_config import IconConfig

        config = IconConfig(
            path=pathlib.Path("/icons/icon.png"),
            scale=1.5,
            brightness=0.8,
        )

        assert config.path == pathlib.Path("/icons/icon.png")
        assert config.scale == 1.5
        assert config.brightness == 0.8

    def test_default_values(self):
        """デフォルト値"""
        from my_lib.panel_config import IconConfig

        config = IconConfig(path=pathlib.Path("/icons/icon.png"))

        assert config.scale == 1.0
        assert config.brightness == 1.0


class TestParseFontConfig:
    """parse_font_config 関数のテスト"""

    def test_parses_valid_data(self):
        """有効なデータをパースする"""
        from my_lib.panel_config import parse_font_config

        data = {
            "path": "/fonts",
            "map": {"jp_bold": "Bold.ttf"},
        }

        config = parse_font_config(data)

        assert config.path == pathlib.Path("/fonts")
        assert config.map == {"jp_bold": "Bold.ttf"}

    def test_raises_for_non_string_path(self):
        """path が文字列でない場合は例外"""
        from my_lib.panel_config import parse_font_config

        data = {"path": 123, "map": {}}

        with pytest.raises(TypeError, match="path must be a string"):
            parse_font_config(data)

    def test_raises_for_non_dict_map(self):
        """map が辞書でない場合は例外"""
        from my_lib.panel_config import parse_font_config

        data = {"path": "/fonts", "map": "not a dict"}

        with pytest.raises(TypeError, match="map must be a dict"):
            parse_font_config(data)

    def test_default_empty_map(self):
        """map がない場合は空辞書"""
        from my_lib.panel_config import parse_font_config

        data = {"path": "/fonts"}

        config = parse_font_config(data)
        assert config.map == {}


class TestParsePanelGeometry:
    """parse_panel_geometry 関数のテスト"""

    def test_parses_valid_data(self):
        """有効なデータをパースする"""
        from my_lib.panel_config import parse_panel_geometry

        data = {
            "width": 800,
            "height": 600,
            "offset_x": 10,
            "offset_y": 20,
        }

        geometry = parse_panel_geometry(data)

        assert geometry.width == 800
        assert geometry.height == 600
        assert geometry.offset_x == 10
        assert geometry.offset_y == 20

    def test_default_offsets(self):
        """オフセットがない場合は 0"""
        from my_lib.panel_config import parse_panel_geometry

        data = {"width": 800, "height": 600}

        geometry = parse_panel_geometry(data)

        assert geometry.offset_x == 0
        assert geometry.offset_y == 0


class TestParseIconConfig:
    """parse_icon_config 関数のテスト"""

    def test_parses_valid_data(self):
        """有効なデータをパースする"""
        from my_lib.panel_config import parse_icon_config

        data = {
            "path": "/icons/icon.png",
            "scale": 1.5,
            "brightness": 0.8,
        }

        config = parse_icon_config(data)

        assert config.path == pathlib.Path("/icons/icon.png")
        assert config.scale == 1.5
        assert config.brightness == 0.8

    def test_raises_for_non_string_path(self):
        """path が文字列でない場合は例外"""
        from my_lib.panel_config import parse_icon_config

        data = {"path": 123}

        with pytest.raises(TypeError, match="path must be a string"):
            parse_icon_config(data)

    def test_default_values(self):
        """デフォルト値"""
        from my_lib.panel_config import parse_icon_config

        data = {"path": "/icons/icon.png"}

        config = parse_icon_config(data)

        assert config.scale == 1.0
        assert config.brightness == 1.0


class TestNormalPanelContext:
    """NormalPanelContext データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_config import FontConfig, NormalPanelContext

        font_config = FontConfig(path=pathlib.Path("/fonts"))
        slack_config = SlackEmptyConfig()

        context = NormalPanelContext(
            font_config=font_config,
            slack_config=slack_config,
            is_side_by_side=True,
            trial=1,
        )

        assert context.font_config == font_config
        assert context.slack_config == slack_config
        assert context.is_side_by_side is True
        assert context.trial == 1

    def test_default_values(self):
        """デフォルト値"""
        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_config import FontConfig, NormalPanelContext

        font_config = FontConfig(path=pathlib.Path("/fonts"))
        slack_config = SlackEmptyConfig()

        context = NormalPanelContext(
            font_config=font_config,
            slack_config=slack_config,
        )

        assert context.is_side_by_side is True
        assert context.trial == 0


class TestDatabasePanelContext:
    """DatabasePanelContext データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.panel_config import DatabasePanelContext, FontConfig

        # DatabasePanelContext は InfluxDBConfig を必要とするため、
        # ここでは簡易的にテスト
        font_config = FontConfig(path=pathlib.Path("/fonts"))

        # db_config は Any として扱う
        context = DatabasePanelContext(
            font_config=font_config,
            db_config=None,  # type: ignore[arg-type]
        )

        assert context.font_config == font_config
