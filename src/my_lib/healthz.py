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


@dataclass(frozen=True)
class HttpHealthzTarget:
    """HTTP ヘルスチェック対象を表すデータクラス"""

    name: str
    url: str
    timeout: float = 5.0
    expected_status: int = 200


def check_liveness(target: HealthzTarget) -> bool:
    """単一ターゲットの liveness をチェックする"""
    return check_liveness_elapsed(target) is None


def check_liveness_elapsed(target: HealthzTarget) -> float | None:
    """単一ターゲットの liveness をチェックし、失敗時の経過秒を返す

    Returns:
        成功時は None、失敗時は最終更新からの経過秒数を返す。
        ファイルが存在しない場合は -1 を返す。
    """
    if not my_lib.footprint.exists(target.liveness_file):
        logging.warning("%s is not executed.", target.name)
        return -1

    elapsed = my_lib.footprint.elapsed(target.liveness_file)
    # NOTE: 少なくとも1分は様子を見る
    if elapsed > max(target.interval * 2, 60):
        logging.warning("Execution interval of %s is too long. %s sec)", target.name, f"{elapsed:,.1f}")
        return elapsed
    else:
        logging.debug("Execution interval of %s: %s sec)", target.name, f"{elapsed:,.1f}")
        return None


def check_liveness_all(target_list: list[HealthzTarget]) -> list[str]:
    """複数ターゲットの liveness をチェックし、失敗したターゲット名のリストを返す"""
    return [target.name for target in target_list if check_liveness(target) is False]


def check_liveness_all_with_ports(
    target_list: list[HealthzTarget],
    *,
    http_port: int | None = None,
    tcp_port: int | None = None,
) -> list[str]:
    """複数ターゲット + ポートの liveness をチェックし、失敗名のリストを返す

    Args:
        target_list: liveness 対象のリスト
        http_port: HTTP ポート（指定時のみチェック）
        tcp_port: TCP ポート（指定時のみチェック）
    """
    failed = check_liveness_all(target_list)

    if http_port is not None and not check_http_port(http_port):
        failed.append("http_port")
    if tcp_port is not None and not check_tcp_port(tcp_port):
        failed.append("tcp_port")

    return failed


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


def check_http_healthz(target: HttpHealthzTarget) -> bool:
    """HTTP エンドポイントのヘルスチェック

    Args:
        target: チェック対象

    Returns:
        成功時は True、失敗時は False
    """
    try:
        resp = requests.get(target.url, timeout=target.timeout)
        if resp.status_code == target.expected_status:
            logging.debug("%s: 正常", target.name)
            return True
        logging.warning("%s がステータス %d を返しました", target.name, resp.status_code)
        return False
    except requests.RequestException as e:
        logging.warning("%s に接続できません: %s", target.name, e)
        return False


def check_healthz_all(
    liveness_targets: list[HealthzTarget] | None = None,
    http_targets: list[HttpHealthzTarget] | None = None,
) -> list[str]:
    """全ターゲット（liveness + HTTP）の統合ヘルスチェック

    Args:
        liveness_targets: liveness ファイルベースのチェック対象
        http_targets: HTTP エンドポイントのチェック対象

    Returns:
        失敗したターゲット名のリスト
    """
    failed: list[str] = []

    if liveness_targets:
        failed.extend(check_liveness_all(liveness_targets))

    if http_targets:
        failed.extend(target.name for target in http_targets if not check_http_healthz(target))

    return failed
