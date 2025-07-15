#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import logging
import os
import pathlib
import shutil
import sys
import time


def cleanup_old_chrome_profiles(
    data_path: pathlib.Path, max_age_hours: int = 24, keep_count: int = 3
) -> list[str]:
    """
    古いChromeプロファイルを自動削除する

    Args:
    ----
        data_path: データディレクトリのパス
        max_age_hours: 削除対象とする最大経過時間（時間）
        keep_count: 最低限保持するプロファイル数

    Returns:
    -------
        削除されたプロファイルのリスト

    """
    chrome_dir = data_path / "chrome"
    if not chrome_dir.exists():
        return []

    removed_profiles = []
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    # プロファイル一覧を取得（作成時刻でソート）
    profiles = []
    for item in chrome_dir.iterdir():
        if item.is_dir() and item.name != "Default":
            try:
                mtime = item.stat().st_mtime
                profiles.append((item, mtime))
            except OSError:
                continue

    # 作成時刻でソート（新しい順）
    profiles.sort(key=lambda x: x[1], reverse=True)

    # 保持すべきプロファイル数を超えた古いプロファイルを削除
    for i, (profile_path, mtime) in enumerate(profiles):
        should_remove = False

        # 最低限保持する数を超えている場合
        if i >= keep_count:
            should_remove = True

        # 最大経過時間を超えている場合
        if current_time - mtime > max_age_seconds:
            should_remove = True

        if should_remove:
            try:
                logging.info("Removing old Chrome profile: %s", profile_path)
                shutil.rmtree(profile_path)
                removed_profiles.append(str(profile_path))
            except OSError as e:
                logging.warning("Failed to remove Chrome profile %s: %s", profile_path, e)

    return removed_profiles


def cleanup_orphaned_chrome_processes():
    """孤立したChromeプロセスを終了する."""
    try:
        import psutil

        orphaned_processes = []
        chrome_processes = []

        # 全てのChromeプロセスを収集
        for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid", "status"]):
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                if proc.info["name"] and "chrome" in proc.info["name"].lower():
                    chrome_processes.append(proc)

                    # ゾンビプロセスまたは孤立プロセスをチェック
                    if proc.info["status"] == psutil.STATUS_ZOMBIE:
                        orphaned_processes.append(proc)
                    else:
                        # 親プロセスが存在しない場合は孤立プロセスと判定
                        parent = proc.parent()
                        if parent is None or not parent.is_running():
                            orphaned_processes.append(proc)

        logging.info("Found %d Chrome processes, %d orphaned", len(chrome_processes), len(orphaned_processes))

        # 段階的にプロセスを終了
        for proc in orphaned_processes:
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                if proc.info["status"] == psutil.STATUS_ZOMBIE:
                    logging.info("Found zombie Chrome process: %s", proc.pid)
                    continue  # ゾンビプロセスは親プロセスが回収する必要がある

                logging.info("Terminating orphaned Chrome process: %s (PID: %s)", proc.info["name"], proc.pid)
                try:
                    # 最初はSIGTERMで優雅に終了を試行
                    proc.terminate()
                    proc.wait(timeout=3)
                    logging.info("Successfully terminated Chrome process: %s", proc.pid)
                except psutil.TimeoutExpired:
                    # タイムアウトした場合はSIGKILLで強制終了
                    with contextlib.suppress(psutil.NoSuchProcess):
                        logging.info("Force killing Chrome process: %s", proc.pid)
                        proc.kill()
                        proc.wait(timeout=2)

        # プロセスグループでの終了も試行
        _cleanup_chrome_process_groups()

    except ImportError:
        logging.warning("psutil not available, skipping orphaned process cleanup")


def _cleanup_chrome_process_groups():
    """Chromeプロセスグループの強制終了"""
    try:
        import shutil
        import subprocess

        # pkillが利用可能かチェック
        if not shutil.which("pkill"):
            logging.warning("pkill not available, skipping process group cleanup")
            return

        # pkillでChromeプロセス全体を終了
        pkill_path = shutil.which("pkill")
        result = subprocess.run(  # noqa: S603
            [pkill_path, "-f", "chrome"], capture_output=True, text=True, timeout=5, check=False
        )

        if result.returncode == 0:
            logging.info("Successfully cleaned up Chrome processes with pkill")

        # Chrome crashpadプロセスも終了
        subprocess.run(  # noqa: S603
            [pkill_path, "-f", "chrome_crashpad"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        logging.warning("Failed to cleanup Chrome process groups")
    except Exception as e:
        logging.warning("Error during Chrome process group cleanup: %s", e)


def get_chrome_profile_stats(data_path: pathlib.Path) -> dict:
    """Chromeプロファイルの統計情報を取得."""
    chrome_dir = data_path / "chrome"
    if not chrome_dir.exists():
        return {"total_count": 0, "total_size_mb": 0}

    total_size = 0
    profile_count = 0

    for item in chrome_dir.iterdir():
        if item.is_dir():
            profile_count += 1
            try:
                # ディレクトリサイズを計算
                for root, _dirs, files in os.walk(item):
                    for file in files:
                        file_path = pathlib.Path(root) / file
                        try:
                            total_size += file_path.stat().st_size
                        except OSError:
                            continue
            except OSError:
                continue

    return {"total_count": profile_count, "total_size_mb": round(total_size / (1024 * 1024), 2)}


if __name__ == "__main__":
    # テスト用のクリーンアップ実行
    logging.basicConfig(level=logging.INFO)

    data_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("data")

    # Before cleanup stats
    stats = get_chrome_profile_stats(data_path)
    logging.info("Chrome profile stats before cleanup:")
    logging.info("  Profiles: %s", stats["total_count"])
    logging.info("  Total size: %s MB", stats["total_size_mb"])

    removed = cleanup_old_chrome_profiles(data_path)
    cleanup_orphaned_chrome_processes()

    logging.info("Removed %s old profiles", len(removed))

    # After cleanup stats
    stats = get_chrome_profile_stats(data_path)
    logging.info("Chrome profile stats after cleanup:")
    logging.info("  Profiles: %s", stats["total_count"])
    logging.info("  Total size: %s MB", stats["total_size_mb"])
