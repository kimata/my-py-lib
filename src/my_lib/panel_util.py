#!/usr/bin/env python3
import logging
import textwrap
import time
import traceback

import my_lib.notify_slack
import my_lib.pil_util
import PIL.Image
import PIL.ImageDraw


def notify_error(config, message):
    logging.error(message)

    if "slack" not in config:
        return

    my_lib.notify_slack.error(
        config["slack"]["bot_token"],
        config["slack"]["error"]["channel"]["name"],
        config["slack"]["from"],
        message,
        config["slack"]["error"]["interval_min"],
    )


def create_error_image(panel_config, font_config, message):
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
    func, panel_config, font_config, slack_config, is_side_by_side, opt_config=None, error_image=True
):
    RETRY_COUNT = 5
    start = time.perf_counter()

    error_message = None
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
