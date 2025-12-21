#!/usr/bin/env python

from __future__ import annotations

import struct
from typing import Any


class ECHONETLite:
    UDP_PORT: int = 3610

    EHD1: int = 0x10

    class EHD2:  # noqa: D106
        FORMAT1: int = 0x81
        FORMAT2: int = 0x82

    class ESV:  # noqa: D106
        # プロパティ値書き込み要求(応答不要)
        PROP_WRITE_NO_RES: int = 0x60
        # プロパティ値書き込み要求(応答要)
        PROP_WRITE: int = 0x61
        # プロパティ値読み出し要求
        PROP_READ: int = 0x62
        # プロパティ値通知要求
        PROP_NOTIFY: int = 0x62
        # プロパティ値書き込み・読み出し要求
        PROP_WRITE_READ: int = 0x6E

    class EOJ:  # noqa: D106
        # 住宅・設備関連機器クラスグループ
        CLASS_GROUP_HOUSING: int = 0x02
        # 管理・操作関連機器クラスグループ
        CLASS_GROUP_MANAGEMENT: int = 0x05

        class HOUSE_CLASS_GROUP:  # noqa: N801, D106
            # 低圧スマート電力量メータクラス
            LOW_VOLTAGE_SMART_METER: int = 0x88

        class MANAGEMENT_CLASS_GROUP:  # noqa: N801, D106
            # コントローラ
            CONTROLLER: int = 0xFF

    class EPC:  # noqa: D106
        class LOW_VOLTAGE_SMART_METER:  # noqa: N801, D106
            # 動作状態
            STATUS: int = 0x80
            # 積算電力量有効桁数
            EFFECTIVE_DIGITS_OF_CUMULATIVE_ENERGY: int = 0xD7
            # 積算電力量計測値(正方向計測値)
            CUMULATIVE_ENERGY_NORMAL_DIRECTION: int = 0xE0
            # 積算電力量計測値(逆方向計測値)
            CUMULATIVE_ENERGY_REVERSE_DIRECTION: int = 0xE3
            # 積算電力量単位(正方向、逆方向計測値)
            CUMULATIVE_ENERGY_UNIT: int = 0xE1
            # 瞬時電力計測値
            INSTANTANEOUS_ENERGY: int = 0xE7
            # 瞬時電流計測値
            INSTANTANEOUS_CURRENT: int = 0xE8
            # 定時積算電力量計測値(正方向計測値)
            CUMULATIVE_ENERGY_FIXED_TIME_NORMAL_DIRECTION: int = 0xEA
            # 定時積算電力量計測値(逆方向計測値)
            CUMULATIVE_ENERGY_FIXED_TIME_REVERSE_DIRECTION: int = 0xEB

    @classmethod
    def parse_frame(cls, packet: bytes | None) -> dict[str, Any]:
        frame: dict[str, Any] = {}

        if (packet is None) or (len(packet) < 10):
            hex_data = " ".join(f"0x{b:02x}" for b in packet) if packet else "None"
            raise Exception(f"Invalid Packet: too short (data = {hex_data})")

        # ヘッダ
        frame["EHD1"] = struct.unpack("B", packet[0:1])[0]
        frame["EHD2"] = struct.unpack("B", packet[1:2])[0]
        frame["TID"] = struct.unpack(">H", packet[2:4])[0]
        if frame["EHD2"] == cls.EHD2.FORMAT1:
            frame["EDATA"] = cls.parse_data(packet[4:])

        cls.validate_header(frame)

        return frame

    @classmethod
    def validate_header(cls, frame: dict[str, Any]) -> None:
        if frame["EHD1"] != cls.EHD1:
            raise Exception("Invalid EHD1: {frame['EHD1']}")
        if (frame["EHD2"] != cls.EHD2.FORMAT1) and (frame["EHD2"] != cls.EHD2.FORMAT2):
            raise Exception("Invalid EHD2: {frame['HD2']}")

    @classmethod
    def parse_data(cls, packet: bytes) -> dict[str, Any]:
        data: dict[str, Any] = {}
        data["SEOJ"] = struct.unpack(">I", b"\00" + packet[0:3])[0]
        data["DEOJ"] = struct.unpack(">I", b"\00" + packet[3:6])[0]
        data["ESV"] = struct.unpack("B", packet[6:7])[0]
        data["OPC"] = struct.unpack("B", packet[7:8])[0]

        prop_list: list[dict[str, Any]] = []
        packet = packet[8:]
        for _ in range(data["OPC"]):
            prop: dict[str, Any] = {}
            prop["EPC"] = struct.unpack("B", packet[0:1])[0]
            prop["PDC"] = struct.unpack("B", packet[1:2])[0]
            if prop["PDC"] == 0:
                prop["EDT"] = None
            else:
                prop["EDT"] = packet[2 : (2 + prop["PDC"])]
            prop_list.append(prop)
        data["prop_list"] = prop_list

        return data

    @classmethod
    def parse_inst_list(cls, packet: bytes) -> list[dict[str, int]]:
        count = struct.unpack("B", packet[0:1])[0]
        packet = packet[1:]

        inst_list: list[dict[str, int]] = []
        for _ in range(count):
            inst_info: dict[str, int] = {}
            inst_info["class_group_code"] = struct.unpack("B", packet[0:1])[0]
            inst_info["class_code"] = struct.unpack("B", packet[1:2])[0]
            inst_info["instance_code"] = struct.unpack("B", packet[2:3])[0]
            inst_list.append(inst_info)
            packet = packet[3:]

        return inst_list

    @classmethod
    def check_class(cls, inst_list: list[dict[str, int]], class_group_code: int, class_code: int) -> bool:
        for inst_info in inst_list:
            if (inst_info["class_group_code"] == class_group_code) and (
                inst_info["class_code"] == class_code
            ):
                return True

        return False

    @classmethod
    def build_frame(cls, edata: bytes, tid: int = 1) -> bytes:
        return struct.pack("2B", cls.EHD1, cls.EHD2.FORMAT1) + struct.pack(">H", tid) + edata

    @classmethod
    def build_edata(cls, seoj: int, deoj: int, esv: int, prop_list: list[dict[str, Any]]) -> bytes:
        seoj_data = struct.pack(">I", seoj)[1:]
        deoj_data = struct.pack(">I", deoj)[1:]

        esv_data = struct.pack("B", esv)
        opc_data = struct.pack("B", len(prop_list))

        edata = seoj_data + deoj_data + esv_data + opc_data
        for prop in prop_list:
            prop_data = cls.build_prop(prop["EPC"], prop["PDC"], prop.get("EDT"))
            edata += prop_data

        return edata

    @classmethod
    def build_eoj(cls, class_group_code: int, class_code: int, instance_code: int = 0x1) -> int:
        return (class_group_code << 16) | (class_code << 8) | instance_code

    @classmethod
    def build_prop(cls, epc: int, pdc: int, edt: bytes | None) -> bytes:
        prop = struct.pack("2B", epc, pdc)
        if pdc != 0 and edt is not None:
            prop += edt

        return prop
