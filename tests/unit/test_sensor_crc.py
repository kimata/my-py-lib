#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/crc.py のテスト"""
from __future__ import annotations

import pytest

from my_lib.sensor.crc import crc8_sensirion, crc16_modbus


class TestCrc8Sensirion:
    """crc8_sensirion 関数のテスト"""

    def test_empty_data(self):
        """空データの場合は初期値 0xFF を返す"""
        result = crc8_sensirion(b"")
        assert result == 0xFF

    def test_single_byte_zero(self):
        """0x00 の CRC"""
        result = crc8_sensirion(b"\x00")
        assert isinstance(result, int)
        assert 0 <= result <= 255

    def test_known_value_from_sht35(self):
        """SHT35 の既知データでの CRC 検証

        Sensirion のデータシートから:
        データ: 0xBEEF -> CRC: 0x92
        """
        result = crc8_sensirion([0xBE, 0xEF])
        assert result == 0x92

    def test_another_known_value(self):
        """別の既知データでの CRC 検証

        データ: 0x0000 -> CRC: 0x81
        """
        result = crc8_sensirion([0x00, 0x00])
        assert result == 0x81

    def test_accepts_bytes(self):
        """bytes 型を受け付ける"""
        result = crc8_sensirion(b"\xBE\xEF")
        assert result == 0x92

    def test_accepts_list(self):
        """list[int] 型を受け付ける"""
        result = crc8_sensirion([0xBE, 0xEF])
        assert result == 0x92

    def test_consistency(self):
        """同じデータに対して同じ結果を返す"""
        data = b"\x12\x34\x56\x78"
        result1 = crc8_sensirion(data)
        result2 = crc8_sensirion(data)
        assert result1 == result2

    def test_different_data_different_crc(self):
        """異なるデータは異なる CRC を返す"""
        crc1 = crc8_sensirion(b"\x00\x00")
        crc2 = crc8_sensirion(b"\x00\x01")
        assert crc1 != crc2


class TestCrc16Modbus:
    """crc16_modbus 関数のテスト"""

    def test_empty_data(self):
        """空データの場合は初期値 [0xFF, 0xFF] を返す"""
        result = crc16_modbus([])
        assert result == [0xFF, 0xFF]

    def test_returns_two_bytes(self):
        """2バイトのリストを返す"""
        result = crc16_modbus([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
        assert len(result) == 2
        assert all(0 <= b <= 255 for b in result)

    def test_known_modbus_value(self):
        """Modbus の既知データでの CRC 検証

        標準的な Modbus RTU フレーム:
        01 03 00 00 00 01 -> CRC: 84 0A
        """
        result = crc16_modbus([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
        assert result == [0x84, 0x0A]

    def test_another_known_value(self):
        """別の既知データでの CRC 検証

        01 06 00 01 00 03 -> CRC: 98 0B
        """
        result = crc16_modbus([0x01, 0x06, 0x00, 0x01, 0x00, 0x03])
        assert result == [0x98, 0x0B]

    def test_consistency(self):
        """同じデータに対して同じ結果を返す"""
        data = [0x01, 0x02, 0x03, 0x04]
        result1 = crc16_modbus(data)
        result2 = crc16_modbus(data)
        assert result1 == result2

    def test_different_data_different_crc(self):
        """異なるデータは異なる CRC を返す"""
        crc1 = crc16_modbus([0x00])
        crc2 = crc16_modbus([0x01])
        assert crc1 != crc2
