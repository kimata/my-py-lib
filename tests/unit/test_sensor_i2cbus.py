#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/i2cbus.py のテスト"""
from __future__ import annotations

import unittest.mock

import pytest

from my_lib.sensor.i2cbus import I2CBUS


class TestI2CBUS:
    """I2CBUS クラスのテスト"""

    def test_arm_bus_id(self):
        """ARM バスIDが 0x1 である"""
        assert I2CBUS.ARM == 0x1

    def test_vc_bus_id(self):
        """VC バスIDが 0x0 である"""
        assert I2CBUS.VC == 0x0

    def test_init_creates_smbus(self):
        """初期化時に SMBus を作成する"""
        bus = I2CBUS(1)
        assert bus.bus_id == 1
        assert bus.smbus is not None

    def test_write_byte_data(self):
        """write_byte_data を呼び出す"""
        bus = I2CBUS(1)
        bus.smbus = unittest.mock.MagicMock()

        bus.write_byte_data(0x42, 0x10, 0xFF)

        bus.smbus.write_byte_data.assert_called_once_with(0x42, 0x10, 0xFF)

    def test_read_i2c_block_data(self):
        """read_i2c_block_data を呼び出す"""
        bus = I2CBUS(1)
        bus.smbus = unittest.mock.MagicMock()
        bus.smbus.read_i2c_block_data.return_value = [0x01, 0x02, 0x03]

        data = bus.read_i2c_block_data(0x42, 0x00, 3)

        bus.smbus.read_i2c_block_data.assert_called_once_with(0x42, 0x00, 3)
        assert data == [0x01, 0x02, 0x03]

    def test_read_byte_data(self):
        """read_byte_data を呼び出す"""
        bus = I2CBUS(1)
        bus.smbus = unittest.mock.MagicMock()
        bus.smbus.read_byte_data.return_value = 0x42

        data = bus.read_byte_data(0x42, 0x00)

        bus.smbus.read_byte_data.assert_called_once_with(0x42, 0x00)
        assert data == 0x42


class TestI2CBUSMsg:
    """I2CBUS.msg クラスのテスト"""

    def test_read_method_exists(self):
        """read メソッドが存在する"""
        assert hasattr(I2CBUS.msg, "read")
        assert callable(I2CBUS.msg.read)

    def test_write_method_exists(self):
        """write メソッドが存在する"""
        assert hasattr(I2CBUS.msg, "write")
        assert callable(I2CBUS.msg.write)
