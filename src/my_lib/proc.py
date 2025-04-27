#!/usr/bin/env python3
import logging
import os

import psutil


def signal_name(sig):
    import signal

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
