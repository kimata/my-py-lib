#!/usr/bin/env python3
"""CRC 計算ユーティリティ"""

from __future__ import annotations


def crc8_sensirion(data: bytes | list[int]) -> int:
    """Sensirion センサー用 CRC-8 を計算する

    SHT35, SCD4x などの Sensirion センサーで使用されるCRC-8アルゴリズム。
    多項式: x^8 + x^5 + x^4 + 1 (0x31)
    初期値: 0xFF

    Args:
        data: CRC を計算するデータ

    Returns:
        計算された CRC-8 値
    """
    poly = 0x31
    crc = 0xFF

    for byte in bytearray(data):
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFF

    return crc


def crc16_modbus(data: list[int]) -> list[int]:
    """Modbus CRC-16 を計算する

    Modbus RTU で使用される CRC-16 アルゴリズム。
    多項式: 0xA001 (反転多項式)
    初期値: 0xFFFF

    Args:
        data: CRC を計算するデータ

    Returns:
        CRC の下位バイトと上位バイトのリスト [low, high]
    """
    poly = 0xA001
    crc = 0xFFFF

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1

    return [crc & 0xFF, (crc >> 8) & 0xFF]
