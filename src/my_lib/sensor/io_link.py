#!/usr/bin/env python3

from __future__ import annotations

MSQ_RW_READ: int = 1
MSQ_RW_WRITE: int = 0

MSQ_CH_PROCESS: int = 0
MSQ_CH_PAGE: int = 1
MSQ_CH_DIAG: int = 2
MSQ_CH_ISDU: int = 3

MSQ_TYPE_0: int = 0
MSQ_TYPE_1: int = 1
MSQ_TYPE_2: int = 2

ISDU_ISRV_READ_8BIT_IDX: int = 0b1001

ISDU_IDX_VENDOR_NAME: int = 0x10
ISDU_IDX_VENDOR_TEXT: int = 0x11
