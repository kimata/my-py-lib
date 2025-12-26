#!/usr/bin/env python3
"""パネル関連の共通設定型定義

設計方針:
- Protocol による構造的部分型付け
- NullObject パターンで None を回避
- isinstance の使用を最小限に
- パスは pathlib.Path で統一
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import my_lib.notify.slack
    from my_lib.sensor_data import InfluxDBConfig


# === Protocol 定義 ===
class GeometryProtocol(Protocol):
    """ジオメトリ（幅・高さ）を持つオブジェクトの Protocol"""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...


class OffsetProtocol(Protocol):
    """オフセット（位置）を持つオブジェクトの Protocol"""

    @property
    def offset_x(self) -> int: ...

    @property
    def offset_y(self) -> int: ...


class FontConfigProtocol(Protocol):
    """フォント設定の Protocol"""

    @property
    def path(self) -> pathlib.Path: ...

    @property
    def map(self) -> dict[str, str]: ...


class IconConfigProtocol(Protocol):
    """アイコン設定の Protocol"""

    @property
    def path(self) -> pathlib.Path: ...

    @property
    def scale(self) -> float: ...

    @property
    def brightness(self) -> float: ...


class PanelConfigProtocol(Protocol):
    """パネル設定（panel プロパティを持つ）の Protocol"""

    @property
    def panel(self) -> GeometryProtocol: ...


# === 具象クラス ===
@dataclass(frozen=True)
class FontConfig:
    """フォント設定"""

    path: pathlib.Path
    map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PanelGeometry:
    """パネルの位置とサイズ"""

    width: int
    height: int
    offset_x: int = 0
    offset_y: int = 0


@dataclass(frozen=True)
class IconConfig:
    """アイコン設定"""

    path: pathlib.Path
    scale: float = 1.0
    brightness: float = 1.0


# === パース関数 ===
def parse_font_config(data: dict[str, str | dict[str, str]]) -> FontConfig:
    """フォント設定をパースする"""
    path = data["path"]
    if not isinstance(path, str):
        msg = "font config path must be a string"
        raise TypeError(msg)

    map_data = data.get("map", {})
    if not isinstance(map_data, dict):
        msg = "font config map must be a dict"
        raise TypeError(msg)

    return FontConfig(
        path=pathlib.Path(path),
        map=dict(map_data),
    )


def parse_panel_geometry(data: dict[str, int]) -> PanelGeometry:
    """パネルジオメトリをパースする"""
    return PanelGeometry(
        width=data["width"],
        height=data["height"],
        offset_x=data.get("offset_x", 0),
        offset_y=data.get("offset_y", 0),
    )


def parse_icon_config(data: dict[str, str | float]) -> IconConfig:
    """アイコン設定をパースする"""
    path = data["path"]
    if not isinstance(path, str):
        msg = "icon config path must be a string"
        raise TypeError(msg)

    scale = data.get("scale", 1.0)
    brightness = data.get("brightness", 1.0)

    return IconConfig(
        path=pathlib.Path(path),
        scale=float(scale) if scale is not None else 1.0,
        brightness=float(brightness) if brightness is not None else 1.0,
    )


# === パネルコンテキスト ===
@dataclass(frozen=True)
class NormalPanelContext:
    """通常パネル用コンテキスト（リトライ機能付き）

    draw_panel_patiently を使用するパネル向け。
    weather, rain_cloud, wbgt などで使用。
    """

    font_config: FontConfigProtocol
    slack_config: my_lib.notify.slack.HasErrorConfig | my_lib.notify.slack.SlackEmptyConfig
    is_side_by_side: bool = True
    trial: int = 0


@dataclass(frozen=True)
class DatabasePanelContext:
    """データベースパネル用コンテキスト

    InfluxDB を使用するパネル向け。
    sensor_graph, power_graph, rain_fall などで使用。
    """

    font_config: FontConfigProtocol
    db_config: InfluxDBConfig
