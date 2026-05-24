#!/usr/bin/env python3
"""BP35A1 (ECHONET Lite Wi-SUN モジュール) ドライバ。

イベント駆動のセッション層 (bp35a1_session.BP35A1Session) を経由してコマンドを送り、
必要なイベントを待つ構造。BP35A1 クラスの public API は echonetenergy.py や
他の上位コードが期待するシグネチャを維持する。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import serial

from my_lib.sensor.bp35a1_session import BP35A1Session, EventKind


@dataclass(frozen=True)
class PanDescriptor:
    """PAN スキャン結果。

    `pair_id` は MODE 2 では返ってくるが MODE 3 (active scan with IE) では
    省略されるケースがあるためデフォルト値を持つ。
    """

    channel: str
    pan_id: str
    addr: str
    pair_id: str = ""


# scan_channel が duration を上げながらリトライする際の上限。
# duration 9 で各チャネル ~5s, 全 33 チャネルで ~165 秒。
# これ以上は 1 サイクルが長くなりすぎて Liveness probe を超える可能性がある。
SCAN_DURATION_MAX: int = 9

# PANA 認証 (SKJOIN) を待つ最大秒数。
JOIN_TIMEOUT: float = 30.0


def _scan_timeout_sec(duration: int) -> float:
    """SKSCAN 1 回分のタイムアウト目安。

    Wi-SUN active scan 仕様で各チャネル滞在時間は約 (2^duration + 1) × 9.6ms。
    全 33 チャネル + ハンドリング余裕 + 終端 EVENT 22 まで含む。
    """
    per_channel_ms = (2**duration + 1) * 9.6
    total_sec = (33 * per_channel_ms / 1000.0) + 10.0
    return max(total_sec, 30.0)


class BP35A1:
    NAME: str = "BP35A1"

    def __init__(self, port: str = "/dev/ttyAMA0", debug: bool = False) -> None:
        self.ser: serial.Serial = serial.Serial(port=port, baudrate=115200, timeout=5)
        self.ser.reset_input_buffer()
        self.session: BP35A1Session = BP35A1Session(self.ser)
        self.opt: int | None = None

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.logger.setLevel(logging.DEBUG if debug else logging.WARNING)

    # ------------------------------------------------------------------
    # 高レベル API (上位コードが使う)
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """モジュールが応答するか確認する。"""
        try:
            self.reset()
            # SKINFO は EINFO 行を返した後 OK を出す。EINFO が来れば応答ありと判定
            evt = self.session.send_and_expect("SKINFO", expect={EventKind.EINFO, EventKind.FAIL}, timeout=5)
            return evt is not None and evt.kind == EventKind.EINFO
        except Exception:
            self.logger.warning("ping failed", exc_info=True)
            return False

    def reset(self) -> None:
        """モジュールをソフトリセットする。"""
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.session.send_and_expect("SKRESET", timeout=3)

    def get_option(self) -> None:
        """ROPT を実行して self.opt に格納する。"""
        evt = self.session.send_and_expect("ROPT", timeout=3)
        if evt is None or evt.kind != EventKind.OK or not evt.args:
            raise RuntimeError("Failed to get option")
        self.opt = int(evt.args[0], 16)

    def set_id(self, b_id: str) -> None:
        """B ルート ID を設定する。"""
        self._send_ok(f"SKSETRBID {b_id}")

    def set_password(self, b_pass: str) -> None:
        """B ルートパスワードを設定する。"""
        self._send_ok(f"SKSETPWD {len(b_pass):X} {b_pass}")

    def scan_channel(self, start_duration: int = 3) -> PanDescriptor | None:
        """アクティブスキャンで PAN を探索する。

        duration を `start_duration` から `SCAN_DURATION_MAX` まで上げながら
        試行し、最初に見つかった PanDescriptor を返す。見つからなければ None。

        SKSCAN MODE 3 (active scan with IE) を使う。MODE 2 より検出率が高く、
        メーターのビーコン送信特性が変動しても拾いやすい。
        """
        for duration in range(start_duration, SCAN_DURATION_MAX + 1):
            command = f"SKSCAN 3 {((1 << 32) - 1):X} {duration}"
            timeout = _scan_timeout_sec(duration)
            self.logger.debug("scan duration=%d (timeout=%.1fs)", duration, timeout)

            events = self.session.send_and_collect(command, until={EventKind.EVENT_22}, timeout=timeout)
            for evt in events:
                if evt.kind == EventKind.EPANDESC:
                    f = evt.fields
                    return PanDescriptor(
                        channel=f.get("Channel", ""),
                        pan_id=f.get("Pan ID", ""),
                        addr=f.get("Addr", ""),
                        pair_id=f.get("PairID", ""),
                    )
        return None

    def connect(self, pan_desc: PanDescriptor) -> str | None:
        """PAN に PANA 認証で接続する。成功時は IPv6 リンクローカルアドレスを返す。"""
        self._send_ok(f"SKSREG S2 {pan_desc.channel}")
        self._send_ok(f"SKSREG S3 {pan_desc.pan_id}")

        # SKLL64 はエコーの後に IPv6 アドレスが 1 行だけ返る (OK なし)
        ipv6_addr = self._send_ll64(pan_desc.addr)
        if ipv6_addr is None:
            self.logger.warning("SKLL64 failed")
            return None

        # SKJOIN は OK の後に EVENT 24 (失敗) か EVENT 25 (成功) が来る
        events = self.session.send_and_collect(
            f"SKJOIN {ipv6_addr}",
            until={EventKind.EVENT_24, EventKind.EVENT_25},
            timeout=JOIN_TIMEOUT,
        )
        for evt in events:
            if evt.kind == EventKind.EVENT_24:
                self.logger.warning("receive EVENT 24 (connect ERROR)")
                return None
            if evt.kind == EventKind.EVENT_25:
                return ipv6_addr
        # タイムアウト
        return None

    def disconnect(self) -> None:
        """PANA セッションを終了する (失敗しても無視)。"""
        try:
            self.session.send_and_collect("SKTERM", until={EventKind.EVENT_27, EventKind.FAIL}, timeout=10)
        except Exception:
            self.logger.debug("disconnect: ignored exception", exc_info=True)

    def send_udp(
        self,
        ipv6_addr: str,
        port: int,
        data: bytes,
        handle: int = 1,
        security: bool = True,
    ) -> None:
        """UDP データを送信する。"""
        header = (
            f"SKSENDTO {handle} {ipv6_addr} {port:04X} {1 if security else 2} {len(data):04X} "
        ).encode()
        # NOTE: ヘッダー + バイナリ + CRLF を 1 度に送信
        self.session.write_raw(header + data + b"\r\n")
        # OK が来るまで待つ (途中で EVENT 21 = 送信完了 が割り込む)
        self.session.collect_until({EventKind.OK, EventKind.FAIL}, timeout=10)

    def recv_udp(self, ipv6_addr: str, timeout: float = 5.0) -> bytes | None:
        """指定送信元からの UDP データを 1 つ受信する。タイムアウトで None。"""
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.ser.timeout = max(0.1, deadline - time.monotonic())
            evt = self.session.parser.next_event()
            if evt is None:
                continue
            if evt.kind != EventKind.ERXUDP:
                continue
            sender = evt.args[0] if evt.args else ""
            if sender == ipv6_addr:
                return evt.payload
        return None

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    def _send_ok(self, command: str, timeout: float = 5) -> None:
        """OK の応答を期待するコマンドを送る。OK 以外が来たら raise。"""
        evt = self.session.send_and_expect(command, timeout=timeout)
        if evt is None or evt.kind != EventKind.OK:
            received = evt.kind if evt else "TIMEOUT"
            raise RuntimeError(f"Command {command!r} did not return OK (got {received})")

    def _send_ll64(self, mac_addr: str) -> str | None:
        """SKLL64 を送って IPv6 アドレス 1 行を取得する。

        SKLL64 はエコーの直後に IPv6 アドレスが 1 行だけ返る (OK なし) という
        特殊な応答仕様。1 行ずつ raw で読んで「IPv6 らしき行」を拾う。
        """
        self.session.send_line(f"SKLL64 {mac_addr}")
        # コマンドエコーや空行を読み飛ばし、IPv6 形式の行を待つ
        for _ in range(10):
            line = self.session.read_line_raw(timeout=3)
            if line is None:
                return None
            if line == "" or line.startswith("SKLL64"):
                continue  # エコーや空行
            # FE80:... のような形式を期待
            if ":" in line and len(line) >= 16:
                return line
        return None
