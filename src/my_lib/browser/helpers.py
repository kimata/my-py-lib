"""ブラウザ抽象層の意味ベースユーティリティ。

`Page` の上に、旧 `selenium_util` のヘルパー（dump_page 等）に相当する
バックエンド非依存の関数を提供する。
"""

from __future__ import annotations

import datetime
import inspect
import logging
import pathlib

from my_lib.browser.protocol import Page


def dump_page(page: Page, index: int, dump_path: pathlib.Path, *, prefix: str | None = None) -> None:
    """ページの HTML とスクリーンショットをダンプする。

    Args:
        page: 対象ページ。
        index: 連番（ファイル名に付与）。
        dump_path: 出力先ディレクトリ。
        prefix: ファイル名の接頭辞。None なら呼び出し元の関数名を使う。

    """
    if prefix is None:
        prefix = inspect.stack()[1].function.replace("<", "").replace(">", "")

    dump_path.mkdir(parents=True, exist_ok=True)

    png_path = dump_path / f"{prefix}_{index:02d}.png"
    htm_path = dump_path / f"{prefix}_{index:02d}.htm"

    png_path.write_bytes(page.screenshot())
    htm_path.write_text(page.content, encoding="utf-8")

    caller = inspect.stack()[1]
    logging.info(
        "page dump: %02d from %s in %s line %d", index, caller.function, caller.filename, caller.lineno
    )


def clean_dump(dump_path: pathlib.Path, keep_days: int = 1) -> None:
    """ダンプディレクトリから古いファイルを削除する（バックエンド非依存の FS 操作）。"""
    if not dump_path.exists():
        return

    time_threshold = datetime.timedelta(keep_days)

    for item in dump_path.iterdir():
        if not item.is_file():
            continue
        try:
            time_diff = datetime.datetime.now(datetime.UTC) - datetime.datetime.fromtimestamp(
                item.stat().st_mtime, datetime.UTC
            )
        except FileNotFoundError:
            # ファイルが別プロセスにより削除された場合（SQLite の一時ファイルなど）
            continue
        if time_diff > time_threshold:
            logging.warning("remove %s [%s day(s) old].", item.absolute(), f"{time_diff.days:,}")
            item.unlink(missing_ok=True)


def title_contains_js(text: str) -> str:
    """タイトルに指定文字列が含まれることを判定する JS 述語を返す（wait_until 用）。"""
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"() => document.title.includes('{escaped}')"
