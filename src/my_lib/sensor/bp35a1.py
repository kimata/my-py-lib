#!/usr/bin/env python

import logging
import pprint

import serial

RETRY_COUNT = 10
WAIT_COUNT = 30


class BP35A1:
    NAME = "BP35A1"

    def __init__(self, port="/dev/ttyAMA0", debug=False):  # noqa: D107
        self.ser = serial.Serial(port=port, baudrate=115200, timeout=5)
        self.opt = None
        self.ser.flushInput()

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.logger.setLevel(logging.DEBUG if debug else logging.WARNING)

    def ping(self):
        try:
            self.reset()

            ret = self.__send_command_raw("SKINFO")
            self.__expect("OK")
            ret = ret.split(" ", 1)

            return ret[0] == "EINFO"
        except Exception:
            return False

    def write(self, data):
        self.logger.debug("SEND: [%s]", pprint.pformat(data))

        if type(data) is str:
            data = data.encode()

        self.ser.write(data)

    def read(self):
        data = self.ser.readline().decode()
        self.logger.debug("RECV: [%s]", pprint.pformat(data))
        return data

    def reset(self):
        # Clear buffer
        self.ser.flushInput()
        self.ser.flushOutput()

        self.logger.warning("reset")
        self.__send_command_without_check("SKRESET")
        self.__expect("OK")

    def get_option(self):
        ret = self.__send_command("ROPT")
        val = int(ret, 16)

        self.opt = val

    def set_id(self, b_id):
        command = f"SKSETRBID {b_id}"
        self.__send_command(command)

    def set_password(self, b_pass):
        command = f"SKSETPWD {len(b_pass):X} {b_pass}"
        self.__send_command(command)

    def scan_channel(self, start_duration=3):
        duration = start_duration
        pan_info = None
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

    def connect(self, pan_desc):
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

    def disconnect(self):
        self.__send_command_without_check("SKTERM")
        try:
            self.__expect("OK")
            self.__expect("EVENT 27")
        except Exception:
            return

    def recv_udp(self, ipv6_addr, wait_count=10):
        for _ in range(wait_count):
            line = self.read().rstrip()
            if line == "":
                continue

            line = line.split(" ", 9)
            if line[0] != "ERXUDP":
                continue
            if line[1] == ipv6_addr:
                # NOTE: 16進文字列をバイナリに変換 (デフォルト設定の WOPT 01 の前提)
                return bytes.fromhex(line[8])
        return None

    def send_udp(self, ipv6_addr, port, data, handle=1, security=True):
        command = f"SKSENDTO {handle} {ipv6_addr} {port:04X} {1 if security else 2} {len(data):04X} "
        self.__send_command_without_check(command.encode() + data)
        while self.read().rstrip() != "OK":
            pass

    def __parse_pan_desc(self):
        self.__expect("EPANDESC")
        pan_desc = {}
        for _ in range(WAIT_COUNT):
            line = self.read()

            if not line.startswith("  "):
                raise Exception(f"Line does not start with space.\nrst: {line}")

            line = line.strip().split(":")
            pan_desc[line[0]] = line[1]

            if line[0] == "PairID":
                break

        return pan_desc

    def __send_command_raw(self, command, echo_back=lambda command: command):
        self.write(command)
        self.write("\r\n")
        # NOTE: echo_back はコマンドからエコーバック文字列を生成する関数。
        # デフォルトはコマンドそのもの。
        self.__expect(echo_back(command))

        return self.read().rstrip()

    def __send_command_without_check(self, command):
        self.write(command)
        self.write("\r\n")
        self.read()

    def __send_command(self, command):
        ret = self.__send_command_raw(command)
        ret = ret.split(" ", 1)

        if ret[0] != "OK":
            raise Exception(f"Status is not OK.\nrst: {ret[0]}")

        return None if len(ret) == 1 else ret[1]

    def __expect(self, text):
        line = ""
        for _ in range(WAIT_COUNT):
            line = self.read().rstrip()

            if line != "":
                break

        if line != text:
            raise Exception(f"Echo back is wrong.\nexp: [{text}]\nrst: [{line.rstrip()}]")
