"""Chrome プロファイル管理ユーティリティ

Chrome プロファイルの健全性チェック、リカバリ、クリーンアップなどを提供します。
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import signal
import sqlite3
import time
from dataclasses import dataclass

import psutil

import my_lib.time


@dataclass(frozen=True)
class _ProfileHealthResult:
    """プロファイル健全性チェックの結果"""

    is_healthy: bool
    errors: tuple[str, ...]
    has_lock_files: bool = False
    has_corrupted_json: bool = False
    has_corrupted_db: bool = False


def _check_json_file(file_path: pathlib.Path) -> str | None:
    """JSON ファイルの整合性をチェック

    Returns:
        エラーメッセージ（正常な場合は None）

    """
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
        json.loads(content)
        return None
    except json.JSONDecodeError as e:
        return f"{file_path.name} is corrupted: {e}"
    except Exception as e:
        return f"{file_path.name} read error: {e}"


def _check_sqlite_db(db_path: pathlib.Path) -> str | None:
    """SQLite データベースの整合性をチェック

    Returns:
        エラーメッセージ（正常な場合は None）

    """
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result[0] != "ok":
            return f"{db_path.name} database is corrupted: {result[0]}"
        return None
    except sqlite3.DatabaseError as e:
        return f"{db_path.name} database error: {e}"
    except Exception as e:
        return f"{db_path.name} check error: {e}"


def _check_profile_health(profile_path: pathlib.Path) -> _ProfileHealthResult:
    """Chrome プロファイルの健全性をチェック

    Args:
        profile_path: Chrome プロファイルのディレクトリパス

    Returns:
        ProfileHealthResult: チェック結果

    """
    errors: list[str] = []
    has_lock_files = False
    has_corrupted_json = False
    has_corrupted_db = False

    if not profile_path.exists():
        # プロファイルが存在しない場合は健全（新規作成される）
        return _ProfileHealthResult(is_healthy=True, errors=())

    default_path = profile_path / "Default"

    # 1. ロックファイルのチェック
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    existing_locks = []
    for lock_file in lock_files:
        lock_path = profile_path / lock_file
        if lock_path.exists() or lock_path.is_symlink():
            existing_locks.append(lock_file)
            has_lock_files = True
    if existing_locks:
        errors.append(f"Lock files exist: {', '.join(existing_locks)}")

    # 2. Local State の JSON チェック
    local_state_error = _check_json_file(profile_path / "Local State")
    if local_state_error:
        errors.append(local_state_error)
        has_corrupted_json = True

    # 3. Preferences の JSON チェック
    if default_path.exists():
        prefs_error = _check_json_file(default_path / "Preferences")
        if prefs_error:
            errors.append(prefs_error)
            has_corrupted_json = True

        # 4. SQLite データベースの整合性チェック
        for db_name in ["Cookies", "History", "Web Data"]:
            db_error = _check_sqlite_db(default_path / db_name)
            if db_error:
                errors.append(db_error)
                has_corrupted_db = True

    is_healthy = len(errors) == 0

    return _ProfileHealthResult(
        is_healthy=is_healthy,
        errors=tuple(errors),
        has_lock_files=has_lock_files,
        has_corrupted_json=has_corrupted_json,
        has_corrupted_db=has_corrupted_db,
    )


def _recover_corrupted_profile(profile_path: pathlib.Path) -> bool:
    """破損したプロファイルをバックアップして新規作成を可能にする

    Args:
        profile_path: Chrome プロファイルのディレクトリパス

    Returns:
        bool: リカバリが成功したかどうか

    """
    if not profile_path.exists():
        return True

    # バックアップ先を決定（タイムスタンプ付き）
    timestamp = my_lib.time.now().strftime("%Y%m%d_%H%M%S")
    backup_path = profile_path.parent / f"{profile_path.name}.corrupted.{timestamp}"

    try:
        shutil.move(str(profile_path), str(backup_path))
        logging.warning(
            "Corrupted profile moved to backup: %s -> %s",
            profile_path,
            backup_path,
        )
        return True
    except Exception:
        logging.exception("Failed to backup corrupted profile")
        return False


def _cleanup_profile_lock(profile_path: pathlib.Path) -> None:
    """プロファイルのロックファイルを削除する"""
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    found_locks = []
    for lock_file in lock_files:
        lock_path = profile_path / lock_file
        if lock_path.exists() or lock_path.is_symlink():
            found_locks.append(lock_path)

    if found_locks:
        logging.warning("Profile lock files found: %s", ", ".join(str(p.name) for p in found_locks))
        for lock_path in found_locks:
            try:
                lock_path.unlink()
            except OSError as e:
                logging.warning("Failed to remove lock file %s: %s", lock_path, e)


def _is_running_in_container() -> bool:
    """コンテナ内で実行中かどうかを判定"""
    return pathlib.Path("/.dockerenv").exists()


def _cleanup_orphaned_chrome_processes_in_container() -> None:
    """コンテナ内で実行中の場合のみ、残った Chrome プロセスをクリーンアップ

    NOTE: プロセスツリーに関係なくプロセス名で一律終了するのはコンテナ内限定
    """
    if not _is_running_in_container():
        return

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc_name = proc.info["name"].lower() if proc.info["name"] else ""
            if "chrome" in proc_name:
                logging.info("Terminating orphaned Chrome process: PID %d", proc.info["pid"])
                os.kill(proc.info["pid"], signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError, OSError):
            pass
    time.sleep(1)


def _get_actual_profile_name(profile_name: str) -> str:
    """PYTEST_XDIST_WORKER を考慮した実際のプロファイル名を取得"""
    suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
    return profile_name + ("." + suffix if suffix is not None else "")


def cleanup_profile_lock(profile_name: str, data_path: pathlib.Path) -> None:
    """Chrome プロファイルのロックファイルを削除する

    ドライバー終了後に残ったロックファイルをクリーンアップします。

    Args:
        profile_name: プロファイル名
        data_path: データディレクトリのパス

    """
    actual_profile_name = _get_actual_profile_name(profile_name)
    profile_path = data_path / "chrome" / actual_profile_name
    _cleanup_profile_lock(profile_path)


def delete_profile(profile_name: str, data_path: pathlib.Path) -> bool:
    """Chrome プロファイルを削除する

    Args:
        profile_name: プロファイル名
        data_path: データディレクトリのパス

    Returns:
        bool: 削除が成功したかどうか

    """
    actual_profile_name = _get_actual_profile_name(profile_name)
    profile_path = data_path / "chrome" / actual_profile_name

    if not profile_path.exists():
        logging.info("Profile does not exist: %s", profile_path)
        return True

    try:
        shutil.rmtree(profile_path)
        logging.warning("Deleted Chrome profile: %s", profile_path)
        return True
    except Exception:
        logging.exception("Failed to delete Chrome profile: %s", profile_path)
        return False
