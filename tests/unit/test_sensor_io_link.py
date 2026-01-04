#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/io_link.py のテスト"""

from __future__ import annotations

from my_lib.sensor import io_link


class TestIoLinkConstants:
    """IO-Link 定数のテスト"""

    def test_msq_rw_constants(self):
        """MSQ RW 定数が正しい値を持つ"""
        assert io_link.MSQ_RW_READ == 1
        assert io_link.MSQ_RW_WRITE == 0

    def test_msq_ch_constants(self):
        """MSQ CH 定数が正しい値を持つ"""
        assert io_link.MSQ_CH_PROCESS == 0
        assert io_link.MSQ_CH_PAGE == 1
        assert io_link.MSQ_CH_DIAG == 2
        assert io_link.MSQ_CH_ISDU == 3

    def test_msq_type_constants(self):
        """MSQ TYPE 定数が正しい値を持つ"""
        assert io_link.MSQ_TYPE_0 == 0
        assert io_link.MSQ_TYPE_1 == 1
        assert io_link.MSQ_TYPE_2 == 2

    def test_isdu_isrv_constants(self):
        """ISDU ISRV 定数が正しい値を持つ"""
        assert io_link.ISDU_ISRV_READ_8BIT_IDX == 0b1001

    def test_isdu_idx_constants(self):
        """ISDU IDX 定数が正しい値を持つ"""
        assert io_link.ISDU_IDX_VENDOR_NAME == 0x10
        assert io_link.ISDU_IDX_VENDOR_TEXT == 0x11

    def test_all_constants_are_int(self):
        """全ての定数が int 型である"""
        constants = [
            io_link.MSQ_RW_READ,
            io_link.MSQ_RW_WRITE,
            io_link.MSQ_CH_PROCESS,
            io_link.MSQ_CH_PAGE,
            io_link.MSQ_CH_DIAG,
            io_link.MSQ_CH_ISDU,
            io_link.MSQ_TYPE_0,
            io_link.MSQ_TYPE_1,
            io_link.MSQ_TYPE_2,
            io_link.ISDU_ISRV_READ_8BIT_IDX,
            io_link.ISDU_IDX_VENDOR_NAME,
            io_link.ISDU_IDX_VENDOR_TEXT,
        ]
        for const in constants:
            assert isinstance(const, int)
