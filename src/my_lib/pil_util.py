#!/usr/bin/env python3
import logging
import pathlib

import PIL.ImageDraw
import PIL.ImageEnhance
import PIL.ImageFont


def get_font(config, font_type, size):
    font_path = pathlib.Path(config["path"]).resolve() / config["map"][font_type]

    logging.info("Load font: %s", font_path)

    return PIL.ImageFont.truetype(font_path, size)


def text_size(img, font, text):
    left, top, right, bottom = PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)

    return (right - left, bottom - top)


# NOTE: 詳細追えてないものの，英語フォントでボディサイズがおかしいものがあったので，
# font_height_scale で補正できるようにしている．FuturaStd とかだと 0.75 が良さそう．
def draw_text(  # noqa: PLR0913
    img,
    text,
    pos,
    font,
    align="left",
    color="#000",
    stroke_width=0,
    stroke_fill=None,
):
    draw = PIL.ImageDraw.Draw(img)

    if align == "center":
        pos = (int(pos[0] - text_size(img, font, text)[0] / 2.0), int(pos[1]))
    elif align == "right":
        pos = (int(pos[0] - text_size(img, font, text)[0]), int(pos[1]))

    # draw.rectangle(
    #     (pos[0], pos[1], pos[0] + 4, pos[1] + 4),
    #     fill="black",
    # )

    pos = (pos[0], pos[1] - PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)[1])

    draw.text(
        pos,
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
        pos[0] + text_size(img, font, text)[0],
        pos[1] + PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)[3],
    )

    # draw.rectangle(
    #     (next_pos[0], next_pos[1], next_pos[0] + 4, next_pos[1] + 4),
    #     fill="black",
    # )

    return next_pos  # noqa: RET504


def load_image(img_config):
    img = PIL.Image.open(pathlib.Path(img_config["path"]))

    if "scale" in img_config:
        img = img.resize(
            (
                int(img.size[0] * img_config["scale"]),
                int(img.size[1] * img_config["scale"]),
            ),
            PIL.Image.LANCZOS,
        )
    if "brightness" in img_config:
        img = PIL.ImageEnhance.Brightness(img).enhance(img_config["brightness"])

    return img


def alpha_paste(img, paint_img, pos):
    canvas = PIL.Image.new(
        "RGBA",
        img.size,
        (255, 255, 255, 0),
    )
    canvas.paste(paint_img, pos)
    img.alpha_composite(canvas, (0, 0))


def convert_to_gray(img):
    img = img.convert("RGB")
    img = img.point([int(pow(x / 255.0, 2.2) * 255) for x in range(256)] * 3)
    img = img.convert("L")
    img = img.point([int(pow(x / 255.0, 1.0 / 2.2) * 255) for x in range(256)])

    return img  # noqa: RET504