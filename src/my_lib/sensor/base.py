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

    # NOTE: クラス変数として既定値を持たせ、サブクラスが super().__init__() を
    # 呼ばなくても hasattr で見つかる安全装置とする。
    # 実体は __init__ でインスタンス変数として上書き初期化される。
    required: bool = False
    consecutive_fails: int = 0

    def __init__(self) -> None:
        # NOTE: my_lib.sensor.sense() が連続失敗回数を読み書きするため
        # ここで必ずインスタンス変数として初期化する
        self.required = False
        self.consecutive_fails = 0

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
    """I2C センサーの基底クラス

    サブクラスは _ping_impl をオーバーライドして実装する。
    独自の ping ロジックが必要な場合は ping 自体をオーバーライドしてもよい。
    """

    TYPE: str = "I2C"
    DEV_ADDR: int = 0x00

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int | None = None) -> None:
        """I2C センサーを初期化する

        Args:
            bus_id: I2C バス番号
            dev_addr: デバイスアドレス（省略時はクラスのデフォルト値）
        """
        super().__init__()
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

    def _ping_impl(self) -> bool:
        """ping の実装。

        I2CSensorBase の `ping()` を利用するサブクラスはこのメソッドを実装する。
        `ping()` 自体をオーバーライドするサブクラスは実装不要。
        """
        raise NotImplementedError


class UARTSensorBase(SensorBase):
    """UART/シリアル接続センサーの基底クラス

    UART センサーは個々の通信プロトコルが大きく異なるため、
    本基底クラスは TYPE と consecutive_fails の初期化のみを担う。
    """

    TYPE: str = "UART"
