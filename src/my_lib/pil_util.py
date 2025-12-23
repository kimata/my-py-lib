#!/usr/bin/env python3
from __future__ import annotations

import logging
import pathlib

import PIL.Image
import PIL.ImageDraw
import PIL.ImageEnhance
import PIL.ImageFont

from my_lib.panel_config import HasFontMap, HasIconProperties

# フォントロード済みキャッシュ
_loaded_fonts: dict[pathlib.Path, bool] = {}


class FontNotFoundError(Exception):
    """フォントファイルが見つからないエラー."""

    def __init__(self, message: str, details: str) -> None:
        """例外を初期化する。

        Args:
            message: エラーメッセージ
            details: 詳細なエラー情報

        """
        super().__init__(message)
        self.details = details


def get_font(config: HasFontMap, font_type: str, size: int) -> PIL.ImageFont.FreeTypeFont:
    """フォントを取得する

    Args:
        config: フォント設定 (path, map を持つ)
        font_type: フォントタイプ (例: "jp_bold", "en_medium")
        size: フォントサイズ

    Returns:
        PIL フォントオブジェクト

    Raises:
        FontNotFoundError: フォントファイルが見つからない場合
    """
    font_path = config.path.resolve() / config.map[font_type]

    if not font_path.exists():
        available_fonts = [f.name for f in config.path.resolve().glob("*") if f.is_file()]
        available_str = ", ".join(available_fonts) if available_fonts else "(なし)"

        details_lines = [
            "=" * 60,
            "フォントファイルが見つかりません",
            "=" * 60,
            "",
            f"  フォントタイプ: {font_type}",
            f"  ファイルパス: {font_path}",
            "",
            "  確認事項:",
            "    - フォントファイルが存在するか確認してください",
            "    - 設定ファイルのフォントパスが正しいか確認してください",
            f"    - フォントディレクトリ: {config.path.resolve()}",
            f"    - 利用可能なファイル: {available_str}",
            "",
            "=" * 60,
        ]
        details = "\n".join(details_lines)
        logging.error("\n%s", details)
        raise FontNotFoundError(
            f"フォントファイルが見つかりません: {font_path}",
            details,
        )

    if font_path not in _loaded_fonts:
        logging.debug("Load font: %s", font_path)
        _loaded_fonts[font_path] = True

    return PIL.ImageFont.truetype(font_path, size)


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
    stroke_fill: str | tuple[int, int, int, int] | None = None,
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
    stroke_fill: str | tuple[int, int, int, int] | None = None,
) -> tuple[int, int]:
    draw = PIL.ImageDraw.Draw(img)

    draw_pos: tuple[int, int]
    if align == "center":
        draw_pos = (int(pos[0] - text_size(img, font, text)[0] / 2.0), int(pos[1]))
    elif align == "right":
        draw_pos = (int(pos[0] - text_size(img, font, text)[0]), int(pos[1]))
    else:
        draw_pos = pos

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

    next_pos = (
        draw_pos[0] + text_size(img, font, text)[0],
        int(draw_pos[1] + PIL.ImageDraw.Draw(img).textbbox((0, 0), text, font)[3]),
    )

    return next_pos


def load_image(img_config: HasIconProperties) -> PIL.Image.Image:
    """画像を読み込む

    Args:
        img_config: アイコン設定 (path, scale, brightness を持つ)

    Returns:
        PIL 画像オブジェクト
    """
    img: PIL.Image.Image = PIL.Image.open(img_config.path)

    if img_config.scale != 1.0:
        img = img.resize(
            (
                int(img.size[0] * img_config.scale),
                int(img.size[1] * img_config.scale),
            ),
            PIL.Image.Resampling.LANCZOS,
        )
    if img_config.brightness != 1.0:
        img = PIL.ImageEnhance.Brightness(img).enhance(img_config.brightness)

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
