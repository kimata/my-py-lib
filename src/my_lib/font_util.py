#!/usr/bin/env python3
"""フォントマップ構築ユーティリティ

パネルモジュールで使用するフォントマップを宣言的に構築するためのユーティリティ。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.font_manager  # type: ignore[import-untyped]
import PIL.ImageFont

import my_lib.panel_config
import my_lib.pil_util
import my_lib.plot_util

if TYPE_CHECKING:
    from typing import TypeAlias

# フォント仕様の型定義: (フォントタイプ, サイズ) のタプル
FontSpec: TypeAlias = tuple[str, int]

# フォントマップ仕様の型定義
# flat: {"key": ("font_type", size)}
# nested: {"group": {"key": ("font_type", size)}}
FontMapSpec: TypeAlias = dict[str, FontSpec | dict[str, FontSpec]]


def build_pil_face_map(
    font_config: my_lib.panel_config.FontConfigProtocol,
    spec: dict[str, FontSpec],
) -> dict[str, PIL.ImageFont.FreeTypeFont]:
    """PIL フォントマップを構築する (フラット構造)

    Args:
        font_config: フォント設定
        spec: フォント仕様の辞書 {名前: (フォントタイプ, サイズ)}

    Returns:
        PIL フォントオブジェクトの辞書
    """
    return {
        name: my_lib.pil_util.get_font(font_config, font_type, size)
        for name, (font_type, size) in spec.items()
    }


def build_pil_face_map_nested(
    font_config: my_lib.panel_config.FontConfigProtocol,
    spec: dict[str, dict[str, FontSpec]],
) -> dict[str, dict[str, PIL.ImageFont.FreeTypeFont]]:
    """PIL フォントマップを構築する (ネスト構造)

    Args:
        font_config: フォント設定
        spec: ネストしたフォント仕様の辞書 {グループ: {名前: (フォントタイプ, サイズ)}}

    Returns:
        ネストした PIL フォントオブジェクトの辞書
    """
    return {group: build_pil_face_map(font_config, group_spec) for group, group_spec in spec.items()}


def build_plot_face_map(
    font_config: my_lib.panel_config.FontConfigProtocol,
    spec: dict[str, FontSpec],
) -> dict[str, matplotlib.font_manager.FontProperties]:
    """Matplotlib フォントマップを構築する

    Args:
        font_config: フォント設定
        spec: フォント仕様の辞書 {名前: (フォントタイプ, サイズ)}

    Returns:
        matplotlib FontProperties オブジェクトの辞書
    """
    return {
        name: my_lib.plot_util.get_plot_font(font_config, font_type, size)
        for name, (font_type, size) in spec.items()
    }
