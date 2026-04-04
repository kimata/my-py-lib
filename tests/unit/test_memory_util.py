# ruff: noqa: S101

from __future__ import annotations

import pathlib
import unittest.mock

import psutil

import my_lib.memory_util


def test_read_pod_memory_bytes_prefers_cgroup_v2(tmp_path: pathlib.Path) -> None:
    cgroup_v2 = tmp_path / "memory.current"
    cgroup_v2.write_text("12345\n")

    with (
        unittest.mock.patch.object(my_lib.memory_util, "_CGROUP_V2_MEMORY_CURRENT", cgroup_v2),
        unittest.mock.patch.object(
            my_lib.memory_util,
            "_CGROUP_V1_MEMORY_CURRENT",
            tmp_path / "missing.usage_in_bytes",
        ),
    ):
        assert my_lib.memory_util.read_pod_memory_bytes() == 12345


def test_read_process_pss_bytes_uses_smaps_rollup(tmp_path: pathlib.Path) -> None:
    rollup_path = pathlib.Path("/proc/123/smaps_rollup")

    with unittest.mock.patch(
        "my_lib.memory_util._read_pss_kib_from_file",
        side_effect=lambda path: 42 if path == rollup_path else None,
    ):
        assert my_lib.memory_util.read_process_pss_bytes(123) == 42 * 1024


def test_sum_process_pss_bytes_returns_none_when_unmeasured() -> None:
    with unittest.mock.patch("my_lib.memory_util.read_process_pss_bytes", return_value=None):
        assert my_lib.memory_util.sum_process_pss_bytes({1, 2}) is None


def test_read_selenium_memory_bytes_aggregates_registry() -> None:
    registry = my_lib.memory_util.BrowserProcessRegistry()
    registry.register(profile_name="a", user_data_dir=pathlib.Path("/tmp/a"), chromedriver_pid=100)  # noqa: S108

    with (
        unittest.mock.patch("my_lib.memory_util.find_browser_related_pids", return_value={100, 101}),
        unittest.mock.patch("my_lib.memory_util.sum_process_pss_bytes", return_value=2048) as mock_sum,
    ):
        assert my_lib.memory_util.read_selenium_memory_bytes(registry) == 2048
        mock_sum.assert_called_once_with({100, 101})


def test_find_browser_related_pids_matches_profile_path() -> None:
    profile = my_lib.memory_util.TrackedBrowserProcessSet(
        profile_name="test",
        user_data_dir=pathlib.Path("/tmp/chrome/profile"),  # noqa: S108
        chromedriver_pid=50,
    )
    chromedriver = unittest.mock.MagicMock()
    chromedriver.children.return_value = [unittest.mock.Mock(pid=51)]
    profile_proc = unittest.mock.MagicMock(spec=psutil.Process)
    profile_proc.pid = 52
    profile_proc.name.return_value = "chrome"
    profile_proc.cmdline.return_value = ["chrome", "--user-data-dir=/tmp/chrome/profile"]
    other_proc = unittest.mock.MagicMock(spec=psutil.Process)
    other_proc.pid = 60
    other_proc.name.return_value = "chrome"
    other_proc.cmdline.return_value = ["chrome", "--user-data-dir=/tmp/chrome/other"]

    current_process = unittest.mock.MagicMock()
    current_process.children.return_value = [profile_proc, other_proc]

    with (
        unittest.mock.patch("psutil.Process", side_effect=[chromedriver, current_process]),
        unittest.mock.patch("psutil.process_iter", return_value=[profile_proc, other_proc]),
        unittest.mock.patch("os.getpid", return_value=999),
    ):
        assert my_lib.memory_util.find_browser_related_pids(profile) == {50, 51, 52}
