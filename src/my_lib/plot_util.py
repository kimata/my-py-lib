#!/usr/bin/env python3
from __future__ import annotations

import functools
import logging
import pathlib
from typing import Any

import matplotlib  # noqa: ICN001
import matplotlib.font_manager


@functools.lru_cache(maxsize=32)
def _get_font_properties(font_path_str: str, size: int) -> matplotlib.font_manager.FontProperties:
    """フォントプロパティをキャッシュ付きで取得"""
    return matplotlib.font_manager.FontProperties(fname=font_path_str, size=size)


def get_plot_font(
    font_config: dict[str, Any], font_type: str, size: int
) -> matplotlib.font_manager.FontProperties:
    font_path = pathlib.Path(font_config["path"]).resolve() / font_config["map"][font_type]

    cache_info = _get_font_properties.cache_info()

    result = _get_font_properties(str(font_path), size)
    new_cache_info = _get_font_properties.cache_info()

    # キャッシュミスが増えた場合は新しいフォントのロード
    if new_cache_info.misses > cache_info.misses:
        logging.debug("Load font: %s (cached)", font_path)

    return result
