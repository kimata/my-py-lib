#!/usr/bin/env python3
"""
ハッシュ計算ユーティリティ

差分検出やキャッシュキー生成のためのハッシュ計算機能を提供します。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def calculate_dict_hash(data: dict[str, Any]) -> str:
    """辞書データのMD5ハッシュを計算する。

    キャッシュの差分検出などに使用します。
    辞書はソートされ、JSON文字列に変換されてからハッシュ化されます。

    Args:
        data: ハッシュ化する辞書データ

    Returns:
        MD5ハッシュ値（16進数文字列）

    Examples:
        >>> calculate_dict_hash({"name": "test", "value": 123})
        'a1b2c3...'

    """
    data_str = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(data_str.encode()).hexdigest()  # noqa: S324
