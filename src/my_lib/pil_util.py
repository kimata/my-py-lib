#!/usr/bin/env python3
from __future__ import annotations

import logging
import pathlib
from typing import Any

import PIL.Image
import PIL.ImageDraw
import PIL.ImageEnhance
import PIL.ImageFont


def get_font(config: dict[str, Any], font_type: str, size: int) -> PIL.ImageFont.FreeTypeFont:
    font_path = pathlib.Path(config["path"]).resolve() / config["map"][font_type]

    if font_path not in get_font.loaded:  # type: ignore[attr-defined]
        logging.debug("Load font: %s", font_path)
        get_font.loaded[font_path] = True  # type: ignore[attr-defined]

    return PIL.ImageFont.truetype(font_path, size)


get_font.loaded: dict[pathlib.Path, bool] = {}  # type: ignore[attr-defined,misc]


def text_size(img: PIL.Image.Image, font: PIL.ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    left, top, right, bottom = PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)

    return (int(right - left), int(bottom - top))


def draw_text(  # noqa: PLR0913
    img: PIL.Image.Image,
    text: str,
    pos: tuple[int, int],
    font: PIL.ImageFont.FreeTypeFont,
    align: str = "left",
    color: str = "#000",
    stroke_width: int = 0,
    stroke_fill: str | None = None,
) -> tuple[int, int]:
    text_line_list = text.split("\n")

    pos_x, next_pos_y = pos
    next_pos_x = pos_x
    for text_line in text_line_list:
        next_pos = draw_text_line(
            img,
            text_line,
            (pos_x, next_pos_y),
            font,
            align,
            color,
            stroke_width,
            stroke_fill,
        )

        next_pos_x = max(next_pos[0], next_pos_x)
        next_pos_y = next_pos[1]

    return (next_pos_x, next_pos_y)


def draw_text_line(  # noqa: PLR0913
    img: PIL.Image.Image,
    text: str,
    pos: tuple[int, int],
    font: PIL.ImageFont.FreeTypeFont,
    align: str = "left",
    color: str = "#000",
    stroke_width: int = 0,
    stroke_fill: str | None = None,
) -> tuple[int, int]:
    draw = PIL.ImageDraw.Draw(img)

    draw_pos: tuple[int, int]
    if align == "center":
        draw_pos = (int(pos[0] - text_size(img, font, text)[0] / 2.0), int(pos[1]))
    elif align == "right":
        draw_pos = (int(pos[0] - text_size(img, font, text)[0]), int(pos[1]))
    else:
        draw_pos = pos

    # draw.rectangle(
    #     (pos[0], pos[1], pos[0] + 4, pos[1] + 4),
    #     fill="black",
    # )

    draw_pos = (draw_pos[0], int(draw_pos[1] - PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)[1]))

    draw.text(
        draw_pos,
        text,
        color,
        font,
        None,
        text_size(img, font, text)[1] * 0.4,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )

    # bbox = draw.textbbox(pos, text, font=font)
    # draw.rectangle(bbox, outline="red")

    next_pos = (
        draw_pos[0] + text_size(img, font, text)[0],
        int(draw_pos[1] + PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)[3]),
    )

    # draw.rectangle(
    #     (next_pos[0], next_pos[1], next_pos[0] + 4, next_pos[1] + 4),
    #     fill="black",
    # )

    return next_pos


def load_image(img_config: dict[str, Any]) -> PIL.Image.Image:
    img: PIL.Image.Image = PIL.Image.open(pathlib.Path(img_config["path"]))

    if "scale" in img_config:
        img = img.resize(
            (
                int(img.size[0] * img_config["scale"]),
                int(img.size[1] * img_config["scale"]),
            ),
            PIL.Image.Resampling.LANCZOS,
        )
    if "brightness" in img_config:
        img = PIL.ImageEnhance.Brightness(img).enhance(img_config["brightness"])

    return img


def alpha_paste(
    img: PIL.Image.Image, paint_img: PIL.Image.Image, pos: tuple[int, int]
) -> None:
    canvas = PIL.Image.new(
        "RGBA",
        img.size,
        (255, 255, 255, 0),
    )
    canvas.paste(paint_img, pos)
    img.alpha_composite(canvas, (0, 0))


def convert_to_gray(img: PIL.Image.Image) -> PIL.Image.Image:
    img = img.convert("RGB")
    img = img.point([int(pow(x / 255.0, 2.2) * 255) for x in range(256)] * 3)
    img = img.convert("L")
    img = img.point([int(pow(x / 255.0, 1.0 / 2.2) * 255) for x in range(256)])

    return img  # noqa: RET504
