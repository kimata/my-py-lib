#!/usr/bin/env python3
"""センサー関連の例外クラス定義"""

from __future__ import annotations


class SensorError(Exception):
    """センサー関連エラーの基底クラス"""

    pass


class SensorCommunicationError(SensorError):
    """センサー通信エラー"""

    pass


class SensorCRCError(SensorError):
    """センサー CRC エラー"""

    pass
