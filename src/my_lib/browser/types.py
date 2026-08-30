"""ブラウザ抽象層の純粋な設定・値オブジェクト。

バックエンド固有の型を一切含まない dataclass / enum のみを置く。
"""

from __future__ import annotations

import dataclasses
import enum
import pathlib


class BrowserBackend(enum.Enum):
    """利用するブラウザバックエンド。"""

    PATCHRIGHT = "patchright"
    SELENIUM = "selenium"


@dataclasses.dataclass(frozen=True)
class Viewport:
    """ビューポートサイズ。"""

    width: int = 1920
    height: int = 1080


@dataclasses.dataclass(frozen=True)
class BrowserProfile:
    """ブラウザ生成時の設定。

    UA / locale / device_scale_factor といった、旧実装で ``execute_cdp_cmd`` により
    後付けしていた項目を、生成時オプションとしてここに集約する
    （Patchright/Playwright はコンテキスト生成時に確定させる作法のため）。

    Attributes:
        name: プロファイル名（データディレクトリのサブディレクトリ名にも使う）。
        data_dir: プロファイル永続化のルートディレクトリ。
        headless: ヘッドレス起動するか。bot 検出回避のため既定は False（Xvfb 上の headful を想定）。
        locale: ブラウザロケール（例: "ja-JP"）。
        user_agent: UA を明示指定する場合。None なら実ブラウザの UA を使う。
        viewport: ビューポートサイズ。
        device_scale_factor: 論理ピクセル比（Retina スクショ等で 2 を指定）。
        stealth: 自動化痕跡の除去を有効にするか（Patchright バックエンドでは常時有効相当）。
        chrome_path: 使用する Chrome 実行ファイル。None ならバックエンド既定。

    """

    name: str
    data_dir: pathlib.Path
    headless: bool = False
    locale: str = "ja-JP"
    user_agent: str | None = None
    viewport: Viewport = dataclasses.field(default_factory=Viewport)
    device_scale_factor: float = 1.0
    stealth: bool = True
    chrome_path: str | None = None


@dataclasses.dataclass(frozen=True)
class ScreenshotSpec:
    """スクリーンショット取得の指定。

    Attributes:
        full_page: ページ全体を撮るか（False なら現在のビューポート）。

    """

    full_page: bool = False
