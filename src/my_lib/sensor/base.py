#!/usr/bin/env python3
"""センサー基底クラス定義"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from my_lib.sensor import i2cbus

# センサー値の型定義
SensorValue = float | int | bool


class SensorBase(ABC):
    """全センサーの基底クラス"""

    NAME: str = "Unknown"
    TYPE: str = "Unknown"
    required: bool = False

    @abstractmethod
    def ping(self) -> bool:
        """センサーが応答するかを確認する

        Returns:
            応答があれば True、なければ False
        """
        ...

    @abstractmethod
    def get_value_map(self) -> dict[str, SensorValue]:
        """センサー値を辞書で取得する"""
        ...


class I2CSensorBase(SensorBase):
    """I2C センサーの基底クラス"""

    TYPE: str = "I2C"
    DEV_ADDR: int = 0x00

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int | None = None) -> None:
        """I2C センサーを初期化する

        Args:
            bus_id: I2C バス番号
            dev_addr: デバイスアドレス（省略時はクラスのデフォルト値）
        """
        self.bus_id: int = bus_id
        self.dev_addr: int = dev_addr if dev_addr is not None else self.DEV_ADDR
        self.i2cbus: i2cbus.I2CBUS = i2cbus.I2CBUS(bus_id)

    def ping(self) -> bool:
        """センサーが応答するかを確認する

        Returns:
            応答があれば True、なければ False
        """
        logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)
        try:
            return self._ping_impl()
        except OSError:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    @abstractmethod
    def _ping_impl(self) -> bool:
        """ping の実装（サブクラスでオーバーライド）"""
        ...
