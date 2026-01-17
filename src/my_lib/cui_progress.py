"""Rich を使用した CUI プログレス表示モジュール

TTY 環境では Rich による視覚的なプログレス表示を行い、
非 TTY 環境（CI/CD パイプラインなど）では logging にフォールバックします。
Null Object パターンを使用して TTY/非TTY 分岐をシンプルにしています。

Examples:
    基本的な使用方法::

        import my_lib.cui_progress

        progress = my_lib.cui_progress.ProgressManager(
            color="#E72121",
            title=" 🛒メルカリ ",
        )
        progress.start()
        try:
            progress.set_status("ログイン中...")
            # ... ログイン処理 ...

            progress.set_progress_bar("アイテム処理", total=100)
            for i in range(100):
                progress.update_progress_bar("アイテム処理")

            progress.set_status("完了")
        finally:
            progress.stop()

    ユーザー入力時の一時停止::

        progress.pause_live()
        answer = input("続行しますか? ")
        progress.resume_live()
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any, ClassVar

import rich.console
import rich.live
import rich.progress
import rich.table
import rich.text

if TYPE_CHECKING:
    pass


class _NullProgress:
    """非TTY環境用の何もしない Progress（Null Object パターン）"""

    tasks: ClassVar[list[rich.progress.Task]] = []

    def add_task(self, description: str, total: float | None = None) -> rich.progress.TaskID:
        return rich.progress.TaskID(0)

    def update(self, task_id: rich.progress.TaskID, advance: float = 1) -> None:
        pass

    def remove_task(self, task_id: rich.progress.TaskID) -> None:
        pass

    def __rich__(self) -> rich.text.Text:
        """Rich プロトコル対応（空のテキストを返す）"""
        return rich.text.Text("")


class _NullLive:
    """非TTY環境用の何もしない Live（Null Object パターン）"""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def refresh(self) -> None:
        pass


class ProgressTask:
    """Rich Progress のタスクを管理するクラス"""

    def __init__(
        self,
        manager: ProgressManager,
        task_id: rich.progress.TaskID,
        total: int,
    ) -> None:
        self._manager = manager
        self._task_id = task_id
        self._total = total
        self._count = 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def count(self) -> int:
        return self._count

    @property
    def task_id(self) -> rich.progress.TaskID:
        return self._task_id

    def update(self, advance: int = 1) -> None:
        """プログレスを進める"""
        self._count += advance
        self._manager._progress.update(self._task_id, advance=advance)
        self._manager._refresh_display()


class _DisplayRenderable:
    """Live 表示用の動的 renderable クラス"""

    def __init__(self, manager: ProgressManager) -> None:
        self._manager = manager

    def __rich__(self) -> Any:
        """Rich が描画時に呼び出すメソッド"""
        return self._manager._create_display()


class ProgressManager:
    """プログレス表示を管理するクラス

    TTY 環境では Rich による視覚的なプログレスバーとステータスバーを表示し、
    非 TTY 環境では logging にフォールバックします。

    Args:
        console: Rich Console インスタンス（省略時は新規作成）
        color: ステータスバーの背景色（CSS カラー形式）
        title: ステータスバーの左端に表示するタイトル
        description_width: プログレスバーの説明列の幅
        show_remaining_time: 残り時間を表示するかどうか
        auto_start: 初期化時に自動的に Live 表示を開始するかどうか
    """

    def __init__(
        self,
        *,
        console: rich.console.Console | None = None,
        color: str = "#6366F1",
        title: str = "",
        description_width: int = 31,
        show_remaining_time: bool = True,
        auto_start: bool = True,
    ) -> None:
        self._console = console if console is not None else rich.console.Console()
        self._color = color
        self._title = title
        self._description_width = description_width
        self._show_remaining_time = show_remaining_time

        # スタイル定義
        self._status_style_normal = f"bold #FFFFFF on {color}"
        self._status_style_error = "bold white on red"

        # 内部状態
        self._progress: rich.progress.Progress | _NullProgress = _NullProgress()
        self._live: rich.live.Live | _NullLive = _NullLive()
        self._start_time: float = time.time()
        self._status_text: str = ""
        self._status_is_error: bool = False
        self._display_renderable: _DisplayRenderable | None = None
        self._progress_bar: dict[str, ProgressTask] = {}
        self._initialized: bool = False

        if auto_start:
            self._init_progress()
            self._live.start()

    @property
    def console(self) -> rich.console.Console:
        """Console インスタンスを取得"""
        return self._console

    @property
    def is_terminal(self) -> bool:
        """TTY 環境かどうか"""
        return self._console.is_terminal

    def _init_progress(self) -> None:
        """Progress と Live を初期化"""
        if self._initialized:
            return

        # 非TTY環境では Live を使用しない
        if not self._console.is_terminal:
            self._initialized = True
            return

        # プログレスバーのカラム構築
        columns: list[rich.progress.ProgressColumn] = [
            rich.progress.TextColumn(f"[bold]{{task.description:<{self._description_width}}}"),
            rich.progress.BarColumn(bar_width=None),
            rich.progress.TaskProgressColumn(),
            rich.progress.TextColumn("{task.completed:>5} / {task.total:<5}"),
            rich.progress.TextColumn("経過:"),
            rich.progress.TimeElapsedColumn(),
        ]

        if self._show_remaining_time:
            columns.extend(
                [
                    rich.progress.TextColumn("残り:"),
                    rich.progress.TimeRemainingColumn(),
                ]
            )

        self._progress = rich.progress.Progress(
            *columns,
            console=self._console,
            expand=True,
        )
        self._start_time = time.time()
        self._display_renderable = _DisplayRenderable(self)
        self._live = rich.live.Live(
            self._display_renderable,
            console=self._console,
            refresh_per_second=4,
        )
        self._initialized = True

    def start(self) -> None:
        """Live 表示を開始"""
        if not self._initialized:
            self._init_progress()
        self._live.start()

    def stop(self) -> None:
        """Live 表示を停止"""
        self._live.stop()

    def pause_live(self) -> None:
        """Live 表示を一時停止（input() の前に呼び出す）"""
        self._live.stop()

    def resume_live(self) -> None:
        """Live 表示を再開（input() の後に呼び出す）"""
        self._live.start()

    def _create_status_bar(self) -> rich.table.Table:
        """ステータスバーを作成（左: タイトル、中央: 進捗、右: 時間）"""
        style = self._status_style_error if self._status_is_error else self._status_style_normal
        elapsed = time.time() - self._start_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

        # ターミナル幅を取得し、明示的に幅を制限
        # NOTE: tmux 環境では幅計算が実際と異なることがあるため、余裕を持たせる
        terminal_width = self._console.width
        if os.environ.get("TMUX"):
            terminal_width -= 1

        table = rich.table.Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=0,
            expand=False,
            width=terminal_width,
            style=style,
        )
        table.add_column("title", justify="left", ratio=1, no_wrap=True, overflow="ellipsis", style=style)
        table.add_column("status", justify="center", ratio=3, no_wrap=True, overflow="ellipsis", style=style)
        table.add_column("time", justify="right", ratio=1, no_wrap=True, overflow="ellipsis", style=style)

        table.add_row(
            rich.text.Text(self._title, style=style) if self._title else rich.text.Text("", style=style),
            rich.text.Text(self._status_text, style=style),
            rich.text.Text(f" {elapsed_str} ", style=style),
        )

        return table

    def _create_display(self) -> Any:
        """表示内容を作成"""
        status_bar = self._create_status_bar()
        # NullProgress の場合 tasks は常に空なのでこの条件で十分
        if len(self._progress.tasks) > 0:
            return rich.console.Group(status_bar, self._progress)
        return status_bar

    def _refresh_display(self) -> None:
        """表示を強制的に再描画"""
        self._live.refresh()

    def set_progress_bar(self, desc: str, total: int) -> None:
        """プログレスバーを作成

        Args:
            desc: プログレスバーの説明（辞書のキーとしても使用）
            total: 総数
        """
        task_id = self._progress.add_task(desc, total=total)
        self._progress_bar[desc] = ProgressTask(self, task_id, total)
        self._refresh_display()

    def update_progress_bar(self, desc: str, advance: int = 1) -> None:
        """プログレスバーを進める

        Args:
            desc: プログレスバーの説明（キー）
            advance: 進める量（デフォルト: 1）

        Note:
            存在しないキーの場合は何もしない
        """
        if desc in self._progress_bar:
            self._progress_bar[desc].update(advance)

    def remove_progress_bar(self, desc: str) -> None:
        """プログレスバーを削除

        Args:
            desc: プログレスバーの説明（キー）

        Note:
            存在しないキーの場合は何もしない
        """
        if desc in self._progress_bar:
            task = self._progress_bar.pop(desc)
            self._progress.remove_task(task.task_id)
            self._refresh_display()

    def has_progress_bar(self, desc: str) -> bool:
        """プログレスバーが存在するか確認

        Args:
            desc: プログレスバーの説明（キー）

        Returns:
            存在する場合は True
        """
        return desc in self._progress_bar

    def get_progress_bar(self, desc: str) -> ProgressTask:
        """プログレスバーを取得

        Args:
            desc: プログレスバーの説明（キー）

        Returns:
            ProgressTask インスタンス

        Raises:
            KeyError: 存在しないキーの場合
        """
        return self._progress_bar[desc]

    def set_status(self, status: str, *, is_error: bool = False) -> None:
        """ステータスを更新

        Args:
            status: 表示するステータステキスト
            is_error: エラー状態かどうか（True の場合、赤背景で表示）

        Note:
            非 TTY 環境では logging で出力
        """
        self._status_text = status
        self._status_is_error = is_error

        # 非TTY環境では logging で出力
        if not self._console.is_terminal:
            if is_error:
                logging.error(status)
            else:
                logging.info(status)
            return

        self._refresh_display()

    def print(self, *args: Any, **kwargs: Any) -> None:
        """コンソールに出力（非TTY環境でのみ使用）

        Args:
            *args: print に渡す引数
            **kwargs: print に渡すキーワード引数
        """
        if not self._console.is_terminal:
            self._console.print(*args, **kwargs)


class NullProgressManager:
    """何もしない ProgressManager（Null Object パターン）

    ProgressManager | None の代わりに使用することで、
    呼び出し側での None チェックを不要にします。

    Examples:
        使用例::

            # Before: None チェックが必要
            progress: ProgressManager | None = None
            if progress:
                progress.set_status("処理中...")

            # After: チェック不要
            progress: ProgressManager | NullProgressManager = NullProgressManager()
            progress.set_status("処理中...")  # 何もしない
    """

    def __init__(
        self,
        *,
        console: rich.console.Console | None = None,
        **_kwargs: Any,
    ) -> None:
        self._console = console if console is not None else rich.console.Console()
        self._start_time: float = time.time()

    @property
    def console(self) -> rich.console.Console:
        """Console インスタンスを取得"""
        return self._console

    @property
    def is_terminal(self) -> bool:
        """TTY 環境かどうか（常に False）"""
        return False

    def start(self) -> None:
        """何もしない"""

    def stop(self) -> None:
        """何もしない"""

    def pause_live(self) -> None:
        """何もしない"""

    def resume_live(self) -> None:
        """何もしない"""

    def set_progress_bar(self, _desc: str, _total: int) -> None:
        """何もしない"""

    def update_progress_bar(self, _desc: str, _advance: int = 1) -> None:
        """何もしない"""

    def remove_progress_bar(self, _desc: str) -> None:
        """何もしない"""

    def has_progress_bar(self, _desc: str) -> bool:
        """常に False を返す"""
        return False

    def set_status(self, _status: str, *, is_error: bool = False) -> None:
        """何もしない"""

    def print(self, *args: Any, **kwargs: Any) -> None:
        """コンソールに出力（Live 表示がないため常に出力）"""
        self._console.print(*args, **kwargs)
