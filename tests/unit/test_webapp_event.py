#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.event モジュールのユニットテスト
"""
from __future__ import annotations

import pytest


class TestEventType:
    """EVENT_TYPE 列挙型のテスト"""

    def test_has_control(self):
        """CONTROL を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.CONTROL.value == "control"

    def test_has_schedule(self):
        """SCHEDULE を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.SCHEDULE.value == "schedule"

    def test_has_log(self):
        """LOG を持つ"""
        from my_lib.webapp.event import EVENT_TYPE

        assert EVENT_TYPE.LOG.value == "log"


class TestEventIndex:
    """event_index 関数のテスト"""

    def test_control_index(self):
        """CONTROL のインデックス"""
        from my_lib.webapp.event import EVENT_TYPE, event_index

        assert event_index(EVENT_TYPE.CONTROL) == 0

    def test_schedule_index(self):
        """SCHEDULE のインデックス"""
        from my_lib.webapp.event import EVENT_TYPE, event_index

        assert event_index(EVENT_TYPE.SCHEDULE) == 1

    def test_log_index(self):
        """LOG のインデックス"""
        from my_lib.webapp.event import EVENT_TYPE, event_index

        assert event_index(EVENT_TYPE.LOG) == 2


class TestNotifyEvent:
    """notify_event 関数のテスト"""

    def test_increments_event_count(self):
        """イベントカウントを増加させる"""
        from my_lib.webapp.event import EVENT_TYPE, event_count, event_index, notify_event

        initial = event_count[event_index(EVENT_TYPE.LOG)]
        notify_event(EVENT_TYPE.LOG)

        assert event_count[event_index(EVENT_TYPE.LOG)] == initial + 1


class TestTerm:
    """term 関数のテスト"""

    def test_does_not_raise_without_thread(self):
        """スレッドがなくてもエラーにならない"""
        from my_lib.webapp.event import term

        # 例外が発生しなければ OK
        term()
