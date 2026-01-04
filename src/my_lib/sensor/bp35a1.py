#!/usr/bin/env python

from __future__ import annotations

import logging
import pprint
from typing import Any

import serial

RETRY_COUNT: int = 10
WAIT_COUNT: int = 30


class BP35A1:
    NAME: str = "BP35A1"

    def __init__(self, port: str = "/dev/ttyAMA0", debug: bool = False) -> None:
        self.ser: serial.Serial = serial.Serial(port=port, baudrate=115200, timeout=5)
        self.opt: int | None = None
        self.ser.reset_input_buffer()

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.logger.setLevel(logging.DEBUG if debug else logging.WARNING)

    def ping(self) -> bool:
        try:
            self.reset()

            ret = self.__send_command_raw("SKINFO")
            self.__expect("OK")
            parts = ret.split(" ", 1)

            return parts[0] == "EINFO"
        except Exception:
            return False

    def write(self, data: str | bytes) -> None:
        self.logger.debug("SEND: [%s]", pprint.pformat(data))

        if isinstance(data, str):
            data = data.encode()

        self.ser.write(data)

    def read(self) -> str:
        data = self.ser.readline().decode()
        self.logger.debug("RECV: [%s]", pprint.pformat(data))
        return data

    def reset(self) -> None:
        # Clear buffer
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        self.logger.debug("reset")
        self.__send_command_without_check("SKRESET")
        self.__expect("OK")

    def get_option(self) -> None:
        ret = self.__send_command("ROPT")
        if ret is None:
            raise RuntimeError("Failed to get option")
        val = int(ret, 16)

        self.opt = val

    def set_id(self, b_id: str) -> None:
        command = f"SKSETRBID {b_id}"
        self.__send_command(command)

    def set_password(self, b_pass: str) -> None:
        command = f"SKSETPWD {len(b_pass):X} {b_pass}"
        self.__send_command(command)

    def scan_channel(self, start_duration: int = 3) -> dict[str, str] | None:
        duration = start_duration
        pan_info: dict[str, str] | None = None
        for _ in range(RETRY_COUNT):
            command = f"SKSCAN 2 {((1 << 32) - 1):X} {duration}"
            self.__send_command(command)

            for _ in range(WAIT_COUNT):
                line = self.read()
                # スキャン完了
                if line.startswith("EVENT 22"):
                    break
                # メータ発見
                if line.startswith("EVENT 20"):
                    pan_info = self.__parse_pan_desc()

            if pan_info is not None:
                return pan_info

            duration += 1
            if duration > 7:
                return None

        return None

    def connect(self, pan_desc: dict[str, str]) -> str | None:
        command = f"SKSREG S2 {pan_desc['Channel']}"
        self.__send_command(command)

        command = f"SKSREG S3 {pan_desc['Pan ID']}"
        self.__send_command(command)

        command = f"SKLL64 {pan_desc['Addr']}"
        ipv6_addr = self.__send_command_raw(command)

        command = f"SKJOIN {ipv6_addr}"

        self.__send_command(command)

        for _ in range(WAIT_COUNT):
            line = self.read()
            # 接続失敗
            if line.startswith("EVENT 24"):
                self.logger.warning("receive EVENT 24 (connect ERROR)")
                return None
            # 接続成功
            if line.startswith("EVENT 25"):
                return ipv6_addr
        # タイムアウト
        return None

    def disconnect(self) -> None:
        self.__send_command_without_check("SKTERM")
        try:
            self.__expect("OK")
            self.__expect("EVENT 27")
        except Exception:
            return

    def recv_udp(self, ipv6_addr: str, wait_count: int = 10) -> bytes | None:
        for _ in range(wait_count):
            line = self.read().rstrip()
            if line == "":
                continue

            parts = line.split(" ", 9)
            if parts[0] != "ERXUDP":
                continue
            if parts[1] == ipv6_addr:
                # NOTE: 16進文字列をバイナリに変換 (デフォルト設定の WOPT 01 の前提)
                return bytes.fromhex(parts[8])
        return None

    def send_udp(
        self, ipv6_addr: str, port: int, data: bytes, handle: int = 1, security: bool = True
    ) -> None:
        command = f"SKSENDTO {handle} {ipv6_addr} {port:04X} {1 if security else 2} {len(data):04X} "
        self.__send_command_without_check(command.encode() + data)
        while self.read().rstrip() != "OK":
            pass

    def __parse_pan_desc(self) -> dict[str, str]:
        self.__expect("EPANDESC")
        pan_desc: dict[str, str] = {}
        for _ in range(WAIT_COUNT):
            line = self.read()

            if not line.startswith("  "):
                raise Exception(f"Line does not start with space.\nrst: {line}")

            parts = line.strip().split(":")
            pan_desc[parts[0]] = parts[1]

            if parts[0] == "PairID":
                break

        return pan_desc

    def __send_command_raw(self, command: str, echo_back: Any = lambda command: command) -> str:
        self.write(command)
        self.write("\r\n")
        # NOTE: echo_back はコマンドからエコーバック文字列を生成する関数。
        # デフォルトはコマンドそのもの。
        self.__expect(echo_back(command))

        return self.read().rstrip()

    def __send_command_without_check(self, command: str | bytes) -> None:
        self.write(command)
        self.write("\r\n")
        self.read()

    def __send_command(self, command: str) -> str | None:
        ret = self.__send_command_raw(command)
        parts = ret.split(" ", 1)

        if parts[0] != "OK":
            raise RuntimeError(f"Status is not OK.\nrst: {parts[0]}")

        return None if len(parts) == 1 else parts[1]

    def __expect(self, text: str) -> None:
        line = ""
        for _ in range(WAIT_COUNT):
            line = self.read().rstrip()

            if line != "":
                break

        if line != text:
            raise Exception(f"Echo back is wrong.\nexp: [{text}]\nrst: [{line.rstrip()}]")
