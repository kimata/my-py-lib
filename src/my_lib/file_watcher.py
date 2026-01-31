#!/usr/bin/env python3
"""ファイル変更監視モジュール.

watchdog を使用してファイルの変更を監視し、コールバックを実行します。
アトミック書き込み（tmp → rename）にも対応しています。
"""

from __future__ import annotations

import logging
import pathlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver


@dataclass
class _WatchEntry:
    """監視エントリ."""

    path: pathlib.Path
    on_change: Callable[[], None]
    debounce_sec: float
    last_triggered: float = field(default=0.0)
    pending_timer: threading.Timer | None = field(default=None)
    lock: threading.Lock = field(default_factory=threading.Lock)


class _EventHandler(FileSystemEventHandler):
    """ファイルシステムイベントハンドラ."""

    def __init__(self, watcher: FileWatcher) -> None:
        super().__init__()
        self._watcher = watcher

    def _handle_event(self, event: FileSystemEvent) -> None:
        """イベントを処理."""
        if event.is_directory:
            return

        # 移動イベントの場合は移動先のパスを使用
        if hasattr(event, "dest_path") and event.dest_path:
            event_path = pathlib.Path(str(event.dest_path)).resolve()
        else:
            event_path = pathlib.Path(str(event.src_path)).resolve()

        self._watcher._trigger_if_watched(event_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """ファイルが変更された時."""
        self._handle_event(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        """ファイルが移動/リネームされた時（アトミック書き込み対応）."""
        self._handle_event(event)

    def on_created(self, event: FileSystemEvent) -> None:
        """ファイルが作成された時."""
        self._handle_event(event)


class FileWatcher:
    """ファイル変更監視.

    複数のファイルを監視し、変更があった場合にコールバックを実行します。
    デバウンス機能により、短時間の連続したイベントをまとめて処理します。

    使用例:
        watcher = FileWatcher()
        watcher.watch(
            path=Path("config.yaml"),
            on_change=lambda: print("config changed"),
            debounce_sec=0.5,
        )
        watcher.start()

        # ... アプリケーション処理 ...

        watcher.stop()

    コンテキストマネージャとしても使用可能:
        with FileWatcher() as watcher:
            watcher.watch(path, on_change)
            # ... アプリケーション処理 ...
    """

    def __init__(self) -> None:
        """初期化."""
        self._entries: dict[pathlib.Path, _WatchEntry] = {}
        self._observer: BaseObserver | None = None
        self._handler = _EventHandler(self)
        self._lock = threading.Lock()
        self._started = False
        self._watched_dirs: set[pathlib.Path] = set()

    def watch(
        self,
        path: pathlib.Path,
        on_change: Callable[[], None],
        debounce_sec: float = 0.5,
    ) -> None:
        """ファイルを監視対象に追加.

        Args:
            path: 監視対象のファイルパス
            on_change: ファイル変更時に呼び出されるコールバック
            debounce_sec: デバウンス時間（秒）。この時間内の連続したイベントは
                         1回のコールバック呼び出しにまとめられます。
        """
        resolved_path = path.resolve()
        parent_dir = resolved_path.parent

        with self._lock:
            self._entries[resolved_path] = _WatchEntry(
                path=resolved_path,
                on_change=on_change,
                debounce_sec=debounce_sec,
            )

            # Observer が開始済みの場合、新しいディレクトリを監視に追加
            if self._started and parent_dir not in self._watched_dirs:
                self._add_watch_dir(parent_dir)

    def unwatch(self, path: pathlib.Path) -> None:
        """ファイルを監視対象から削除.

        Args:
            path: 監視対象から削除するファイルパス
        """
        resolved_path = path.resolve()

        with self._lock:
            entry = self._entries.pop(resolved_path, None)
            if entry and entry.pending_timer:
                entry.pending_timer.cancel()

    def start(self) -> None:
        """監視を開始."""
        with self._lock:
            if self._started:
                return

            self._observer = Observer()

            # 監視対象ファイルの親ディレクトリを監視
            for entry in self._entries.values():
                parent_dir = entry.path.parent
                self._add_watch_dir(parent_dir)

            observer = self._observer
            observer.start()
            self._started = True
            logging.debug("FileWatcher started")

    def stop(self) -> None:
        """監視を停止."""
        with self._lock:
            if not self._started or self._observer is None:
                return

            # 保留中のタイマーをすべてキャンセル
            for entry in self._entries.values():
                if entry.pending_timer:
                    entry.pending_timer.cancel()
                    entry.pending_timer = None

            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None
            self._started = False
            self._watched_dirs.clear()
            logging.debug("FileWatcher stopped")

    def _add_watch_dir(self, directory: pathlib.Path) -> None:
        """ディレクトリを監視対象に追加（内部メソッド）."""
        if directory in self._watched_dirs:
            return

        if self._observer is None:
            return

        self._observer.schedule(self._handler, str(directory), recursive=False)
        self._watched_dirs.add(directory)
        logging.debug("Watching directory: %s", directory)

    def _trigger_if_watched(self, event_path: pathlib.Path) -> None:
        """監視対象のファイルであればコールバックをトリガー（内部メソッド）."""
        with self._lock:
            entry = self._entries.get(event_path)
            if entry is None:
                return

        self._schedule_callback(entry)

    def _schedule_callback(self, entry: _WatchEntry) -> None:
        """デバウンス付きでコールバックをスケジュール（内部メソッド）."""
        with entry.lock:
            # 既存のタイマーがあればキャンセル
            if entry.pending_timer:
                entry.pending_timer.cancel()
                entry.pending_timer = None

            # デバウンス時間後にコールバックを実行
            def execute_callback() -> None:
                with entry.lock:
                    entry.pending_timer = None
                    entry.last_triggered = time.time()

                logging.debug("File changed: %s", entry.path)
                try:
                    entry.on_change()
                except Exception:
                    logging.exception("Error in file change callback for %s", entry.path)

            entry.pending_timer = threading.Timer(entry.debounce_sec, execute_callback)
            entry.pending_timer.daemon = True
            entry.pending_timer.start()

    def __enter__(self) -> FileWatcher:
        """コンテキストマネージャ開始."""
        self.start()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: object,
    ) -> None:
        """コンテキストマネージャ終了."""
        self.stop()
