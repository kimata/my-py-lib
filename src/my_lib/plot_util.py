#!/usr/bin/env python3
from __future__ import annotations

import functools
import logging
import pathlib

import matplotlib.font_manager

import my_lib.panel_config


@functools.lru_cache(maxsize=32)
def _get_font_properties(font_path: pathlib.Path, size: int) -> matplotlib.font_manager.FontProperties:
    """フォントプロパティをキャッシュ付きで取得"""
    return matplotlib.font_manager.FontProperties(fname=str(font_path), size=size)


def get_plot_font(
    font_config: my_lib.panel_config.FontConfigProtocol, font_type: str, size: int
) -> matplotlib.font_manager.FontProperties:
    """matplotlib 用フォントを取得する

    Args:
        font_config: フォント設定 (path, map を持つ)
        font_type: フォントタイプ (例: "jp_bold", "en_medium")
        size: フォントサイズ

    Returns:
        matplotlib FontProperties オブジェクト
    """
    font_path = font_config.path.resolve() / font_config.map[font_type]

    cache_info = _get_font_properties.cache_info()

    result = _get_font_properties(font_path, size)
    new_cache_info = _get_font_properties.cache_info()

    # キャッシュミスが増えた場合は新しいフォントのロード
    if new_cache_info.misses > cache_info.misses:
        logging.debug("Load font: %s (cached)", font_path)

    return result
