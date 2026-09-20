"""find / find_all が生成した ElementHandle の寿命管理。

Playwright の ElementHandle は、明示的な dispose()・親（Page/Context）の破棄・
接続全体で 10 万個を超えたときの GC のいずれかでしか解放されない。ナビゲーションでは
解放されないため、同じページを長期間使い回すクローラーでは node ドライバと Python の
双方にハンドルが溜まり続け、全操作が時間とともに遅くなる（price-watch で 1 巡回が
40 分 → 120 分に劣化した実障害）。

このモジュールは、ページごとに生成したハンドルを台帳で管理し、次の 2 つのタイミングで
dispose する。

1. ラッパー（PatchrightElement）が GC されたとき: 生ハンドルを「破棄待ち」に移し、
   次の find / find_all / goto の呼び出し時にまとめて dispose する。
2. ナビゲーション（goto / refresh）の直前: 台帳にある全ハンドルを dispose する。

NOTE: weakref のコールバック内では Playwright を呼ばない。Playwright の sync API は
      再入不可で、GC が別 greenlet の途中で走ると壊れる。コールバックはリストへの
      移動だけ行い、実際の dispose() は通常の呼び出し経路（flush）からのみ実行する。
"""

from __future__ import annotations

import contextlib
import itertools
import threading
import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from patchright.sync_api import ElementHandle as PwElementHandle
    from patchright.sync_api import Page as PwPage

_page_registries: weakref.WeakKeyDictionary[PwPage, HandleRegistry] = weakref.WeakKeyDictionary()
_page_registries_lock = threading.Lock()


def registry_for(pw_page: PwPage) -> HandleRegistry:
    """Playwright Page に紐づく台帳を返す（同じ Page には常に同じ台帳）。

    PatchrightPage ラッパーは Frame スコープ等で複数生成され得るため、台帳は
    ラッパーではなく生の Page に紐づける。Page が解放されれば台帳も解放される。
    """
    with _page_registries_lock:
        registry = _page_registries.get(pw_page)
        if registry is None:
            registry = HandleRegistry()
            _page_registries[pw_page] = registry
        return registry


class HandleRegistry:
    """1 ページ配下の ElementHandle の台帳。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: dict[int, PwElementHandle] = {}
        self._refs: dict[int, weakref.ref[object]] = {}
        self._pending: list[PwElementHandle] = []
        self._keys = itertools.count()

    def register(self, wrapper: object, handle: PwElementHandle) -> None:
        """ラッパーとハンドルを登録する。ラッパーが GC されたら破棄待ちに移す。"""
        key = next(self._keys)
        ref = weakref.ref(wrapper, self._make_callback(key))
        with self._lock:
            self._live[key] = handle
            self._refs[key] = ref

    def _make_callback(self, key: int) -> Callable[[weakref.ref[object]], None]:
        def on_collected(_: weakref.ref[object]) -> None:
            self._on_collected(key)

        return on_collected

    def _on_collected(self, key: int) -> None:
        # GC コールバック: Playwright は呼ばず、破棄待ちへ移すだけ。
        with self._lock:
            handle = self._live.pop(key, None)
            self._refs.pop(key, None)
            if handle is not None:
                self._pending.append(handle)

    def flush(self) -> None:
        """破棄待ちのハンドルを dispose する。通常の呼び出し経路からのみ呼ぶ。"""
        with self._lock:
            pending, self._pending = self._pending, []
        for handle in pending:
            # NOTE: ページが閉じられた後やサーバー側 GC で既に破棄済みの場合は失敗するが、
            #       解放が目的なので無視してよい。
            with contextlib.suppress(Exception):
                handle.dispose()

    def dispose_all(self) -> None:
        """台帳にある全ハンドルを dispose する（ナビゲーション直前に呼ぶ）。"""
        with self._lock:
            self._pending.extend(self._live.values())
            self._live.clear()
            self._refs.clear()
        self.flush()

    @property
    def live_count(self) -> int:
        """ラッパーが生存中のハンドル数（テスト・診断用）。"""
        with self._lock:
            return len(self._live)

    @property
    def pending_count(self) -> int:
        """破棄待ちのハンドル数（テスト・診断用）。"""
        with self._lock:
            return len(self._pending)
