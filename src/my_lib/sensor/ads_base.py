#!/usr/bin/env python3
"""
ADS1015/ADS1115 シリーズ ADC の共通基底クラス。

このモジュールは ADS1015 と ADS1115 の共通機能を提供します。
"""

from __future__ import annotations

import logging
import time

from my_lib.sensor import i2cbus
from my_lib.sensor.base import I2CSensorBase
from my_lib.sensor.exceptions import SensorCommunicationError


class ADSBase(I2CSensorBase):
    """ADS1015/ADS1115 シリーズ ADC の共通基底クラス"""

    # サブクラスでオーバーライドするクラス変数
    NAME: str = ""
    DEV_ADDR: int = 0x00  # 7bit

    # レジスタアドレス
    REG_CONFIG: int = 0x01
    REG_VALUE: int = 0x00

    # FSR (Full Scale Range) 設定
    REG_CONFIG_FSR_0256: int = 5
    REG_CONFIG_FSR_2048: int = 2

    # MUX 設定
    REG_CONFIG_MUX_01: int = 0
    REG_CONFIG_MUX_0G: int = 4

    # NOTE: ADS1115 の DR=000 (8SPS) では変換に 125ms かかる。余裕を持った上限。
    CONVERSION_TIMEOUT_SEC: float = 1.0

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int | None = None) -> None:
        super().__init__(bus_id, dev_addr)

        self.mux: int = self.REG_CONFIG_MUX_01
        self.pga: int = self.REG_CONFIG_FSR_0256

    def init(self) -> None:
        # NOTE: シングルショット変換を開始する (OS=1, MODE=1)。
        # 連続変換モードだと前周期の古い変換値を読んでしまうため、
        # 変換を明示的に開始して OS ビットで完了を待つ。
        os_bit = 1
        mode = 1
        self.i2cbus.i2c_rdwr(
            self.i2cbus.msg.write(
                self.dev_addr,
                [self.REG_CONFIG, (os_bit << 7) | (self.mux << 4) | (self.pga << 1) | mode, 0x03],
            )
        )

    def _wait_conversion(self) -> None:
        """変換完了 (config レジスタ MSB の OS ビットが 1) を待つ。"""
        deadline = time.monotonic() + self.CONVERSION_TIMEOUT_SEC
        while time.monotonic() < deadline:
            read = self.i2cbus.msg.read(self.dev_addr, 2)
            self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_CONFIG]), read)
            if bytes(read)[0] & 0x80:
                return
            time.sleep(0.01)

        raise SensorCommunicationError("A/D 変換完了待ちがタイムアウト")

    def set_mux(self, mux: int) -> None:
        self.mux = mux

    def set_pga(self, pga: int) -> None:
        self.pga = pga

    def ping(self) -> bool:
        try:
            read = self.i2cbus.msg.read(self.dev_addr, 2)
            self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_CONFIG]), read)

            return bytes(read)[0] != 0
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self) -> list[float]:
        self.init()
        self._wait_conversion()

        read = self.i2cbus.msg.read(self.dev_addr, 2)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_VALUE]), read)

        raw = int.from_bytes(bytes(read), byteorder="big", signed=True)
        if self.pga == self.REG_CONFIG_FSR_0256:
            mvolt = raw * 7.8125 / 1000
        elif self.pga == self.REG_CONFIG_FSR_2048:
            mvolt = raw * 62.5 / 1000
        else:
            raise ValueError(f"Unsupported PGA value: {self.pga}")

        return [round(mvolt, 3)]

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"mvolt": value[0]}
