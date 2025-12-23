#!/usr/bin/env python3
from __future__ import annotations

import logging
import textwrap
import time
import traceback
from collections.abc import Callable
from typing import Any

import PIL.Image
import PIL.ImageDraw

import my_lib.notify.slack
import my_lib.pil_util


def notify_error(config: dict[str, Any], message: str) -> None:
    logging.error(message)

    if "slack" not in config:
        return

    slack_config = my_lib.notify.slack.parse_config(config["slack"])
    if isinstance(
        slack_config,
        (
            my_lib.notify.slack.SlackConfig,
            my_lib.notify.slack.SlackErrorInfoConfig,
            my_lib.notify.slack.SlackErrorOnlyConfig,
        ),
    ):
        my_lib.notify.slack.error(slack_config, config["slack"]["from"], message)


def create_error_image(
    panel_config: dict[str, Any], font_config: dict[str, Any], message: str
) -> PIL.Image.Image:
    img = PIL.Image.new(
        "RGBA",
        (panel_config["panel"]["width"], panel_config["panel"]["height"]),
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

    next_pos_y = 110
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


def draw_panel_patiently(  # noqa: PLR0913
    func: Callable[..., PIL.Image.Image],
    panel_config: dict[str, Any],
    font_config: dict[str, Any],
    slack_config: dict[str, Any] | None,
    is_side_by_side: bool,
    opt_config: dict[str, Any] | None = None,
    error_image: bool = True,
) -> tuple[PIL.Image.Image, float] | tuple[PIL.Image.Image, float, str | None]:
    RETRY_COUNT = 5
    start = time.perf_counter()

    error_message: str = "Unknown error"
    for i in range(RETRY_COUNT):
        try:
            return (
                func(panel_config, font_config, slack_config, is_side_by_side, i + 1, opt_config),
                time.perf_counter() - start,
            )
        except Exception:
            error_message = traceback.format_exc()
            logging.exception("Failed to draw panel")

        logging.warning("Retry %d time(s)", i + 1)
        time.sleep(2)

    return (
        create_error_image(panel_config, font_config, error_message)
        if error_image
        else PIL.Image.new(
            "RGBA",
            (panel_config["panel"]["width"], panel_config["panel"]["height"]),
            (255, 255, 255, 100),
        ),
        time.perf_counter() - start,
        error_message,
    )
