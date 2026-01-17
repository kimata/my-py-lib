#!/usr/bin/env python3
"""ECHONET Lite プロトコル実装

ECHONET Lite 規格（APPENDIX ECHONET 機器オブジェクト詳細規定）に基づいた実装。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class EchonetLiteProperty:
    """ECHONET Lite プロパティ

    規格: ECHONET Lite 規格書 第2部 3.2.5
    - EPC: ECHONET プロパティコード (1 byte)
    - PDC: プロパティ値データ長 (1 byte)
    - EDT: プロパティ値データ (PDC bytes)
    """

    epc: int  # ECHONET Property Code
    pdc: int  # Property Data Counter
    edt: bytes | None = None  # ECHONET property Data


@dataclass(frozen=True)
class EchonetLiteData:
    """ECHONET Lite データ部 (EDATA)

    規格: ECHONET Lite 規格書 第2部 3.2.1
    - SEOJ: 送信元 ECHONET オブジェクト (3 bytes)
    - DEOJ: 相手先 ECHONET オブジェクト (3 bytes)
    - ESV: ECHONET Lite サービス (1 byte)
    - OPC: 処理プロパティ数 (1 byte)
    """

    seoj: int  # Source ECHONET Object
    deoj: int  # Destination ECHONET Object
    esv: int  # ECHONET Lite Service
    opc: int  # OPeration Count
    props: tuple[EchonetLiteProperty, ...]


@dataclass(frozen=True)
class EchonetLiteFrame:
    """ECHONET Lite フレーム

    規格: ECHONET Lite 規格書 第2部 3.2
    - EHD1: ECHONET Lite 電文ヘッダ1 (1 byte, 0x10 固定)
    - EHD2: ECHONET Lite 電文ヘッダ2 (1 byte, 0x81: Format1, 0x82: Format2)
    - TID: トランザクション ID (2 bytes)
    - EDATA: ECHONET Lite データ部
    """

    ehd1: int  # ECHONET Lite Header 1
    ehd2: int  # ECHONET Lite Header 2
    tid: int  # Transaction ID
    edata: EchonetLiteData | None = None


@dataclass(frozen=True)
class EchonetLiteInstance:
    """ECHONET オブジェクトインスタンス情報

    規格: ECHONET Lite 規格書 第2部 3.3.1
    """

    class_group_code: int  # クラスグループコード
    class_code: int  # クラスコード
    instance_code: int  # インスタンスコード


class ECHONETLite:
    """ECHONET Lite プロトコル実装クラス"""

    UDP_PORT: int = 3610

    EHD1: int = 0x10

    class EHD2:
        FORMAT1: int = 0x81
        FORMAT2: int = 0x82

    class ESV:
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

    class EOJ:
        # 住宅・設備関連機器クラスグループ
        CLASS_GROUP_HOUSING: int = 0x02
        # 管理・操作関連機器クラスグループ
        CLASS_GROUP_MANAGEMENT: int = 0x05

        class HOUSE_CLASS_GROUP:
            # 低圧スマート電力量メータクラス
            LOW_VOLTAGE_SMART_METER: int = 0x88

        class MANAGEMENT_CLASS_GROUP:
            # コントローラ
            CONTROLLER: int = 0xFF

    class EPC:
        class LOW_VOLTAGE_SMART_METER:
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
    def parse_frame(cls, packet: bytes) -> EchonetLiteFrame:
        """パケットからフレームをパースする"""
        if len(packet) < 10:
            hex_data = " ".join(f"0x{b:02x}" for b in packet)
            raise ValueError(f"Invalid Packet: too short (data = {hex_data})")

        # ヘッダ
        ehd1 = struct.unpack("B", packet[0:1])[0]
        ehd2 = struct.unpack("B", packet[1:2])[0]
        tid = struct.unpack(">H", packet[2:4])[0]

        edata: EchonetLiteData | None = None
        if ehd2 == cls.EHD2.FORMAT1:
            edata = cls.parse_data(packet[4:])

        frame = EchonetLiteFrame(ehd1=ehd1, ehd2=ehd2, tid=tid, edata=edata)
        cls.validate_header(frame)

        return frame

    @classmethod
    def validate_header(cls, frame: EchonetLiteFrame) -> None:
        """フレームヘッダを検証する"""
        if frame.ehd1 != cls.EHD1:
            raise ValueError(f"Invalid EHD1: {frame.ehd1}")
        if (frame.ehd2 != cls.EHD2.FORMAT1) and (frame.ehd2 != cls.EHD2.FORMAT2):
            raise ValueError(f"Invalid EHD2: {frame.ehd2}")

    @classmethod
    def parse_data(cls, packet: bytes) -> EchonetLiteData:
        """パケットからデータ部をパースする"""
        seoj = struct.unpack(">I", b"\00" + packet[0:3])[0]
        deoj = struct.unpack(">I", b"\00" + packet[3:6])[0]
        esv = struct.unpack("B", packet[6:7])[0]
        opc = struct.unpack("B", packet[7:8])[0]

        prop_list: list[EchonetLiteProperty] = []
        packet = packet[8:]
        for _ in range(opc):
            epc = struct.unpack("B", packet[0:1])[0]
            pdc = struct.unpack("B", packet[1:2])[0]
            edt: bytes | None = None
            if pdc != 0:
                edt = packet[2 : (2 + pdc)]
            prop_list.append(EchonetLiteProperty(epc=epc, pdc=pdc, edt=edt))
            packet = packet[2 + pdc :]

        return EchonetLiteData(seoj=seoj, deoj=deoj, esv=esv, opc=opc, props=tuple(prop_list))

    @classmethod
    def parse_inst_list(cls, packet: bytes) -> list[EchonetLiteInstance]:
        """インスタンスリストをパースする"""
        count = struct.unpack("B", packet[0:1])[0]
        packet = packet[1:]

        inst_list: list[EchonetLiteInstance] = []
        for _ in range(count):
            class_group_code = struct.unpack("B", packet[0:1])[0]
            class_code = struct.unpack("B", packet[1:2])[0]
            instance_code = struct.unpack("B", packet[2:3])[0]
            inst_list.append(
                EchonetLiteInstance(
                    class_group_code=class_group_code,
                    class_code=class_code,
                    instance_code=instance_code,
                )
            )
            packet = packet[3:]

        return inst_list

    @classmethod
    def check_class(
        cls, inst_list: list[EchonetLiteInstance], class_group_code: int, class_code: int
    ) -> bool:
        """インスタンスリストに指定したクラスが含まれるか確認する"""
        for inst_info in inst_list:
            if (inst_info.class_group_code == class_group_code) and (inst_info.class_code == class_code):
                return True

        return False

    @classmethod
    def build_frame(cls, edata: bytes, tid: int = 1) -> bytes:
        """フレームを構築する"""
        return struct.pack("2B", cls.EHD1, cls.EHD2.FORMAT1) + struct.pack(">H", tid) + edata

    @classmethod
    def build_edata(cls, seoj: int, deoj: int, esv: int, prop_list: list[EchonetLiteProperty]) -> bytes:
        """データ部を構築する"""
        seoj_data = struct.pack(">I", seoj)[1:]
        deoj_data = struct.pack(">I", deoj)[1:]

        esv_data = struct.pack("B", esv)
        opc_data = struct.pack("B", len(prop_list))

        edata = seoj_data + deoj_data + esv_data + opc_data
        for prop in prop_list:
            prop_data = cls.build_prop(prop.epc, prop.pdc, prop.edt)
            edata += prop_data

        return edata

    @classmethod
    def build_eoj(cls, class_group_code: int, class_code: int, instance_code: int = 0x1) -> int:
        """EOJ を構築する"""
        return (class_group_code << 16) | (class_code << 8) | instance_code

    @classmethod
    def build_prop(cls, epc: int, pdc: int, edt: bytes | None) -> bytes:
        """プロパティを構築する"""
        prop = struct.pack("2B", epc, pdc)
        if pdc != 0 and edt is not None:
            prop += edt

        return prop
