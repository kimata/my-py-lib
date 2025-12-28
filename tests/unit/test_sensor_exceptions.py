#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/exceptions.py のテスト"""
from __future__ import annotations

import pytest

from my_lib.sensor.exceptions import SensorCommunicationError, SensorCRCError, SensorError


class TestSensorError:
    """SensorError のテスト"""

    def test_is_exception(self):
        """Exception を継承している"""
        assert issubclass(SensorError, Exception)

    def test_can_raise(self):
        """例外として raise できる"""
        with pytest.raises(SensorError):
            raise SensorError("test error")

    def test_message(self):
        """メッセージを保持する"""
        error = SensorError("test message")
        assert str(error) == "test message"


class TestSensorCommunicationError:
    """SensorCommunicationError のテスト"""

    def test_inherits_sensor_error(self):
        """SensorError を継承している"""
        assert issubclass(SensorCommunicationError, SensorError)

    def test_can_raise(self):
        """例外として raise できる"""
        with pytest.raises(SensorCommunicationError):
            raise SensorCommunicationError("communication failed")

    def test_can_catch_as_sensor_error(self):
        """SensorError として catch できる"""
        with pytest.raises(SensorError):
            raise SensorCommunicationError("communication failed")


class TestSensorCRCError:
    """SensorCRCError のテスト"""

    def test_inherits_sensor_error(self):
        """SensorError を継承している"""
        assert issubclass(SensorCRCError, SensorError)

    def test_can_raise(self):
        """例外として raise できる"""
        with pytest.raises(SensorCRCError):
            raise SensorCRCError("CRC mismatch")

    def test_can_catch_as_sensor_error(self):
        """SensorError として catch できる"""
        with pytest.raises(SensorError):
            raise SensorCRCError("CRC mismatch")
