#!/usr/bin/env python3
"""メルカリ関連の例外クラス定義"""

from __future__ import annotations


class MercariError(Exception):
    """メルカリ関連エラーの基底クラス"""


class LoginError(MercariError):
    """メルカリへのログインに失敗した場合に発生するエラー"""
