"""
BP35A1 のシリアル通信を「イベント駆動」で扱うレイヤ。

レイヤ構造:
  Layer 0: pyserial の serial.Serial (外部)
  Layer 1: EventParser    — シリアル行ストリームを Event オブジェクト列に変換
  Layer 2: BP35A1Session  — コマンド送信 + イベント待機 + 行プッシュバック

Event は kind ("OK", "EVENT_22", "EPANDESC" など) でタグ付けされた構造化データ。
複数行ブロック (EPANDESC) も 1 つの Event にまとまる。
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

import serial


class EventKind:
    """BP35A1 から受信する行の分類。"""

    OK = "OK"
    FAIL = "FAIL"

    # メタイベント (EVENT NN <args>)
    EVENT_1F = "EVENT_1F"  # ED scan 完了
    EVENT_20 = "EVENT_20"  # PAN ビーコン発見
    EVENT_21 = "EVENT_21"  # UDP 送信完了
    EVENT_22 = "EVENT_22"  # アクティブスキャン完了
    EVENT_24 = "EVENT_24"  # PANA 認証失敗
    EVENT_25 = "EVENT_25"  # PANA 認証成功
    EVENT_26 = "EVENT_26"  # PANA セッション終了要求受信
    EVENT_27 = "EVENT_27"  # PANA セッション終了
    EVENT_29 = "EVENT_29"  # PANA セッション寿命満了
    EVENT_32 = "EVENT_32"  # ARIB 法令違反
    EVENT_33 = "EVENT_33"  # ARIB 法令違反解除
    EVENT_OTHER = "EVENT_OTHER"

    # データブロック / 単発応答
    EPANDESC = "EPANDESC"  # PAN 詳細 (複数行)
    ERXUDP = "ERXUDP"  # UDP 受信
    EEDSCAN = "EEDSCAN"  # ED scan 結果
    EINFO = "EINFO"  # SKINFO 応答
    EVER = "EVER"  # SKVER 応答
    EPONG = "EPONG"  # SKPING 応答
    EADDR = "EADDR"  # SKADDRADDR 応答

    UNKNOWN = "UNKNOWN"  # コマンドエコー等を含む未分類行


# EVENT NN を kind に変換するマップ
_EVENT_KIND_MAP: dict[str, str] = {
    "1F": EventKind.EVENT_1F,
    "20": EventKind.EVENT_20,
    "21": EventKind.EVENT_21,
    "22": EventKind.EVENT_22,
    "24": EventKind.EVENT_24,
    "25": EventKind.EVENT_25,
    "26": EventKind.EVENT_26,
    "27": EventKind.EVENT_27,
    "29": EventKind.EVENT_29,
    "32": EventKind.EVENT_32,
    "33": EventKind.EVENT_33,
}


@dataclass
class Event:
    """BP35A1 から受信した 1 単位のイベント。"""

    kind: str
    raw: str  # 行 (block の場合は先頭の "EPANDESC" 等)
    args: list[str] = field(default_factory=list)  # 行をスペース分割した結果 (kind 自体は除く)
    fields: dict[str, str] = field(default_factory=dict)  # block 系イベントのフィールド (EPANDESC 等)
    payload: bytes = b""  # ERXUDP のバイナリペイロード (WOPT 01 で 16 進文字列をデコード)


class EventParser:
    """シリアル行ストリームを Event 列に変換する。

    EPANDESC のような複数行ブロックも 1 Event として組み立てる。
    block 終端を超えて読んだ行は内部バッファに pushback され、次回の next_event で返る。
    """

    # EPANDESC ブロックを読む際の最大行数 (無限ループ防止)
    _BLOCK_MAX_LINES = 50

    def __init__(self, ser: serial.Serial) -> None:
        self.ser = ser
        self.logger = logging.getLogger(__name__)
        self._lookahead: deque[str] = deque()

    def _read_line(self) -> str | None:
        """1 行 read。pushback があれば優先的に返す。タイムアウトで None。"""
        if self._lookahead:
            return self._lookahead.popleft()
        data = self.ser.readline()
        if not data:
            return None
        return data.decode("utf-8", errors="replace")

    def _pushback(self, line: str) -> None:
        """1 行を内部バッファに戻す。次回 _read_line で返る。"""
        self._lookahead.appendleft(line)

    def next_event(self) -> Event | None:
        """次の Event を返す。タイムアウト (1 行も読めない) で None。"""
        while True:
            line = self._read_line()
            if line is None:
                return None  # シリアルタイムアウト
            stripped = line.rstrip("\r\n")
            if stripped == "":
                continue  # 空行はスキップして次を待つ
            return self._classify(stripped)

    def _classify(self, line: str) -> Event:
        """1 行を分類して Event を構築する。"""
        # OK / OK <args>
        if line == "OK" or line.startswith("OK "):
            return Event(kind=EventKind.OK, raw=line, args=line.split()[1:])

        # FAIL / FAIL <args>
        if line == "FAIL" or line.startswith("FAIL "):
            return Event(kind=EventKind.FAIL, raw=line, args=line.split()[1:])

        # EVENT NN <args>
        if line.startswith("EVENT "):
            parts = line.split()
            num = parts[1].upper() if len(parts) >= 2 else ""
            kind = _EVENT_KIND_MAP.get(num, EventKind.EVENT_OTHER)
            return Event(kind=kind, raw=line, args=parts[2:])

        # EPANDESC: 複数行ブロックを取り込む
        if line == "EPANDESC":
            return self._parse_pan_desc_block()

        # ERXUDP: 1 行で完結 (WOPT 01 前提)
        if line.startswith("ERXUDP "):
            return self._parse_erxudp(line)

        # 単発の E* 応答 (引数つき)
        for prefix, kind in (
            ("EEDSCAN", EventKind.EEDSCAN),
            ("EINFO ", EventKind.EINFO),
            ("EVER ", EventKind.EVER),
            ("EPONG ", EventKind.EPONG),
            ("EADDR ", EventKind.EADDR),
        ):
            if line.startswith(prefix):
                return Event(kind=kind, raw=line, args=line.split()[1:])

        # それ以外 (コマンドエコー、SKLL64 の IPv6 応答など) は UNKNOWN
        return Event(kind=EventKind.UNKNOWN, raw=line)

    def _parse_pan_desc_block(self) -> Event:
        """EPANDESC ブロック (複数行) を読み取って fields に格納する。

        "  Key:Value" 形式の行を取り込み、スペース始まりでない行が来たら終端。
        終端を超えて読んだ行は pushback して次回 next_event で再現する。
        """
        fields: dict[str, str] = {}
        for _ in range(self._BLOCK_MAX_LINES):
            line = self._read_line()
            if line is None:
                break  # timeout (block 途中で打ち切り)
            stripped = line.rstrip("\r\n")
            if not stripped.startswith("  "):
                # ブロック終端 — 読みすぎた行は次の next_event で再生
                if stripped != "":
                    self._pushback(line)
                break
            kv = stripped.strip().split(":", 1)
            if len(kv) == 2:
                fields[kv[0].strip()] = kv[1].strip()
        return Event(kind=EventKind.EPANDESC, raw="EPANDESC", fields=fields)

    def _parse_erxudp(self, line: str) -> Event:
        """ERXUDP 行を解析して payload を bytes に変換する (WOPT 01 前提)。

        フォーマット (仕様書):
          ERXUDP <sender> <dest> <rport> <lport> <senderlla> <secured>
                 [<side>] <datalen> <data>

        BP35A1 のファームウェアバージョンや WOPT 設定により <side> フィールドが
        省略される場合がある (実機 1.2.10 では省略)。 末尾から <data> を取ることで
        どちらのフォーマットにも対応する (<data> は WOPT 01 で 16 進文字列のため空白を含まない)。
        """
        parts = line.split(" ")
        payload = b""
        # 最低限: ERXUDP, sender, dest, rport, lport, senderlla, secured, datalen, data (9 要素)
        if len(parts) >= 9:
            try:
                payload = bytes.fromhex(parts[-1])
            except ValueError:
                self.logger.warning("ERXUDP payload not hex: %r", parts[-1])
        return Event(kind=EventKind.ERXUDP, raw=line, args=parts[1:], payload=payload)


class BP35A1Session:
    """BP35A1 とのコマンド送受信を Event 駆動で扱う。

    Layer 3 (BP35A1 クラス) はここを経由してコマンドを送り、必要なイベントを待つ。
    シリアルから読まれた行は EventParser で分類され、 イベント単位で API に返る。
    """

    def __init__(self, ser: serial.Serial) -> None:
        self.ser = ser
        self.parser = EventParser(ser)
        self.logger = logging.getLogger(__name__)

    def write_raw(self, data: bytes) -> None:
        """生バイト列を送信 (CRLF などは含めない)。"""
        self.ser.write(data)

    def send_line(self, line: str) -> None:
        """1 行コマンドを送信 (末尾に CRLF を付加)。"""
        self.logger.debug("SEND: %r", line)
        self.ser.write(line.encode() + b"\r\n")

    def collect_until(self, until: set[str], timeout: float) -> list[Event]:
        """until のいずれかの kind が来るまで、 受信した全 Event を集めて返す。

        - until に該当する Event は最後の要素として含まれる
        - timeout 経過時はそこまでの Event をすべて返す (until を含まない)
        """
        deadline = time.monotonic() + timeout
        events: list[Event] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return events
            # シリアル read のタイムアウトを残り時間に合わせる
            self.ser.timeout = max(0.1, remaining)
            evt = self.parser.next_event()
            if evt is None:
                continue  # 読みかけなしで戻った (1 行も読めず) → 残時間でリトライ
            events.append(evt)
            if evt.kind in until:
                return events

    def send_and_collect(self, command: str, until: set[str], timeout: float = 10) -> list[Event]:
        """コマンド送信 + until のいずれかが来るまで Event を集める。"""
        self.send_line(command)
        return self.collect_until(until, timeout)

    def send_and_expect(
        self, command: str, expect: set[str] | None = None, timeout: float = 5
    ) -> Event | None:
        """コマンド送信 + expect のいずれか 1 つ目を返す。タイムアウトで None。"""
        if expect is None:
            expect = {EventKind.OK, EventKind.FAIL}
        events = self.send_and_collect(command, expect, timeout)
        for evt in events:
            if evt.kind in expect:
                return evt
        return None

    def read_line_raw(self, timeout: float = 5) -> str | None:
        """生の 1 行を読む (Event 分類しない)。SKLL64 のような単発応答に使う。

        コマンドエコー等を素通しするので、 呼び出し側で必要なら捨てる。
        """
        self.ser.timeout = max(0.1, timeout)
        line = self.parser._read_line()
        if line is None:
            return None
        return line.rstrip("\r\n")
