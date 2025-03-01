#!/usr/bin/env python
"""
ECHONET Lite を使って電力系から電力を取得するライブラリです．

Usage:
  echonetenergy.py [-c CONFIG] [-i IF_DEV] [-d DEV] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -i IF_DEV         : ECHONET Lite のインターフェースデバイスを指定します．[default: BP35A1]
  -d DEV_FILE       : デバイスファイルを指定します．[default: /dev/ttyAMA0]
  -D                : デバッグモードで動作します．
"""

import logging
import pathlib
import pickle
import pprint
import struct
import tempfile

import my_lib.sensor.echonetlite
from my_lib.sensor.echonetlite import ECHONETLite

PAN_DESC_DAT_PATH = pathlib.Path(tempfile.gettempdir()) / "pan_desc.dat"


class EchonetEnergy:
    RETRY_COUNT = 5

    def __init__(self, echonet_if, b_id, b_pass, debug=False):  # noqa: D107
        echonet_if.set_id(b_id)
        echonet_if.set_password(b_pass)

        self.echonet_if = echonet_if
        self.ipv6_addr = None

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.logger.setLevel(logging.DEBUG if debug else logging.WARNING)

    def parse_frame(self, recv_packet):
        self.logger.debug("recv_packet = \n%s", pprint.pformat(recv_packet, indent=2))
        frame = ECHONETLite.parse_frame(recv_packet)
        self.logger.debug("frame = \n%s", pprint.pformat(frame, indent=2))

        return frame

    def get_pan_info(self):
        return self.echonet_if.scan_channel()

    def connect(self, pan_info):
        self.ipv6_addr = self.echonet_if.connect(pan_info)
        if self.ipv6_addr is None:
            raise Exception("Faile to connect Wi-SUN")  # noqa: EM101, TRY002, TRY003

        # NOTE: インスタンスリスト通知メッセージが来ない場合があるので
        # チェックを省略

        # for i in range(self.RETRY_COUNT):
        #     recv_packet = self.echonet_if.recv_udp(self.ipv6_addr)

        #     frame = self.parse_frame(recv_packet)
        #     if ((frame['EDATA']['SEOJ'] == 0x0EF001) and
        #         (frame['EDATA']['DEOJ'] == 0x0EF001)):
        #         break

        # # インスタンスリスト
        # inst_list = ECHONETLite.parse_inst_list(
        #     frame['EDATA']['prop_list'][0]['EDT'])

        # # 低圧スマート電力量メータクラスがあるか確認
        # is_meter_exit = ECHONETLite.check_class(
        #     inst_list, 0x02, 0x88)

        # if not is_meter_exit:
        #     raise Exception('Meter not fount')

    def disconnect(self):
        self.echonet_if.disconnect()

    def get_current_energy(self):
        meter_eoj = ECHONETLite.build_eoj(
            ECHONETLite.EOJ.CLASS_GROUP_HOUSING, ECHONETLite.EOJ.HOUSE_CLASS_GROUP.LOW_VOLTAGE_SMART_METER
        )

        edata = ECHONETLite.build_edata(
            ECHONETLite.build_eoj(
                ECHONETLite.EOJ.CLASS_GROUP_MANAGEMENT, ECHONETLite.EOJ.MANAGEMENT_CLASS_GROUP.CONTROLLER
            ),
            meter_eoj,
            ECHONETLite.ESV.PROP_READ,
            [
                {
                    "EPC": ECHONETLite.EPC.LOW_VOLTAGE_SMART_METER.INSTANTANEOUS_ENERGY,
                    "PDC": 0,
                }
            ],
        )
        send_packet = ECHONETLite.build_frame(edata)

        while True:
            self.echonet_if.send_udp(self.ipv6_addr, ECHONETLite.UDP_PORT, send_packet)
            recv_packet = self.echonet_if.recv_udp(self.ipv6_addr)
            frame = self.parse_frame(recv_packet)

            if frame["EDATA"]["SEOJ"] != meter_eoj:
                continue
            for prop in frame["EDATA"]["prop_list"]:
                if prop["EPC"] != ECHONETLite.EPC.LOW_VOLTAGE_SMART_METER.INSTANTANEOUS_ENERGY:
                    continue
                if len(prop["EDT"]) != prop["PDC"]:
                    continue
                return struct.unpack(">I", prop["EDT"])[0]


# PAN ID の探索 (キャッシュ付き)
def get_pan_info(energy_meter):
    if PAN_DESC_DAT_PATH.exists():
        with PAN_DESC_DAT_PATH.open(mode="rb") as f:
            try:
                return pickle.load(f)  # noqa: S301
            except Exception:  # noqa: S110
                pass

    pan_info = energy_meter.get_pan_info()

    with PAN_DESC_DAT_PATH.open(mode="wb") as f:
        pickle.dump(pan_info, f)

    return pan_info


if __name__ == "__main__":
    # TEST Code
    import importlib

    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    if_dev = args["-i"]
    dev_file = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    class_name = if_dev
    module_name = f"my_lib.sensor.{if_dev.lower()}"

    module = importlib.import_module(module_name)
    if_class = getattr(module, class_name)

    echonet_if = if_class(dev_file, debug_mode)
    energy_meter = EchonetEnergy(echonet_if, config["id"], config["pass"])

    pan_info = get_pan_info(energy_meter)
    print(pan_info)

    energy_meter.connect(pan_info)

    while True:
        logging.info(energy_meter.get_current_energy())
