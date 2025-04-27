#!/usr/bin/env python3
import logging
import os


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


def reap_zombie():
    try:
        while True:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            logging.warning("Reaped zombie process: pid=%d status=%s", pid, status_text(status))
    except ChildProcessError:
        pass
