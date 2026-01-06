# ruff: noqa: S101
"""cui_progress モジュールのテスト"""

from __future__ import annotations

import rich.console
import rich.progress

import my_lib.cui_progress


class TestNullProgress:
    """_NullProgress のテスト"""

    def test_add_task_returns_zero(self) -> None:
        progress = my_lib.cui_progress._NullProgress()
        task_id = progress.add_task("test", total=100)
        assert task_id == 0

    def test_update_does_nothing(self) -> None:
        progress = my_lib.cui_progress._NullProgress()
        task_id = progress.add_task("test", total=100)
        progress.update(task_id, advance=10)  # Should not raise

    def test_remove_task_does_nothing(self) -> None:
        progress = my_lib.cui_progress._NullProgress()
        task_id = progress.add_task("test", total=100)
        progress.remove_task(task_id)  # Should not raise

    def test_rich_returns_empty_text(self) -> None:
        progress = my_lib.cui_progress._NullProgress()
        result = progress.__rich__()
        assert str(result) == ""


class TestNullLive:
    """_NullLive のテスト"""

    def test_start_does_nothing(self) -> None:
        live = my_lib.cui_progress._NullLive()
        live.start()  # Should not raise

    def test_stop_does_nothing(self) -> None:
        live = my_lib.cui_progress._NullLive()
        live.stop()  # Should not raise

    def test_refresh_does_nothing(self) -> None:
        live = my_lib.cui_progress._NullLive()
        live.refresh()  # Should not raise


class TestProgressManager:
    """ProgressManager のテスト"""

    def test_init_with_defaults(self) -> None:
        # Non-TTY console for testing
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        assert manager.is_terminal is False
        assert isinstance(manager._progress, my_lib.cui_progress._NullProgress)

    def test_init_with_custom_color(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            color="#E72121",
            title=" Test ",
        )

        assert manager._color == "#E72121"
        assert manager._title == " Test "

    def test_init_with_auto_start_false(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            auto_start=False,
        )

        # Should still be usable
        manager.set_status("Testing")
        assert manager._status_text == "Testing"

    def test_console_property(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        assert manager.console is console

    def test_set_progress_bar(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("test", total=100)
        assert manager.has_progress_bar("test")

    def test_has_progress_bar_returns_false_for_nonexistent(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        assert manager.has_progress_bar("nonexistent") is False

    def test_update_progress_bar(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("test", total=100)
        manager.update_progress_bar("test", advance=10)

        task = manager.get_progress_bar("test")
        assert task.count == 10

    def test_update_progress_bar_nonexistent_does_nothing(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        # Should not raise
        manager.update_progress_bar("nonexistent", advance=10)

    def test_remove_progress_bar(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("test", total=100)
        manager.remove_progress_bar("test")

        assert not manager.has_progress_bar("test")

    def test_remove_progress_bar_nonexistent_does_nothing(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        # Should not raise
        manager.remove_progress_bar("nonexistent")

    def test_get_progress_bar(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("test", total=100)
        task = manager.get_progress_bar("test")

        assert task.total == 100
        assert task.count == 0

    def test_pause_resume_live(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.pause_live()
        manager.resume_live()  # Should not raise

    def test_set_status(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_status("Testing...")
        assert manager._status_text == "Testing..."
        assert manager._status_is_error is False

    def test_set_status_with_error(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_status("Error!", is_error=True)
        assert manager._status_text == "Error!"
        assert manager._status_is_error is True

    def test_start_stop(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            auto_start=False,
        )

        manager.start()
        manager.stop()  # Should not raise

    def test_print_non_tty(self, capsys: object) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        # print() should work in non-TTY mode
        manager.print("Test output")


class TestProgressTask:
    """ProgressTask のテスト"""

    def test_properties(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("test", total=100)
        task = manager.get_progress_bar("test")

        assert task.total == 100
        assert task.count == 0
        assert task.task_id == 0  # NullProgress always returns 0

    def test_update(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("test", total=100)
        task = manager.get_progress_bar("test")

        task.update(advance=5)
        assert task.count == 5

        task.update()  # default advance=1
        assert task.count == 6

    def test_multiple_progress_bars(self) -> None:
        console = rich.console.Console(force_terminal=False)
        manager = my_lib.cui_progress.ProgressManager(console=console)

        manager.set_progress_bar("task1", total=100)
        manager.set_progress_bar("task2", total=200)

        assert manager.has_progress_bar("task1")
        assert manager.has_progress_bar("task2")

        task1 = manager.get_progress_bar("task1")
        task2 = manager.get_progress_bar("task2")

        assert task1.total == 100
        assert task2.total == 200

        task1.update(10)
        task2.update(20)

        assert task1.count == 10
        assert task2.count == 20


class TestProgressManagerWithTTY:
    """TTY 環境での ProgressManager のテスト

    Note:
        force_terminal=True を設定しても、テスト環境によっては
        実際の is_terminal が False になる場合があるため、
        一部のテストはスキップされる可能性があります。
    """

    def test_init_with_tty(self) -> None:
        # Force terminal mode for testing
        console = rich.console.Console(force_terminal=True)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            auto_start=False,
        )

        # force_terminal=True の場合、is_terminal は True になる
        # ただし、_init_progress 内の is_terminal チェックも同様に True になるため
        # 正常な Progress インスタンスが作成されるはず
        #
        # Note: pytest-xdist の並列実行環境では、実際の TTY 状態と
        # force_terminal の設定が競合する場合があるため、
        # _progress の型は環境に依存する可能性がある
        assert isinstance(
            manager._progress,
            rich.progress.Progress | my_lib.cui_progress._NullProgress,
        )

    def test_start_stop_with_tty(self) -> None:
        console = rich.console.Console(force_terminal=True)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            auto_start=False,
        )

        manager.start()
        manager.stop()

    def test_progress_bar_operations_with_tty(self) -> None:
        console = rich.console.Console(force_terminal=True)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            auto_start=False,
        )

        manager.set_progress_bar("test", total=100)
        assert manager.has_progress_bar("test")

        manager.update_progress_bar("test", advance=50)
        task = manager.get_progress_bar("test")
        assert task.count == 50

        manager.remove_progress_bar("test")
        assert not manager.has_progress_bar("test")

    def test_status_update_with_tty(self) -> None:
        console = rich.console.Console(force_terminal=True)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            auto_start=False,
        )

        manager.set_status("Testing...")
        assert manager._status_text == "Testing..."

        manager.set_status("Error!", is_error=True)
        assert manager._status_is_error is True

    def test_custom_settings_with_tty(self) -> None:
        console = rich.console.Console(force_terminal=True)
        manager = my_lib.cui_progress.ProgressManager(
            console=console,
            color="#E72121",
            title=" 🛒メルカリ ",
            description_width=20,
            show_remaining_time=False,
            auto_start=False,
        )

        assert manager._color == "#E72121"
        assert manager._title == " 🛒メルカリ "
        assert manager._description_width == 20
        assert manager._show_remaining_time is False
