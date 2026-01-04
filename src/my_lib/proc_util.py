#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import signal

import psutil


def signal_name(sig: int) -> str:
    try:
        return signal.Signals(sig).name
    except ValueError:
        return "UNKNOWN"


def status_text(status: int) -> str:
    if os.WIFEXITED(status):
        return f"Exited normally with code {os.WEXITSTATUS(status)}"
    elif os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        return f"Terminated by signal {sig} ({signal_name(sig)})"
    elif os.WIFSTOPPED(status):
        sig = os.WSTOPSIG(status)
        return f"Stopped by signal {sig} ({signal_name(sig)})"
    else:
        return f"Unknown status: {status}"


def kill_child(timeout: float = 5) -> None:
    """現在のプロセスの子プロセスを終了させる

    Args:
        timeout: プロセス終了を待つ最大時間（秒）

    """
    try:
        parent = psutil.Process()
        children = parent.children(recursive=True)

        if not children:
            return

        # 子プロセスにSIGTERMを送信
        for child in children:
            try:
                logging.info("Terminating child process: %d (%s)", child.pid, child.name())
                child.terminate()
            except psutil.NoSuchProcess:
                pass  # プロセスが既に終了している
            except psutil.AccessDenied:
                logging.warning("Access denied to terminate process %d", child.pid)
            except Exception as e:
                logging.warning("Failed to terminate child process %d: %s", child.pid, e)

        # プロセスの終了を待つ（最大timeout/2秒）
        gone, alive = psutil.wait_procs(children, timeout=min(timeout / 2, 2.5))

        # まだ生きているプロセスにSIGKILLを送信
        if alive:
            for child in alive:
                try:
                    logging.warning("Force killing child process: %d (%s)", child.pid, child.name())
                    child.kill()
                except psutil.NoSuchProcess:
                    pass  # プロセスが既に終了している
                except psutil.AccessDenied:
                    logging.warning("Access denied to kill process %d", child.pid)
                except Exception as e:
                    logging.warning("Failed to kill child process %d: %s", child.pid, e)

            # SIGKILLの効果を待つ
            gone, alive = psutil.wait_procs(alive, timeout=min(timeout / 2, 2.5))

            # それでも終了しないプロセスがある場合は警告
            if alive:
                for child in alive:
                    logging.error(
                        "Failed to terminate child process %d (%s) within timeout", child.pid, child.name()
                    )

    except Exception as e:
        logging.warning("Failed to kill child processes: %s", e)


def get_child_pid_map() -> dict[int, str]:
    pid_map: dict[int, str] = {}
    parent = psutil.Process()

    try:
        children = parent.children(recursive=False)
    except psutil.Error:
        return pid_map

    children = parent.children(recursive=False)
    for child in children:
        pid_map[child.pid] = child.name()

    return pid_map


def reap_zombie() -> None:
    pid_map = get_child_pid_map()
    try:
        while True:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break

            logging.warning(
                "Reaped zombie process: pid=%d cmd=%s status=%s",
                pid,
                pid_map[pid],
                status_text(status),
            )
    except ChildProcessError:
        pass
