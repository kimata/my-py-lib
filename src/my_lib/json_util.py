#!/usr/bin/env python3
"""
タイムゾーン付きの日付を JSON で扱うためのライブラリです。

Usage:
  json_util.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import datetime
import json
import re
from typing import Any


class DateTimeJSONEncoder(json.JSONEncoder):
    """datetime オブジェクトを ISO format 文字列に変換する JSON エンコーダー"""

    def default(self, obj: Any) -> Any:  # type: ignore[override]
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


def datetime_hook(dct: dict[str, Any]) -> dict[str, Any]:
    """辞書内のISO形式文字列をdatetimeオブジェクトに変換するフック関数"""
    # ISO 8601形式の日時文字列パターン（タイムゾーン付き）
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$")

    def convert_value(value: Any) -> Any:
        if isinstance(value, str) and iso_pattern.match(value):
            try:
                # ISO形式文字列をdatetimeオブジェクトに変換
                return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                # 変換に失敗した場合は元の文字列のまま
                return value
        elif isinstance(value, list):
            # リスト内の要素も再帰的に処理
            return [convert_value(item) for item in value]
        elif isinstance(value, dict):
            # ネストした辞書も再帰的に処理
            return {k: convert_value(v) for k, v in value.items()}
        return value

    return {key: convert_value(value) for key, value in dct.items()}


def loads(json_str: str) -> Any:
    result = json.loads(json_str, object_hook=datetime_hook)

    # 結果が文字列で、ISO形式の日時文字列の場合はdatetimeオブジェクトに変換
    if isinstance(result, str):
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$")
        if iso_pattern.match(result):
            try:
                return datetime.datetime.fromisoformat(result.replace("Z", "+00:00"))
            except ValueError:
                return result

    return result


def dumps(obj: Any) -> str:
    return json.dumps(obj, cls=DateTimeJSONEncoder)


def serialize_datetime(dt: datetime.datetime | None) -> str | None:
    """datetime を ISO 8601 文字列に変換する。

    Args:
        dt: 変換する datetime オブジェクト（None も可）

    Returns:
        ISO 8601 形式の文字列、または None

    Examples:
        >>> serialize_datetime(datetime.datetime(2024, 1, 1, 12, 0, 0))
        '2024-01-01T12:00:00'

    """
    if dt is None:
        return None
    return dt.isoformat()


def deserialize_datetime(dt_str: str | None) -> datetime.datetime | None:
    """ISO 8601 文字列を datetime に変換する。

    Args:
        dt_str: ISO 8601 形式の日時文字列（None も可）

    Returns:
        datetime オブジェクト、または None（変換失敗時も None）

    Examples:
        >>> deserialize_datetime('2024-01-01T12:00:00')
        datetime.datetime(2024, 1, 1, 12, 0, 0)

    """
    if not dt_str:
        return None
    try:
        return datetime.datetime.fromisoformat(dt_str)
    except ValueError:
        return None


if __name__ == "__main__":
    # TEST Code
    import logging

    import docopt

    import my_lib.logger
    import my_lib.pretty
    import my_lib.time

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    now = my_lib.time.now()

    logging.info(now)

    json_str = dumps(now)

    logging.info(my_lib.pretty.format(json_str))

    now2 = loads(json_str)

    logging.info(now)
