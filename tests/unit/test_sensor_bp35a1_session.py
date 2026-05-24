#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/bp35a1_session.py のテスト"""

from __future__ import annotations

from collections import deque

import pytest

from my_lib.sensor.bp35a1_session import BP35A1Session, Event, EventKind, EventParser


class FakeSerial:
    """シリアルポートのモック。readline で順次行を返す。"""

    def __init__(self, lines: list[bytes]) -> None:
        self._queue: deque[bytes] = deque(lines)
        self.timeout: float = 5.0
        self.written: bytearray = bytearray()

    def readline(self) -> bytes:
        if self._queue:
            return self._queue.popleft()
        return b""  # timeout を模擬

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    def reset_input_buffer(self) -> None:
        self._queue.clear()

    def reset_output_buffer(self) -> None:
        self.written.clear()

    def feed(self, *lines: bytes) -> None:
        """追加の行を末尾に投入する。"""
        for line in lines:
            self._queue.append(line)


class TestEventParserBasic:
    """EventParser の基本的な行分類のテスト"""

    def test_ok_alone(self):
        ser = FakeSerial([b"OK\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.OK
        assert evt.args == []

    def test_ok_with_args(self):
        ser = FakeSerial([b"OK 01\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.OK
        assert evt.args == ["01"]

    def test_fail(self):
        ser = FakeSerial([b"FAIL ER01\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.FAIL
        assert evt.args == ["ER01"]

    def test_event_22(self):
        ser = FakeSerial([b"EVENT 22 FE80:0000:0000:0000:021D:1290:0004:63D3\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.EVENT_22
        assert evt.args == ["FE80:0000:0000:0000:021D:1290:0004:63D3"]

    def test_event_25(self):
        ser = FakeSerial([b"EVENT 25 FE80::1\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.EVENT_25

    def test_einfo(self):
        ser = FakeSerial([b"EINFO FE80::1 001D1290000463D3 21 FFFF FFFE\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.EINFO
        assert evt.args[0] == "FE80::1"

    def test_blank_lines_skipped(self):
        ser = FakeSerial([b"\r\n", b"\r\n", b"OK\r\n"])
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.OK

    def test_unknown_line(self):
        ser = FakeSerial([b"SKSCAN 3 FFFFFFFF 8\r\n"])  # コマンドエコー
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.UNKNOWN

    def test_timeout_returns_none(self):
        ser = FakeSerial([])  # 何も流さない (readline が "" を返す)
        evt = EventParser(ser).next_event()
        assert evt is None


class TestEventParserPanDesc:
    """EPANDESC ブロックの解析テスト"""

    def test_mode2_with_pair_id(self):
        """MODE 2 の応答 (PairID あり)"""
        ser = FakeSerial(
            [
                b"EPANDESC\r\n",
                b"  Channel:21\r\n",
                b"  Channel Page:09\r\n",
                b"  Pan ID:8888\r\n",
                b"  Addr:001D129012345678\r\n",
                b"  LQI:A7\r\n",
                b"  PairID:01234567\r\n",
            ]
        )
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.EPANDESC
        assert evt.fields["Channel"] == "21"
        assert evt.fields["Pan ID"] == "8888"
        assert evt.fields["Addr"] == "001D129012345678"
        assert evt.fields["PairID"] == "01234567"

    def test_mode3_without_pair_id(self):
        """MODE 3 の応答 (PairID なし) — EVENT 22 が後続する典型ケース"""
        ser = FakeSerial(
            [
                b"EPANDESC\r\n",
                b"  Channel:3B\r\n",
                b"  Channel Page:09\r\n",
                b"  Pan ID:2D7E\r\n",
                b"  Addr:38E08E0001912D7E\r\n",
                b"  LQI:89\r\n",
                b"EVENT 22 FE80::1\r\n",
            ]
        )
        parser = EventParser(ser)
        evt1 = parser.next_event()
        assert evt1 is not None
        assert evt1.kind == EventKind.EPANDESC
        assert evt1.fields["LQI"] == "89"
        assert "PairID" not in evt1.fields

        # 終端を超えて読まれた EVENT 22 は pushback されて次の next_event で返るべき
        evt2 = parser.next_event()
        assert evt2 is not None
        assert evt2.kind == EventKind.EVENT_22

    def test_block_aborted_by_timeout(self):
        """ブロック途中で timeout (シリアル無音) になっても落ちない"""
        ser = FakeSerial(
            [b"EPANDESC\r\n", b"  Channel:3B\r\n"]
            # その後 readline が "" を返してタイムアウト
        )
        evt = EventParser(ser).next_event()
        assert evt is not None
        assert evt.kind == EventKind.EPANDESC
        assert evt.fields == {"Channel": "3B"}


class TestEventParserErxudp:
    """ERXUDP の解析テスト"""

    def test_payload_decoded(self):
        # ERXUDP <sender> <dest> <rport> <lport> <senderlla> <secured> <side> <datalen> <data>
        line = b"ERXUDP FE80::1 FE80::2 0E1A 0E1A 001D129000000001 1 0 000A 31323334353637383930\r\n"
        evt = EventParser(FakeSerial([line])).next_event()
        assert evt is not None
        assert evt.kind == EventKind.ERXUDP
        # payload は 16 進文字列 "31323334..." をデコードしたもの = "1234567890"
        assert evt.payload == b"1234567890"
        assert evt.args[0] == "FE80::1"  # sender


class TestBP35A1Session:
    """BP35A1Session のテスト"""

    def test_send_and_expect_ok(self):
        ser = FakeSerial(
            [
                b"SKSETRBID 0123\r\n",  # コマンドエコー (UNKNOWN として捨てられる)
                b"OK\r\n",
            ]
        )
        sess = BP35A1Session(ser)
        evt = sess.send_and_expect("SKSETRBID 0123", timeout=2)
        assert evt is not None
        assert evt.kind == EventKind.OK
        # 実際に送信された内容に CRLF が含まれているか
        assert ser.written.endswith(b"\r\n")
        assert b"SKSETRBID 0123" in bytes(ser.written)

    def test_send_and_expect_timeout_returns_none(self):
        ser = FakeSerial([])
        sess = BP35A1Session(ser)
        evt = sess.send_and_expect("FOO", timeout=0.3)
        assert evt is None

    def test_collect_until_includes_terminator(self):
        ser = FakeSerial(
            [
                b"EVENT 20 FE80::1\r\n",
                b"EPANDESC\r\n",
                b"  Channel:3B\r\n",
                b"  Pan ID:2D7E\r\n",
                b"  Addr:38E08E0001912D7E\r\n",
                b"  LQI:89\r\n",
                b"EVENT 22 FE80::1\r\n",
            ]
        )
        sess = BP35A1Session(ser)
        events = sess.send_and_collect("SKSCAN 3 FFFFFFFF 8", until={EventKind.EVENT_22}, timeout=2)
        kinds = [e.kind for e in events]
        # 順序: EVENT_20, EPANDESC, EVENT_22
        assert EventKind.EVENT_20 in kinds
        assert EventKind.EPANDESC in kinds
        assert kinds[-1] == EventKind.EVENT_22

    def test_collect_until_timeout_returns_partial(self):
        ser = FakeSerial(
            [
                b"OK\r\n",
                b"EVENT 20 FE80::1\r\n",
                # EVENT 22 が来ないまま timeout
            ]
        )
        sess = BP35A1Session(ser)
        events = sess.collect_until({EventKind.EVENT_22}, timeout=0.5)
        kinds = [e.kind for e in events]
        # EVENT_22 は来ないが、 OK と EVENT_20 は集まる
        assert EventKind.OK in kinds
        assert EventKind.EVENT_20 in kinds
        assert EventKind.EVENT_22 not in kinds


@pytest.fixture
def bp_session():
    """fake serial で初期化された BP35A1Session を返す"""
    return BP35A1Session(FakeSerial([]))


def test_event_dataclass_defaults():
    """Event のフィールドのデフォルト値"""
    evt = Event(kind=EventKind.OK, raw="OK")
    assert evt.args == []
    assert evt.fields == {}
    assert evt.payload == b""
