#!/usr/bin/env python3
# ruff: noqa: S101
"""weather.py のテスト"""
from __future__ import annotations

import datetime
import io
import unittest.mock

import lxml.html
import pytest

import my_lib.weather


class TestFetchPage:
    """fetch_page 関数のテスト"""

    def test_fetches_page_with_encoding(self):
        """エンコーディング指定でページを取得する"""
        html_content = b"<html><body>Test</body></html>"

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = unittest.mock.MagicMock()
            mock_response.read.return_value = html_content
            mock_urlopen.return_value = mock_response

            result = my_lib.weather.fetch_page("http://example.com", "UTF-8")

            assert result is not None
            assert isinstance(result, lxml.html.HtmlElement)

    def test_fetches_page_without_encoding(self):
        """エンコーディングなしでページを取得する"""
        html_content = b"<html><body>Test</body></html>"

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = unittest.mock.MagicMock()
            mock_response.read.return_value = html_content
            mock_urlopen.return_value = mock_response

            result = my_lib.weather.fetch_page("http://example.com", None)

            assert result is not None
            assert isinstance(result, lxml.html.HtmlElement)


class TestParseWeatherYahoo:
    """parse_weather_yahoo 関数のテスト"""

    def test_parses_weather_info(self):
        """天気情報をパースする"""
        html = lxml.html.fromstring('<td>晴れ<img src="http://example.com/sunny_g.png"/></td>')

        result = my_lib.weather.parse_weather_yahoo(html)

        assert result.text == "晴れ"
        assert result.icon_url == "http://example.com/sunny.png"


class TestParseWindYahoo:
    """parse_wind_yahoo 関数のテスト"""

    def test_parses_wind_info(self):
        """風情報をパースする"""
        html = lxml.html.fromstring("<td>北 5</td>")

        result = my_lib.weather.parse_wind_yahoo(html)

        assert result.dir == "北"
        assert result.speed == 5


class TestParseDateYahoo:
    """parse_date_yahoo 関数のテスト"""

    def test_parses_date(self):
        """日付をパースする"""
        html_str = """
        <html>
            <h3><span class="yjSt">1月15日の天気</span></h3>
            <h3><span class="yjSt">1月16日の天気</span></h3>
        </html>
        """
        html = lxml.html.fromstring(html_str)

        result = my_lib.weather.parse_date_yahoo(html, 1)

        assert result.month == 1
        assert result.day == 15

    def test_raises_for_invalid_format(self):
        """無効なフォーマットでエラーを発生させる"""
        html = lxml.html.fromstring('<html><h3><span class="yjSt">Invalid date</span></h3></html>')

        with pytest.raises(ValueError, match="Failed to parse date"):
            my_lib.weather.parse_date_yahoo(html, 1)


class TestParseClothingYahoo:
    """parse_clothing_yahoo 関数のテスト"""

    def test_parses_clothing_index(self):
        """服装指数をパースする"""
        html_str = """
        <html>
            <dl class="indexList_item indexList_item-clothing">
                <dd><p class="index-50">dummy</p></dd>
            </dl>
        </html>
        """
        html = lxml.html.fromstring(html_str)

        result = my_lib.weather.parse_clothing_yahoo(html, 1)

        assert result == 50


class TestParseWbgtCurrent:
    """parse_wbgt_current 関数のテスト"""

    def test_parses_wbgt_value(self):
        """WBGT値をパースする"""
        html = lxml.html.fromstring('<html><span class="present_num">28.5</span></html>')

        result = my_lib.weather.parse_wbgt_current(html)

        assert result == 28.5

    def test_returns_none_when_not_found(self):
        """見つからない場合は None を返す"""
        html = lxml.html.fromstring("<html><body>No WBGT</body></html>")

        result = my_lib.weather.parse_wbgt_current(html)

        assert result is None


class TestGetSunsetUrlNao:
    """get_sunset_url_nao 関数のテスト"""

    def test_generates_url(self):
        """URLを生成する"""
        date = datetime.datetime(2024, 7, 15)

        result = my_lib.weather.get_sunset_url_nao(13, date)

        assert "2024" in result
        assert "s13" in result
        assert "07" in result


class TestGetSunsetNao:
    """get_sunset_nao 関数のテスト"""

    def test_returns_question_marks_on_error(self):
        """エラー時は ? を返す"""
        with unittest.mock.patch("my_lib.weather.get_sunset_date_nao") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = my_lib.weather.get_sunset_nao(13)

            assert result.today == "?"
            assert result.tomorrow == "?"


class TestSunsetResult:
    """SunsetResult データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        result = my_lib.weather.SunsetResult(today="17:00", tomorrow="17:01")

        assert result.today == "17:00"
        assert result.tomorrow == "17:01"


class TestTenkiHourlyData:
    """TenkiHourlyData データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        data = my_lib.weather.TenkiHourlyData(temp=25.5, precip=10, humi=60)

        assert data.temp == 25.5
        assert data.precip == 10
        assert data.humi == 60


class TestTenkiDayData:
    """TenkiDayData データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        date = datetime.datetime(2024, 1, 1)
        data = my_lib.weather.TenkiDayData(date=date)

        assert data.date == date
        assert data.data == []


class TestTenkiResult:
    """TenkiResult データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        today = my_lib.weather.TenkiDayData(date=datetime.datetime(2024, 1, 1))
        tomorrow = my_lib.weather.TenkiDayData(date=datetime.datetime(2024, 1, 2))

        result = my_lib.weather.TenkiResult(today=today, tomorrow=tomorrow)

        assert result.today.date.day == 1
        assert result.tomorrow.date.day == 2


class TestParseDateTenki:
    """parse_date_tenki 関数のテスト"""

    def test_parses_date(self):
        """日付をパースする"""
        html_str = """
        <html>
            <table class="forecast-point-1h">
                <tr><td>2024年1月15日</td></tr>
            </table>
        </html>
        """
        html = lxml.html.fromstring(html_str)

        result = my_lib.weather.parse_date_tenki(html, 1)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_raises_for_invalid_format(self):
        """無効なフォーマットでエラーを発生させる"""
        html_str = """
        <html>
            <table class="forecast-point-1h">
                <tr><td>Invalid date</td></tr>
            </table>
        </html>
        """
        html = lxml.html.fromstring(html_str)

        with pytest.raises(ValueError, match="Failed to parse date"):
            my_lib.weather.parse_date_tenki(html, 1)


class TestWeatherInfo:
    """WeatherInfo データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        info = my_lib.weather.WeatherInfo(text="晴れ", icon_url="http://example.com/sunny.png")

        assert info.text == "晴れ"
        assert info.icon_url == "http://example.com/sunny.png"

    def test_is_frozen(self):
        """不変である"""
        info = my_lib.weather.WeatherInfo(text="晴れ", icon_url="http://example.com/sunny.png")

        with pytest.raises(AttributeError):
            info.text = "曇り"  # type: ignore


class TestWindInfo:
    """WindInfo データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        wind = my_lib.weather.WindInfo(dir="北", speed=5)

        assert wind.dir == "北"
        assert wind.speed == 5


class TestHourlyData:
    """HourlyData データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        weather = my_lib.weather.WeatherInfo(text="晴れ", icon_url="http://example.com/sunny.png")
        wind = my_lib.weather.WindInfo(dir="北", speed=5)

        hourly = my_lib.weather.HourlyData(
            hour=12,
            weather=weather,
            temp=25.0,
            humi=60.0,
            precip=0.0,
            wind=wind,
        )

        assert hourly.hour == 12
        assert hourly.temp == 25.0
        assert hourly.humi == 60.0
        assert hourly.precip == 0.0


class TestDayData:
    """DayData データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        date = datetime.datetime(2024, 1, 1, 0, 0, 0)

        day = my_lib.weather.DayData(date=date)

        assert day.date == date
        assert day.data == []

    def test_creates_with_data(self):
        """データ付きでインスタンスを作成する"""
        date = datetime.datetime(2024, 1, 1, 0, 0, 0)
        weather = my_lib.weather.WeatherInfo(text="晴れ", icon_url="http://example.com/sunny.png")
        wind = my_lib.weather.WindInfo(dir="北", speed=5)
        hourly = my_lib.weather.HourlyData(
            hour=12, weather=weather, temp=25.0, humi=60.0, precip=0.0, wind=wind
        )

        day = my_lib.weather.DayData(date=date, data=[hourly])

        assert len(day.data) == 1


class TestWeatherResult:
    """WeatherResult データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        today = my_lib.weather.DayData(date=datetime.datetime(2024, 1, 1))
        tomorrow = my_lib.weather.DayData(date=datetime.datetime(2024, 1, 2))

        result = my_lib.weather.WeatherResult(today=today, tomorrow=tomorrow)

        assert result.today.date.day == 1
        assert result.tomorrow.date.day == 2


class TestClothingData:
    """ClothingData データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        date = datetime.datetime(2024, 1, 1)

        clothing = my_lib.weather.ClothingData(date=date, data=50)

        assert clothing.date == date
        assert clothing.data == 50


class TestClothingResult:
    """ClothingResult データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        today = my_lib.weather.ClothingData(date=datetime.datetime(2024, 1, 1), data=50)
        tomorrow = my_lib.weather.ClothingData(date=datetime.datetime(2024, 1, 2), data=60)

        result = my_lib.weather.ClothingResult(today=today, tomorrow=tomorrow)

        assert result.today.data == 50
        assert result.tomorrow.data == 60


class TestWbgtDailyData:
    """WbgtDailyData データクラスのテスト"""

    def test_creates_instance_with_defaults(self):
        """デフォルト値でインスタンスを作成する"""
        wbgt = my_lib.weather.WbgtDailyData()

        assert wbgt.today is None
        assert wbgt.tomorrow is None

    def test_creates_instance_with_data(self):
        """データ付きでインスタンスを作成する"""
        wbgt = my_lib.weather.WbgtDailyData(
            today=[25, 26, 27, None, 28],
            tomorrow=[30, 31, 32, 33, 34],
        )

        assert wbgt.today == [25, 26, 27, None, 28]
        assert wbgt.tomorrow == [30, 31, 32, 33, 34]


class TestWbgtResult:
    """WbgtResult データクラスのテスト"""

    def test_creates_instance_with_defaults(self):
        """デフォルト値でインスタンスを作成する"""
        result = my_lib.weather.WbgtResult()

        assert result.current is None
        assert result.daily.today is None
        assert result.daily.tomorrow is None

    def test_creates_instance_with_data(self):
        """データ付きでインスタンスを作成する"""
        daily = my_lib.weather.WbgtDailyData(today=[25, 26], tomorrow=[30, 31])

        result = my_lib.weather.WbgtResult(current=28.5, daily=daily)

        assert result.current == 28.5
        assert result.daily.today == [25, 26]
