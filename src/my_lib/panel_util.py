#!/usr/bin/env python3
from __future__ import annotations

import logging
import textwrap
import time
import traceback
from collections.abc import Callable
from typing import TypeVar

import PIL.Image
import PIL.ImageDraw

import my_lib.notify.slack
import my_lib.panel_config
import my_lib.pil_util

# Panel描画関数のオプション設定用TypeVar
OptConfigT = TypeVar("OptConfigT")


def notify_error(
    slack_config: my_lib.notify.slack.HasErrorConfig | my_lib.notify.slack.SlackEmptyConfig,
    from_name: str,
    message: str,
) -> None:
    """エラーを Slack に通知する

    Args:
        slack_config: Slack 設定 (SlackErrorProtocol を満たす、または SlackEmptyConfig)
        from_name: 送信元の名前
        message: エラーメッセージ
    """
    logging.error(message)
    my_lib.notify.slack.error(slack_config, from_name, message)


def create_error_image(
    panel_config: my_lib.panel_config.PanelConfigProtocol,
    font_config: my_lib.panel_config.FontConfigProtocol,
    message: str,
) -> PIL.Image.Image:
    """エラー画像を生成する

    Args:
        panel_config: パネル設定 (panel.width, panel.height を持つ)
        font_config: フォント設定
        message: エラーメッセージ

    Returns:
        エラー画像
    """
    img = PIL.Image.new(
        "RGBA",
        (panel_config.panel.width, panel_config.panel.height),
        (255, 255, 255, 100),
    )
    my_lib.pil_util.draw_text(
        img,
        "ERROR",
        (10, 10),
        my_lib.pil_util.get_font(font_config, "en_bold", 100),
        "left",
        "#666",
    )

    next_pos_y: float = 110
    for line in textwrap.wrap(message, 90):
        next_pos_y = (
            my_lib.pil_util.draw_text(
                img,
                line,
                (20, next_pos_y),
                my_lib.pil_util.get_font(font_config, "en_medium", 30),
                "left",
                "#666",
            )[1]
            + 10
        )

    return img


def draw_panel_patiently(
    func: Callable[
        [
            my_lib.panel_config.PanelConfigProtocol,
            my_lib.panel_config.NormalPanelContext,
            OptConfigT,
        ],
        PIL.Image.Image,
    ],
    panel_config: my_lib.panel_config.PanelConfigProtocol,
    context: my_lib.panel_config.NormalPanelContext,
    opt_config: OptConfigT = None,  # type: ignore[assignment]
    error_image: bool = True,
) -> tuple[PIL.Image.Image, float] | tuple[PIL.Image.Image, float, str]:
    """パネル描画を忍耐強くリトライする

    Args:
        func: パネル描画関数 (panel_config, context) -> Image
        panel_config: パネル設定
        context: パネルコンテキスト（font_config, slack_config, is_side_by_side を含む）
        opt_config: オプション設定
        error_image: エラー時にエラー画像を返すかどうか

    Returns:
        成功時: (画像, 経過時間)
        失敗時: (エラー画像, 経過時間, エラーメッセージ)
    """
    RETRY_COUNT = 5
    start = time.perf_counter()

    error_message: str = "Unknown error"
    for i in range(RETRY_COUNT):
        try:
            # trial を更新したコンテキストを作成
            trial_context = my_lib.panel_config.NormalPanelContext(
                font_config=context.font_config,
                slack_config=context.slack_config,
                is_side_by_side=context.is_side_by_side,
                trial=i + 1,
            )
            return (
                func(panel_config, trial_context, opt_config),
                time.perf_counter() - start,
            )
        except Exception:
            error_message = traceback.format_exc()
            logging.exception("Failed to draw panel")

        logging.warning("Retry %d time(s)", i + 1)
        time.sleep(2)

    if error_image:
        return (
            create_error_image(panel_config, context.font_config, error_message),
            time.perf_counter() - start,
            error_message,
        )
    else:
        return (
            PIL.Image.new(
                "RGBA",
                (panel_config.panel.width, panel_config.panel.height),
                (255, 255, 255, 100),
            ),
            time.perf_counter() - start,
            error_message,
        )
