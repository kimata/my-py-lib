#!/usr/bin/env python3
import functools
import logging
import pathlib

import matplotlib  # noqa: ICN001


@functools.lru_cache(maxsize=32)
def _get_font_properties(font_path_str, size):
    """フォントプロパティをキャッシュ付きで取得"""
    return matplotlib.font_manager.FontProperties(fname=font_path_str, size=size)


def get_plot_font(config, font_type, size):
    font_path = pathlib.Path(config["path"]).resolve() / config["map"][font_type]

    cache_info = _get_font_properties.cache_info()

    result = _get_font_properties(str(font_path), size)
    new_cache_info = _get_font_properties.cache_info()

    # キャッシュミスが増えた場合は新しいフォントのロード
    if new_cache_info.misses > cache_info.misses:
        logging.info("Load font: %s (cached)", font_path)

    return result
