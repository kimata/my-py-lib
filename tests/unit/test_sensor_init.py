#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/__init__.py のテスト"""

from __future__ import annotations

import unittest.mock

import pytest


class MockSensor:
    """テスト用のモックセンサー"""

    def __init__(self, name: str = "MockSensor", sensor_type: str = "I2C", dev_addr: int = 0x42):
        self.NAME = name
        self.TYPE = sensor_type
        self.dev_addr = dev_addr
        self.required = False
        self._ping_result = True
        self._values: dict[str, float] = {}

    def ping(self) -> bool:
        return self._ping_result

    def get_value_map(self) -> dict[str, float]:
        return self._values


@pytest.fixture
def mock_smbus():
    """smbus2 をモックする"""
    mock = unittest.mock.MagicMock()
    with unittest.mock.patch.dict("sys.modules", {"smbus2": mock}):
        yield mock


class TestSensorInfo:
    """sensor_info 関数のテスト"""

    def test_i2c_sensor_info(self, mock_smbus):
        """I2C センサーの情報を返す"""
        from my_lib.sensor import sensor_info

        sensor = MockSensor(name="SHT35", sensor_type="I2C", dev_addr=0x44)
        info = sensor_info(sensor)

        assert info == "SHT35 (I2C: 0x44)"

    def test_non_i2c_sensor_info(self, mock_smbus):
        """非 I2C センサーの情報を返す"""
        from my_lib.sensor import sensor_info

        sensor = MockSensor(name="RG-15", sensor_type="UART", dev_addr=0x00)
        info = sensor_info(sensor)

        assert info == "RG-15 (UART)"


class TestPing:
    """ping 関数のテスト"""

    def test_returns_active_sensors(self, mock_smbus):
        """応答があるセンサーのリストを返す"""
        from my_lib.sensor import ping

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = True
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = True

        result = ping([sensor1, sensor2])

        assert len(result) == 2
        assert sensor1 in result
        assert sensor2 in result

    def test_filters_inactive_sensors(self, mock_smbus):
        """応答がないセンサーを除外する"""
        from my_lib.sensor import ping

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = True
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = False

        result = ping([sensor1, sensor2])

        assert len(result) == 1
        assert sensor1 in result
        assert sensor2 not in result

    def test_raises_for_required_missing_sensor(self, mock_smbus):
        """必須センサーが見つからない場合は例外を発生"""
        from my_lib.sensor import ping

        sensor = MockSensor(name="RequiredSensor")
        sensor._ping_result = False
        sensor.required = True

        with pytest.raises(RuntimeError, match="required sensor"):
            ping([sensor])

    def test_empty_list_returns_empty(self, mock_smbus):
        """空のリストを渡すと空のリストを返す"""
        from my_lib.sensor import ping

        result = ping([])

        assert result == []


class TestSense:
    """sense 関数のテスト"""

    def test_collects_values_from_sensors(self, mock_smbus):
        """センサーから値を収集する"""
        from my_lib.sensor import sense

        sensor1 = MockSensor(name="Sensor1")
        sensor1._values = {"temp": 25.0}
        sensor2 = MockSensor(name="Sensor2")
        sensor2._values = {"humidity": 60.0}

        value_map, is_success = sense([sensor1, sensor2])

        assert value_map == {"temp": 25.0, "humidity": 60.0}
        assert is_success is True

    def test_returns_false_on_exception(self, mock_smbus):
        """例外が発生した場合は is_success が False"""
        from my_lib.sensor import sense

        sensor = MockSensor(name="FailingSensor")

        def raise_error():
            raise OSError("Sensor error")

        sensor.get_value_map = raise_error  # type: ignore

        value_map, is_success = sense([sensor])

        assert is_success is False

    def test_continues_after_exception(self, mock_smbus):
        """例外が発生しても他のセンサーの値を収集する"""
        from my_lib.sensor import sense

        sensor1 = MockSensor(name="FailingSensor")

        def raise_error():
            raise OSError("Sensor error")

        sensor1.get_value_map = raise_error  # type: ignore

        sensor2 = MockSensor(name="WorkingSensor")
        sensor2._values = {"temp": 25.0}

        value_map, is_success = sense([sensor1, sensor2])

        assert value_map == {"temp": 25.0}
        assert is_success is False

    def test_empty_list_returns_empty(self, mock_smbus):
        """空のリストを渡すと空の値マップを返す"""
        from my_lib.sensor import sense

        value_map, is_success = sense([])

        assert value_map == {}
        assert is_success is True


class TestLoad:
    """load 関数のテスト"""

    @pytest.fixture
    def mock_sensor_module(self, mock_smbus):
        """my_lib.sensor モジュールをモックする"""
        mock_sensor_class = unittest.mock.MagicMock()
        mock_sensor_instance = MockSensor()
        mock_sensor_class.return_value = mock_sensor_instance

        with unittest.mock.patch("my_lib.sensor.my_lib.sensor") as mock_module:
            mock_module.sht35 = mock_sensor_class

            mock_i2cbus = unittest.mock.MagicMock()
            mock_i2cbus.I2CBUS.ARM = 0x1
            mock_module.i2cbus = mock_i2cbus

            yield mock_module, mock_sensor_class, mock_sensor_instance

    def test_loads_i2c_sensor(self, mock_sensor_module):
        """I2C センサーをロードする"""
        from my_lib.sensor import load

        mock_module, mock_sensor_class, mock_sensor_instance = mock_sensor_module

        sensor_def_list = [
            {"name": "sht35"},
        ]

        result = load(sensor_def_list)

        assert len(result) == 1

    def test_sets_required_flag(self, mock_sensor_module):
        """required フラグを設定する"""
        from my_lib.sensor import load

        mock_module, mock_sensor_class, mock_sensor_instance = mock_sensor_module

        sensor_def_list = [
            {"name": "sht35", "required": True},
        ]

        result = load(sensor_def_list)

        assert result[0].required is True
