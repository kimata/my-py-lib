#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.time モジュールのユニットテスト
"""
from __future__ import annotations

import datetime
import unittest.mock
import zoneinfo

import pytest


class TestGetTz:
    """get_tz 関数のテスト"""

    def test_returns_default_timezone_when_tz_not_set(self):
        """TZ環境変数が未設定の場合、デフォルトタイムゾーンを返す"""
        import my_lib.time

        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            assert my_lib.time.get_tz() == my_lib.time.TIMEZONE_DEFAULT

    def test_returns_tz_environment_variable_when_set(self):
        """TZ環境変数が設定されている場合、その値を返す"""
        import my_lib.time

        with unittest.mock.patch.dict("os.environ", {"TZ": "America/New_York"}):
            assert my_lib.time.get_tz() == "America/New_York"


class TestGetZoneinfo:
    """get_zoneinfo 関数のテスト"""

    def test_returns_zoneinfo_object(self):
        """ZoneInfo オブジェクトを返す"""
        import my_lib.time

        result = my_lib.time.get_zoneinfo()
        assert isinstance(result, zoneinfo.ZoneInfo)

    def test_returns_correct_timezone(self):
        """正しいタイムゾーンの ZoneInfo を返す"""
        import my_lib.time

        with unittest.mock.patch.dict("os.environ", {"TZ": "Asia/Tokyo"}):
            result = my_lib.time.get_zoneinfo()
            assert str(result) == "Asia/Tokyo"


class TestGetPytz:
    """get_pytz 関数のテスト"""

    def test_returns_pytz_timezone(self):
        """pytz タイムゾーンオブジェクトを返す"""
        import pytz

        import my_lib.time

        result = my_lib.time.get_pytz()
        assert isinstance(result, pytz.BaseTzInfo)


class TestNow:
    """now 関数のテスト"""

    def test_returns_datetime_object(self):
        """datetime オブジェクトを返す"""
        import my_lib.time

        result = my_lib.time.now()
        assert isinstance(result, datetime.datetime)

    def test_returns_timezone_aware_datetime(self):
        """タイムゾーン付きの datetime を返す"""
        import my_lib.time

        result = my_lib.time.now()
        assert result.tzinfo is not None

    def test_returns_current_time(self):
        """現在時刻に近い値を返す"""
        import my_lib.time

        before = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo"))
        result = my_lib.time.now()
        after = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo"))

        assert before <= result <= after
