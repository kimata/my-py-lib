#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.rpi モジュールのユニットテスト
"""

from __future__ import annotations

import time

import pytest


class TestIsRasberryPi:
    """is_rasberry_pi 関数のテスト"""

    def test_returns_boolean(self):
        """真偽値を返す"""
        import my_lib.rpi

        result = my_lib.rpi.is_rasberry_pi()
        assert isinstance(result, bool)


class TestGpioSetmode:
    """gpio.setmode メソッドのテスト"""

    def test_does_not_raise(self):
        """エラーを発生させない"""
        import my_lib.rpi

        my_lib.rpi.gpio.setmode(my_lib.rpi.gpio.BCM)


class TestGpioSetup:
    """gpio.setup メソッドのテスト"""

    def test_does_not_raise_for_valid_pin(self):
        """有効なピンでエラーを発生させない"""
        import my_lib.rpi

        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)

    def test_raises_for_invalid_pin(self):
        """無効なピンでエラーを発生させる"""
        import my_lib.rpi

        with pytest.raises(ValueError, match="not a valid GPIO pin"):
            my_lib.rpi.gpio.setup(100, my_lib.rpi.gpio.OUT)


class TestGpioOutput:
    """gpio.output メソッドのテスト"""

    def test_sets_pin_low(self):
        """ピンを LOW に設定する"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)
        my_lib.rpi.gpio.output(10, 0)

        assert my_lib.rpi.gpio.input(10) == 0

    def test_sets_pin_high(self):
        """ピンを HIGH に設定する"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)
        my_lib.rpi.gpio.output(10, 1)

        assert my_lib.rpi.gpio.input(10) == 1

    def test_raises_for_invalid_pin(self):
        """無効なピンでエラーを発生させる"""
        import my_lib.rpi

        with pytest.raises(ValueError, match="not a valid GPIO pin"):
            my_lib.rpi.gpio.output(100, 0)


class TestGpioInput:
    """gpio.input メソッドのテスト"""

    def test_returns_pin_state(self):
        """ピンの状態を返す"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)
        my_lib.rpi.gpio.output(10, 1)

        assert my_lib.rpi.gpio.input(10) == 1

    def test_raises_for_invalid_pin(self):
        """無効なピンでエラーを発生させる"""
        import my_lib.rpi

        with pytest.raises(ValueError, match="not a valid GPIO pin"):
            my_lib.rpi.gpio.input(100)


class TestGpioHistory:
    """GPIO 履歴機能のテスト"""

    def test_hist_get_returns_list(self):
        """履歴リストを返す"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        result = my_lib.rpi.gpio.hist_get()

        assert isinstance(result, list)

    def test_hist_clear_empties_history(self):
        """履歴をクリアする"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)
        my_lib.rpi.gpio.output(10, 0)

        assert len(my_lib.rpi.gpio.hist_get()) > 0

        my_lib.rpi.gpio.hist_clear()
        assert my_lib.rpi.gpio.hist_get() == []

    def test_records_output_operations(self):
        """出力操作を記録する"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)

        my_lib.rpi.gpio.output(10, 0)
        my_lib.rpi.gpio.output(10, 1)
        my_lib.rpi.gpio.output(10, 0)

        hist = my_lib.rpi.gpio.hist_get()
        assert len(hist) == 3
        assert hist[0]["state"] == "LOW"
        assert hist[1]["state"] == "HIGH"
        assert hist[2]["state"] == "LOW"

    def test_records_high_period(self):
        """HIGH 期間を記録する"""
        import my_lib.rpi

        my_lib.rpi.gpio.hist_clear()
        my_lib.rpi.gpio.setup(10, my_lib.rpi.gpio.OUT)

        my_lib.rpi.gpio.output(10, 1)
        time.sleep(1.1)
        my_lib.rpi.gpio.output(10, 0)

        hist = my_lib.rpi.gpio.hist_get()
        assert "high_period" in hist[-1]
        assert hist[-1]["high_period"] >= 1


class TestGpioSetwarnings:
    """gpio.setwarnings メソッドのテスト"""

    def test_does_not_raise(self):
        """エラーを発生させない"""
        import my_lib.rpi

        my_lib.rpi.gpio.setwarnings(False)
        my_lib.rpi.gpio.setwarnings(True)


class TestGpioCleanup:
    """gpio.cleanup メソッドのテスト"""

    def test_does_not_raise(self):
        """エラーを発生させない"""
        import my_lib.rpi

        my_lib.rpi.gpio.cleanup()
        my_lib.rpi.gpio.cleanup([10, 11])
