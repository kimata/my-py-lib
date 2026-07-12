#!/usr/bin/env python3
"""Atlas Scientific EZO シリーズセンサーの共通基底クラス"""

from __future__ import annotations

import contextlib
import time

from my_lib.sensor.base import I2CSensorBase
from my_lib.sensor.exceptions import SensorCommunicationError


class EZOBase(I2CSensorBase):
    """EZO シリーズ (pH / RTD / DO など) の共通処理。

    応答フォーマットは先頭 1 バイトがステータスコード
    (1=成功, 2=構文エラー, 254=処理中, 255=データなし)、以降が ASCII データ。
    """

    # NOTE: "i" コマンドの応答 "?I,<デバイス名>,<バージョン>" に含まれるデバイス名。
    # サブクラスでオーバーライドする。
    DEVICE_ID: str = ""

    # NOTE: Atlas 公式サンプルに合わせた読み出しサイズ。応答は NUL 終端される。
    RESPONSE_LENGTH: int = 31

    STATUS_OK: int = 1
    STATUS_PROCESSING: int = 254
    STATUS_NO_DATA: int = 255

    def __init__(self, bus_id: int | None = None, dev_addr: int | None = None) -> None:
        from my_lib.sensor import i2cbus

        super().__init__(
            bus_id=bus_id if bus_id is not None else i2cbus.I2CBUS.ARM,
            dev_addr=dev_addr,
        )

    def _ping_impl(self) -> bool:
        return self.exec_command("i").split(",")[1] == self.DEVICE_ID

    def exec_command(self, cmd: str, delay: float = 1.0) -> str:
        """コマンドを実行し、ステータス検査済みの応答文字列 (ステータスバイト除く) を返す。"""
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, list(cmd.encode())))

        time.sleep(delay)

        read = self.i2cbus.msg.read(self.dev_addr, self.RESPONSE_LENGTH)
        self.i2cbus.i2c_rdwr(read)
        raw = bytes(read)

        status = raw[0]
        if status == self.STATUS_PROCESSING:
            raise SensorCommunicationError(f"{self.NAME}: 応答が未完 (処理中)")
        if status == self.STATUS_NO_DATA:
            raise SensorCommunicationError(f"{self.NAME}: 送信すべきデータなし")
        if status != self.STATUS_OK:
            raise SensorCommunicationError(f"{self.NAME}: エラー応答 (status={status})")

        return raw[1:].split(b"\x00", 1)[0].decode()

    def change_devaddr(self, dev_addr_new: int) -> None:
        # NOTE: アドレスを変更したときは NACK が帰ってくるっぽいので、エラーは無視する
        with contextlib.suppress(OSError, SensorCommunicationError):
            self.exec_command(f"I2C,{dev_addr_new}")
