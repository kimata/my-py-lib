from __future__ import annotations

import contextlib
import os
import pathlib
import threading
from collections.abc import Iterable
from dataclasses import dataclass

import psutil

_CGROUP_V2_MEMORY_CURRENT = pathlib.Path("/sys/fs/cgroup/memory.current")
_CGROUP_V1_MEMORY_CURRENT = pathlib.Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")

_CHROME_PROCESS_NAME_PARTS = ("chrome", "chromium", "headless_shell")


@dataclass(frozen=True)
class TrackedBrowserProcessSet:
    profile_name: str
    user_data_dir: pathlib.Path
    chromedriver_pid: int | None = None


class BrowserProcessRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, TrackedBrowserProcessSet] = {}
        self._lock = threading.Lock()

    def register(
        self, *, profile_name: str, user_data_dir: pathlib.Path, chromedriver_pid: int | None
    ) -> None:
        with self._lock:
            self._profiles[profile_name] = TrackedBrowserProcessSet(
                profile_name=profile_name,
                user_data_dir=user_data_dir,
                chromedriver_pid=chromedriver_pid,
            )

    def unregister(self, profile_name: str) -> None:
        with self._lock:
            self._profiles.pop(profile_name, None)

    def snapshot_profiles(self) -> tuple[TrackedBrowserProcessSet, ...]:
        with self._lock:
            return tuple(self._profiles.values())


browser_process_registry = BrowserProcessRegistry()


def read_pod_memory_bytes() -> int | None:
    for path in (_CGROUP_V2_MEMORY_CURRENT, _CGROUP_V1_MEMORY_CURRENT):
        if not path.exists():
            continue
        with contextlib.suppress(OSError, ValueError):
            return int(path.read_text().strip())
    return None


def read_process_pss_bytes(pid: int) -> int | None:
    proc_root = pathlib.Path("/proc") / str(pid)
    rollup_path = proc_root / "smaps_rollup"
    pss_kib = _read_pss_kib_from_file(rollup_path)
    if pss_kib is not None:
        return pss_kib * 1024

    smaps_path = proc_root / "smaps"
    pss_kib = _read_pss_kib_from_file(smaps_path)
    if pss_kib is not None:
        return pss_kib * 1024

    return None


def sum_process_pss_bytes(pids: Iterable[int]) -> int | None:
    total = 0
    measured = False
    for pid in set(pids):
        pss_bytes = read_process_pss_bytes(pid)
        if pss_bytes is None:
            continue
        total += pss_bytes
        measured = True
    return total if measured else None


def read_selenium_memory_bytes(registry: BrowserProcessRegistry | None = None) -> int | None:
    registry = registry or browser_process_registry
    tracked_pids: set[int] = set()

    for profile in registry.snapshot_profiles():
        tracked_pids.update(find_browser_related_pids(profile))

    return sum_process_pss_bytes(tracked_pids)


def find_browser_related_pids(profile: TrackedBrowserProcessSet) -> set[int]:
    pids: set[int] = set()
    profile_path = str(profile.user_data_dir)

    if profile.chromedriver_pid is not None:
        pids.add(profile.chromedriver_pid)
        with contextlib.suppress(psutil.Error):
            for child in psutil.Process(profile.chromedriver_pid).children(recursive=True):
                pids.add(child.pid)

    with contextlib.suppress(psutil.Error):
        current_process = psutil.Process(os.getpid())
        for child in current_process.children(recursive=True):
            if _matches_browser_process(child, profile_path):
                pids.add(child.pid)

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        with contextlib.suppress(psutil.Error):
            if _matches_browser_process(proc, profile_path):
                pids.add(proc.pid)

    return pids


def _matches_browser_process(process: psutil.Process, profile_path: str) -> bool:
    name = process.name().lower()
    if not any(part in name for part in _CHROME_PROCESS_NAME_PARTS):
        return False

    cmdline = process.cmdline()
    return any(arg == f"--user-data-dir={profile_path}" or profile_path in arg for arg in cmdline)


def _read_pss_kib_from_file(path: pathlib.Path) -> int | None:
    if not path.exists():
        return None

    with contextlib.suppress(OSError, ValueError):
        for line in path.read_text().splitlines():
            if not line.startswith("Pss:"):
                continue
            _, value, *_ = line.split()
            return int(value)

    return None
