#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.json_util モジュールのユニットテスト
"""
from __future__ import annotations

import datetime
import zoneinfo

import pytest


class TestDateTimeJSONEncoder:
    """DateTimeJSONEncoder クラスのテスト"""

    def test_encodes_datetime_to_isoformat(self):
        """datetime を ISO 形式文字列にエンコードする"""
        import json

        import my_lib.json_util

        dt = datetime.datetime(2024, 1, 15, 12, 30, 45, tzinfo=zoneinfo.ZoneInfo("Asia/Tokyo"))
        result = json.dumps(dt, cls=my_lib.json_util.DateTimeJSONEncoder)
        assert "2024-01-15T12:30:45" in result

    def test_passes_through_other_types(self):
        """他の型はそのまま処理する"""
        import json

        import my_lib.json_util

        data = {"name": "test", "value": 123}
        result = json.dumps(data, cls=my_lib.json_util.DateTimeJSONEncoder)
        assert '"name": "test"' in result
        assert '"value": 123' in result


class TestLoads:
    """loads 関数のテスト"""

    def test_deserializes_iso_datetime_string(self):
        """ISO 形式の日時文字列を datetime に変換する"""
        import my_lib.json_util

        json_str = '"2024-01-15T12:30:45+09:00"'
        result = my_lib.json_util.loads(json_str)

        assert isinstance(result, datetime.datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_deserializes_utc_datetime_string(self):
        """UTC の日時文字列を datetime に変換する"""
        import my_lib.json_util

        json_str = '"2024-01-15T12:30:45Z"'
        result = my_lib.json_util.loads(json_str)

        assert isinstance(result, datetime.datetime)
        assert result.tzinfo is not None

    def test_deserializes_nested_datetime(self):
        """ネストした datetime も変換する"""
        import my_lib.json_util

        json_str = '{"timestamp": "2024-01-15T12:30:45+09:00", "name": "test"}'
        result = my_lib.json_util.loads(json_str)

        assert isinstance(result["timestamp"], datetime.datetime)
        assert result["name"] == "test"

    def test_deserializes_datetime_in_list(self):
        """リスト内の datetime も変換する"""
        import my_lib.json_util

        json_str = '{"items": ["2024-01-15T12:30:45+09:00", "string", 123]}'
        result = my_lib.json_util.loads(json_str)

        assert isinstance(result["items"][0], datetime.datetime)
        assert result["items"][1] == "string"
        assert result["items"][2] == 123

    def test_handles_simple_json(self):
        """通常の JSON を正しく処理する"""
        import my_lib.json_util

        json_str = '{"name": "test", "value": 123}'
        result = my_lib.json_util.loads(json_str)

        assert result == {"name": "test", "value": 123}


class TestDumps:
    """dumps 関数のテスト"""

    def test_serializes_datetime(self):
        """datetime をシリアライズする"""
        import my_lib.json_util

        dt = datetime.datetime(2024, 1, 15, 12, 30, 45, tzinfo=zoneinfo.ZoneInfo("Asia/Tokyo"))
        result = my_lib.json_util.dumps(dt)

        assert "2024-01-15T12:30:45" in result

    def test_serializes_complex_object(self):
        """複合オブジェクトをシリアライズする"""
        import my_lib.json_util
        import my_lib.time

        now = my_lib.time.now()
        data = {"timestamp": now, "name": "test", "count": 123}

        result = my_lib.json_util.dumps(data)
        assert "timestamp" in result
        assert "test" in result
        assert "123" in result


class TestRoundTrip:
    """シリアライズ/デシリアライズのラウンドトリップテスト"""

    def test_datetime_round_trip(self):
        """datetime のラウンドトリップが正しく動作する"""
        import my_lib.json_util
        import my_lib.time

        original = my_lib.time.now()
        json_str = my_lib.json_util.dumps(original)
        restored = my_lib.json_util.loads(json_str)

        assert restored == original

    def test_complex_object_round_trip(self):
        """複合オブジェクトのラウンドトリップが正しく動作する"""
        import my_lib.json_util
        import my_lib.time

        now = my_lib.time.now()
        original = {
            "timestamp": now,
            "name": "test",
            "count": 123,
            "nested": {"created_at": now, "items": [now, "string", 456]},
        }

        json_str = my_lib.json_util.dumps(original)
        restored = my_lib.json_util.loads(json_str)

        assert restored["timestamp"] == now
        assert restored["name"] == "test"
        assert restored["count"] == 123
        assert restored["nested"]["created_at"] == now
        assert restored["nested"]["items"][0] == now


class TestSerializeDatetime:
    """serialize_datetime 関数のテスト"""

    def test_serializes_datetime(self):
        """datetime を ISO 8601 文字列に変換する"""
        import my_lib.json_util

        dt = datetime.datetime(2024, 1, 15, 12, 30, 45)
        result = my_lib.json_util.serialize_datetime(dt)
        assert result == "2024-01-15T12:30:45"

    def test_returns_none_for_none_input(self):
        """None 入力に対して None を返す"""
        import my_lib.json_util

        assert my_lib.json_util.serialize_datetime(None) is None


class TestDeserializeDatetime:
    """deserialize_datetime 関数のテスト"""

    def test_deserializes_iso_string(self):
        """ISO 8601 文字列を datetime に変換する"""
        import my_lib.json_util

        result = my_lib.json_util.deserialize_datetime("2024-01-15T12:30:45")
        assert isinstance(result, datetime.datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_returns_none_for_none_input(self):
        """None 入力に対して None を返す"""
        import my_lib.json_util

        assert my_lib.json_util.deserialize_datetime(None) is None

    def test_returns_none_for_empty_string(self):
        """空文字列に対して None を返す"""
        import my_lib.json_util

        assert my_lib.json_util.deserialize_datetime("") is None

    def test_returns_none_for_invalid_format(self):
        """不正な形式に対して None を返す"""
        import my_lib.json_util

        assert my_lib.json_util.deserialize_datetime("invalid") is None
