#!/usr/bin/env python3
import logging
import os
import signal
import subprocess
import time

import psutil


def signal_name(sig):
    try:
        return signal.Signals(sig).name
    except ValueError:
        return "UNKNOWN"


def status_text(status):
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


def kill_child():  # noqa: C901, PLR0912
    """現在のプロセスの子プロセスを終了させる"""
    try:
        current_pid = os.getpid()
        # psコマンドで子プロセスを検索
        result = subprocess.run(
            ["ps", "-o", "pid,ppid,cmd", "--no-headers", "-A"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        child_pids = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.strip().split(None, 2)
                if len(parts) >= 2:
                    pid, ppid = parts[0], parts[1]
                    try:
                        if int(ppid) == current_pid and int(pid) != current_pid:
                            child_pids.append(int(pid))
                    except ValueError:
                        continue

        # 子プロセスにSIGTERMを送信
        for child_pid in child_pids:
            try:
                logging.info("Terminating child process: %d", child_pid)
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:  # noqa: PERF203
                pass  # プロセスが既に終了している
            except Exception as e:
                logging.warning("Failed to terminate child process %d: %s", child_pid, e)

        # 少し待ってからSIGKILLを送信
        if child_pids:
            time.sleep(0.5)
            for child_pid in child_pids:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:  # noqa: PERF203
                    pass  # プロセスが既に終了している
                except Exception as e:
                    logging.warning("Failed to kill child process %d: %s", child_pid, e)

    except Exception as e:
        logging.warning("Failed to kill child processes: %s", e)


def get_child_pid_map():
    pid_map = {}
    parent = psutil.Process()

    try:
        children = parent.children(recursive=False)
    except psutil.Error:
        return pid_map

    children = parent.children(recursive=False)
    for child in children:
        pid_map[child.pid] = child.name()

    return pid_map


def reap_zombie():
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
