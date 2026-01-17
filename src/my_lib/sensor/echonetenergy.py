#!/usr/bin/env python3
"""
ECHONET Lite を使って電力系から電力を取得するライブラリです。

Usage:
  echonetenergy.py [-c CONFIG] [-i IF_DEV] [-d DEV] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -i IF_DEV         : ECHONET Lite のインターフェースデバイスを指定します。[default: BP35A1]
  -d DEV_FILE       : デバイスファイルを指定します。[default: /dev/ttyAMA0]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import pathlib
import pickle
import pprint
import struct
import tempfile
from typing import Any

import my_lib.sensor
from my_lib.sensor.echonetlite import ECHONETLite, EchonetLiteFrame, EchonetLiteProperty

PAN_DESC_DAT_PATH: pathlib.Path = pathlib.Path(tempfile.gettempdir()) / "pan_desc.dat"
RETRY_COUNT: int = 5


class EchonetEnergy:
    NAME: str = "EchonetEnergy"
    TYPE: str = "UART"

    def __init__(self, dev_file: str, param: dict[str, Any], debug: bool = False) -> None:
        echonet_if = getattr(my_lib.sensor, param["if"].lower())(dev_file, debug)

        self.b_id: str = param["id"]
        self.b_pass: str = param["pass"]

        self.echonet_if: Any = echonet_if
        self.ipv6_addr: str | None = None
        self.is_connected: bool = False

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.logger.setLevel(logging.DEBUG if debug else logging.WARNING)

    def ping(self) -> bool:
        return self.echonet_if.ping()

    def parse_frame(self, recv_packet: bytes) -> EchonetLiteFrame:
        self.logger.debug("recv_packet = \n%s", pprint.pformat(recv_packet, indent=2))
        frame = ECHONETLite.parse_frame(recv_packet)
        self.logger.debug("frame = \n%s", pprint.pformat(frame, indent=2))

        return frame

    # PAN ID の探索 (キャッシュ付き)
    def get_pan_info(self) -> dict[str, str] | None:
        if PAN_DESC_DAT_PATH.exists():
            with PAN_DESC_DAT_PATH.open(mode="rb") as f:
                try:
                    pan_info = pickle.load(f)  # noqa: S301
                    if isinstance(pan_info, dict):
                        return pan_info
                except Exception:  # noqa: S110
                    pass

        pan_info = self.get_pan_info_impl()

        with PAN_DESC_DAT_PATH.open(mode="wb") as f:
            pickle.dump(pan_info, f)

        return pan_info

    def get_pan_info_impl(self) -> dict[str, str] | None:
        return self.echonet_if.scan_channel()

    def connect(self, pan_info: dict[str, str]) -> None:
        self.echonet_if.set_id(self.b_id)
        self.echonet_if.set_password(self.b_pass)

        self.ipv6_addr = self.echonet_if.connect(pan_info)
        if self.ipv6_addr is None:
            raise RuntimeError("Failed to connect Wi-SUN")

        # NOTE: インスタンスリスト通知メッセージが来ない場合があるので
        # チェックを省略

        # for i in range(RETRY_COUNT):
        #     recv_packet = self.echonet_if.recv_udp(self.ipv6_addr)

        #     frame = self.parse_frame(recv_packet)
        #     if ((frame.edata.seoj == 0x0EF001) and
        #         (frame.edata.deoj == 0x0EF001)):
        #         break

        # # インスタンスリスト
        # inst_list = ECHONETLite.parse_inst_list(
        #     frame.edata.props[0].edt)

        # # 低圧スマート電力量メータクラスがあるか確認
        # is_meter_exit = ECHONETLite.check_class(
        #     inst_list, 0x02, 0x88)

        # if not is_meter_exit:
        #     raise Exception('Meter not found')

    def disconnect(self) -> None:
        self.echonet_if.disconnect()

    def get_value(self) -> list[int]:
        if not self.is_connected:
            pan_info = self.get_pan_info()
            if pan_info is None:
                raise RuntimeError("Failed to get PAN info")
            self.connect(pan_info)
            self.is_connected = True

        meter_eoj = ECHONETLite.build_eoj(
            ECHONETLite.EOJ.CLASS_GROUP_HOUSING,
            ECHONETLite.EOJ.HOUSE_CLASS_GROUP.LOW_VOLTAGE_SMART_METER,
        )

        edata = ECHONETLite.build_edata(
            ECHONETLite.build_eoj(
                ECHONETLite.EOJ.CLASS_GROUP_MANAGEMENT,
                ECHONETLite.EOJ.MANAGEMENT_CLASS_GROUP.CONTROLLER,
            ),
            meter_eoj,
            ECHONETLite.ESV.PROP_READ,
            [
                EchonetLiteProperty(
                    epc=ECHONETLite.EPC.LOW_VOLTAGE_SMART_METER.INSTANTANEOUS_ENERGY,
                    pdc=0,
                )
            ],
        )
        send_packet = ECHONETLite.build_frame(edata)

        while True:
            self.echonet_if.send_udp(self.ipv6_addr, ECHONETLite.UDP_PORT, send_packet)
            recv_packet = self.echonet_if.recv_udp(self.ipv6_addr)
            frame = self.parse_frame(recv_packet)

            if frame.edata is None:
                continue
            if frame.edata.seoj != meter_eoj:
                continue
            for prop in frame.edata.props:
                if prop.epc != ECHONETLite.EPC.LOW_VOLTAGE_SMART_METER.INSTANTANEOUS_ENERGY:
                    continue
                if prop.edt is None or len(prop.edt) != prop.pdc:
                    continue
                return [struct.unpack(">I", prop.edt)[0]]

    def get_value_map(self) -> dict[str, int]:
        value = self.get_value()

        return {"power": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    if_dev = args["-i"]
    dev_file = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    sensor = EchonetEnergy(dev_file, {**config, "if": if_dev})

    ping = sensor.ping()
    logging.info("PING: %s", ping)

    if ping:
        while True:
            logging.info(sensor.get_value_map())
