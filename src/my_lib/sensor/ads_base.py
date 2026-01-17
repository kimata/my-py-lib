#!/usr/bin/env python3
"""
ADS1015/ADS1115 シリーズ ADC の共通基底クラス。

このモジュールは ADS1015 と ADS1115 の共通機能を提供します。
"""

from __future__ import annotations

import time

from my_lib.sensor import i2cbus


class ADSBase:
    """ADS1015/ADS1115 シリーズ ADC の共通基底クラス"""

    # サブクラスでオーバーライドするクラス変数
    NAME: str = ""
    DEV_ADDR: int = 0x00  # 7bit

    TYPE: str = "I2C"

    # レジスタアドレス
    REG_CONFIG: int = 0x01
    REG_VALUE: int = 0x00

    # FSR (Full Scale Range) 設定
    REG_CONFIG_FSR_0256: int = 5
    REG_CONFIG_FSR_2048: int = 2

    # MUX 設定
    REG_CONFIG_MUX_01: int = 0
    REG_CONFIG_MUX_0G: int = 4

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int | None = None) -> None:
        self.bus_id: int = bus_id
        self.dev_addr: int = dev_addr if dev_addr is not None else self.DEV_ADDR
        self.i2cbus: i2cbus.I2CBUS = i2cbus.I2CBUS(bus_id)

        self.mux: int = self.REG_CONFIG_MUX_01
        self.pga: int = self.REG_CONFIG_FSR_0256

    def init(self) -> None:
        os = 1
        self.i2cbus.i2c_rdwr(
            self.i2cbus.msg.write(
                self.dev_addr,
                [self.REG_CONFIG, (os << 7) | (self.mux << 4) | (self.pga << 1), 0x03],
            )
        )

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
            return False

    def get_value(self) -> list[float]:
        self.init()
        time.sleep(0.1)

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
