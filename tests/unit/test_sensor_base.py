#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/base.py のテスト"""

from __future__ import annotations

import unittest.mock

import pytest


class TestSensorBase:
    """SensorBase クラスのテスト"""

    def test_is_abstract(self):
        """抽象クラスである"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorBase

            with pytest.raises(TypeError, match="abstract"):
                SensorBase()  # type: ignore[reportAbstractUsage]

    def test_has_name_attribute(self):
        """NAME 属性を持つ"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorBase

            assert hasattr(SensorBase, "NAME")
            assert SensorBase.NAME == "Unknown"

    def test_has_type_attribute(self):
        """TYPE 属性を持つ"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorBase

            assert hasattr(SensorBase, "TYPE")
            assert SensorBase.TYPE == "Unknown"

    def test_has_required_attribute(self):
        """required 属性を持つ"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorBase

            assert hasattr(SensorBase, "required")
            assert SensorBase.required is False


class TestI2CSensorBase:
    """I2CSensorBase クラスのテスト"""

    @pytest.fixture
    def mock_smbus(self):
        """smbus2 をモックする"""
        mock = unittest.mock.MagicMock()
        with unittest.mock.patch.dict("sys.modules", {"smbus2": mock}):
            yield mock

    def test_is_abstract(self, mock_smbus):
        """抽象クラスである（_ping_impl が未実装）"""
        from my_lib.sensor.base import I2CSensorBase

        with pytest.raises(TypeError, match="abstract"):
            I2CSensorBase()  # type: ignore[reportAbstractUsage]

    def test_type_is_i2c(self, mock_smbus):
        """TYPE が 'I2C' である"""
        from my_lib.sensor.base import I2CSensorBase

        assert I2CSensorBase.TYPE == "I2C"

    def test_default_dev_addr(self, mock_smbus):
        """デフォルトのデバイスアドレスが 0x00"""
        from my_lib.sensor.base import I2CSensorBase

        assert I2CSensorBase.DEV_ADDR == 0x00

    def test_init_with_defaults(self, mock_smbus):
        """デフォルト値で初期化できる"""
        from my_lib.sensor.base import I2CSensorBase

        class TestSensor(I2CSensorBase):
            NAME = "Test"
            DEV_ADDR = 0x42

            def _ping_impl(self) -> bool:
                return True

            def get_value_map(self):
                return {}

        sensor = TestSensor()
        assert sensor.bus_id == 0x1
        assert sensor.dev_addr == 0x42

    def test_init_with_custom_address(self, mock_smbus):
        """カスタムアドレスで初期化できる"""
        from my_lib.sensor.base import I2CSensorBase

        class TestSensor(I2CSensorBase):
            NAME = "Test"
            DEV_ADDR = 0x42

            def _ping_impl(self) -> bool:
                return True

            def get_value_map(self):
                return {}

        sensor = TestSensor(dev_addr=0x50)
        assert sensor.dev_addr == 0x50

    def test_init_with_custom_bus(self, mock_smbus):
        """カスタムバスIDで初期化できる"""
        from my_lib.sensor.base import I2CSensorBase

        class TestSensor(I2CSensorBase):
            NAME = "Test"

            def _ping_impl(self) -> bool:
                return True

            def get_value_map(self):
                return {}

        sensor = TestSensor(bus_id=0)
        assert sensor.bus_id == 0

    def test_ping_returns_true_on_success(self, mock_smbus):
        """ping 成功時に True を返す"""
        from my_lib.sensor.base import I2CSensorBase

        class TestSensor(I2CSensorBase):
            NAME = "Test"

            def _ping_impl(self) -> bool:
                return True

            def get_value_map(self):
                return {}

        sensor = TestSensor()
        assert sensor.ping() is True

    def test_ping_returns_false_on_exception(self, mock_smbus):
        """ping で例外が発生した場合に False を返す"""
        from my_lib.sensor.base import I2CSensorBase

        class TestSensor(I2CSensorBase):
            NAME = "Test"

            def _ping_impl(self) -> bool:
                raise OSError("I2C error")

            def get_value_map(self):
                return {}

        sensor = TestSensor()
        assert sensor.ping() is False

    def test_ping_calls_ping_impl(self, mock_smbus):
        """ping が _ping_impl を呼び出す"""
        from my_lib.sensor.base import I2CSensorBase

        class TestSensor(I2CSensorBase):
            NAME = "Test"
            ping_called = False

            def _ping_impl(self) -> bool:
                TestSensor.ping_called = True
                return True

            def get_value_map(self):
                return {}

        sensor = TestSensor()
        sensor.ping()
        assert TestSensor.ping_called is True


class TestSensorValue:
    """SensorValue 型のテスト"""

    def test_accepts_float(self):
        """float を受け付ける"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorValue

            value: SensorValue = 25.5
            assert isinstance(value, float)

    def test_accepts_int(self):
        """int を受け付ける"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorValue

            value: SensorValue = 100
            assert isinstance(value, int)

    def test_accepts_bool(self):
        """bool を受け付ける"""
        with unittest.mock.patch.dict("sys.modules", {"smbus2": unittest.mock.MagicMock()}):
            from my_lib.sensor.base import SensorValue

            value: SensorValue = True
            assert isinstance(value, bool)
