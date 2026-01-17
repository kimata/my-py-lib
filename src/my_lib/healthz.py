#!/usr/bin/env python3
from __future__ import annotations

import logging
import pathlib
import socket
from dataclasses import dataclass

import requests

import my_lib.footprint


@dataclass(frozen=True)
class HealthzTarget:
    """Liveness チェック対象を表すデータクラス"""

    name: str
    liveness_file: pathlib.Path
    interval: float


def check_liveness(target: HealthzTarget) -> bool:
    """単一ターゲットの liveness をチェックする"""
    if not my_lib.footprint.exists(target.liveness_file):
        logging.warning("%s is not executed.", target.name)
        return False

    elapsed = my_lib.footprint.elapsed(target.liveness_file)
    # NOTE: 少なくとも1分は様子を見る
    if elapsed > max(target.interval * 2, 60):
        logging.warning("Execution interval of %s is too long. %s sec)", target.name, f"{elapsed:,.1f}")
        return False
    else:
        logging.debug("Execution interval of %s: %s sec)", target.name, f"{elapsed:,.1f}")
        return True


def check_liveness_all(target_list: list[HealthzTarget]) -> list[str]:
    """複数ターゲットの liveness をチェックし、失敗したターゲット名のリストを返す"""
    return [target.name for target in target_list if not check_liveness(target)]


def check_tcp_port(port: int, address: str = "127.0.0.1") -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((address, port))
        sock.close()
        return result == 0
    except OSError:
        logging.exception("Failed to check TCP port")
        return False


def check_http_port(port: int, address: str = "127.0.0.1") -> bool:
    try:
        if requests.get(f"http://{address}:{port}/", timeout=5).status_code == 200:
            return True
    except requests.RequestException:
        logging.exception("Failed to access Web server")

    return False
