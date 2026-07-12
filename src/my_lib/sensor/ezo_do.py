#!/usr/bin/env python3
"""
EZO-DO を使って溶存酸素 (DO) を取得するライブラリです。

Usage:
  ezo_do.py [-b BUS] [-d DEV_ADDR] [-C DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x68]
  -C DEV_ADDR       : デバイスアドレスを変更します。
  -D                : デバッグモードで動作します。
"""

# NOTE: Atlas Scientific の工場出荷時デフォルトアドレスは 0x61。
# 既存の運用機材が 0x68 に変更済みのため、クラスのデフォルトは 0x68 としている。

from __future__ import annotations

from my_lib.sensor.ezo_base import EZOBase


class EZO_DO(EZOBase):
    NAME: str = "EZO-DO"
    DEV_ADDR: int = 0x68  # 7bit
    DEVICE_ID: str = "DO"

    def _ping_impl(self) -> bool:
        # NOTE: ファームウェアの版によってデバイス名が "DO" と "D.O." の両方があり得る
        return self.exec_command("i").split(",")[1] in ("DO", "D.O.")

    def get_value(self) -> float:
        return round(float(self.exec_command("R")), 3)

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"do": value}


if __name__ == "__main__":
    # TEST Code
    import logging

    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    dev_addr_new = args["-C"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = EZO_DO(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)

    if ping:
        if dev_addr_new is not None:
            dev_addr_new = int(dev_addr_new)
            logging.info("Change dev addr 0x%02X to 0x%02X", dev_addr, dev_addr_new)
            sensor.change_devaddr(dev_addr_new)
        else:
            logging.info("VALUE: %s", sensor.get_value_map())
