#!/usr/bin/env python3
"""pytest-xdist 並列実行用ユーティリティ

pytest-xdist による並列テスト実行時に、ワーカー間の干渉を防ぐための
ユーティリティ関数を提供する。
"""

from __future__ import annotations

import os
import pathlib


def get_worker_id(default: str = "main") -> str:
    """pytest-xdist のワーカーIDを取得

    pytest-xdist による並列実行時に各ワーカーを識別するためのIDを返す。
    環境変数 PYTEST_XDIST_WORKER が設定されていない場合は default を返す。

    Parameters
    ----------
    default : str
        ワーカーIDが設定されていない場合のデフォルト値（デフォルト: "main"）

    Returns
    -------
        str: ワーカーID（例: "gw0", "gw1", ... または default）

    """
    return os.environ.get("PYTEST_XDIST_WORKER", default)


def get_path(path_str: str | pathlib.Path) -> pathlib.Path:
    """ワーカー固有のパスを取得

    pytest-xdist による並列実行時に、各ワーカーが独立したファイルを
    使用できるように、ファイル名にワーカーIDを付加したパスを返す。

    Parameters
    ----------
    path_str : str | pathlib.Path
        元のファイルパス

    Returns
    -------
        pathlib.Path: ワーカー固有のパス（例: "data.db" → "data.db.gw0"）

    """
    suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
    path = pathlib.Path(path_str)

    if suffix is None:
        return path
    else:
        return path.with_name(path.name + "." + suffix)
