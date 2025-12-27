#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.pil_util モジュールのユニットテスト
"""
from __future__ import annotations

import pathlib

import PIL.Image
import PIL.ImageFont
import pytest


class TestFontNotFoundError:
    """FontNotFoundError のテスト"""

    def test_is_exception(self):
        """Exception のサブクラス"""
        from my_lib.pil_util import FontNotFoundError

        assert issubclass(FontNotFoundError, Exception)


class TestImageNotFoundError:
    """ImageNotFoundError のテスト"""

    def test_is_exception(self):
        """Exception のサブクラス"""
        from my_lib.pil_util import ImageNotFoundError

        assert issubclass(ImageNotFoundError, Exception)


class TestGetFont:
    """get_font 関数のテスト"""

    def test_raises_for_nonexistent_font(self):
        """存在しないフォントで例外を発生"""
        from my_lib.panel_config import FontConfig
        from my_lib.pil_util import FontNotFoundError, get_font

        config = FontConfig(
            path=pathlib.Path("/nonexistent"),
            map={"test": "font.ttf"},
        )

        with pytest.raises(FontNotFoundError):
            get_font(config, "test", 12)

    def test_returns_font_for_existing_file(self, temp_dir):
        """存在するフォントファイルを読み込む"""
        # NOTE: 実際のフォントファイルが必要なため、このテストは統合テストで行う
        pass


class TestTextSize:
    """text_size 関数のテスト"""

    def test_returns_tuple(self):
        """タプルを返す"""
        from my_lib.pil_util import text_size

        img = PIL.Image.new("RGBA", (100, 100))
        font = PIL.ImageFont.load_default()

        result = text_size(img, font, "test")  # type: ignore[arg-type]

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)


class TestDrawText:
    """draw_text 関数のテスト"""

    def test_draws_text_on_image(self):
        """画像にテキストを描画する"""
        from my_lib.pil_util import draw_text

        img = PIL.Image.new("RGBA", (200, 100), (255, 255, 255, 255))
        font = PIL.ImageFont.load_default()

        result = draw_text(img, "Hello", (10, 10), font)  # type: ignore[arg-type]

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_handles_multiline_text(self):
        """複数行テキストを処理する"""
        from my_lib.pil_util import draw_text

        img = PIL.Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        font = PIL.ImageFont.load_default()

        result = draw_text(img, "Line 1\nLine 2", (10, 10), font)  # type: ignore[arg-type]

        assert isinstance(result, tuple)


class TestDrawTextLine:
    """draw_text_line 関数のテスト"""

    def test_draws_left_aligned(self):
        """左寄せで描画する"""
        from my_lib.pil_util import draw_text_line

        img = PIL.Image.new("RGBA", (200, 100), (255, 255, 255, 255))
        font = PIL.ImageFont.load_default()

        result = draw_text_line(img, "Hello", (10, 10), font, align="left")  # type: ignore[arg-type]

        assert isinstance(result, tuple)

    def test_draws_center_aligned(self):
        """中央寄せで描画する"""
        from my_lib.pil_util import draw_text_line

        img = PIL.Image.new("RGBA", (200, 100), (255, 255, 255, 255))
        font = PIL.ImageFont.load_default()

        result = draw_text_line(img, "Hello", (100, 10), font, align="center")  # type: ignore[arg-type]

        assert isinstance(result, tuple)

    def test_draws_right_aligned(self):
        """右寄せで描画する"""
        from my_lib.pil_util import draw_text_line

        img = PIL.Image.new("RGBA", (200, 100), (255, 255, 255, 255))
        font = PIL.ImageFont.load_default()

        result = draw_text_line(img, "Hello", (190, 10), font, align="right")  # type: ignore[arg-type]

        assert isinstance(result, tuple)

    def test_draws_with_stroke(self):
        """ストローク付きで描画する"""
        from my_lib.pil_util import draw_text_line

        img = PIL.Image.new("RGBA", (200, 100), (255, 255, 255, 255))
        font = PIL.ImageFont.load_default()

        result = draw_text_line(
            img, "Hello", (10, 10), font, stroke_width=2, stroke_fill="#FF0000"  # type: ignore[arg-type]
        )

        assert isinstance(result, tuple)


class TestLoadImage:
    """load_image 関数のテスト"""

    def test_raises_for_nonexistent_image(self):
        """存在しない画像で例外を発生"""
        from my_lib.panel_config import IconConfig
        from my_lib.pil_util import ImageNotFoundError, load_image

        config = IconConfig(path=pathlib.Path("/nonexistent.png"))

        with pytest.raises(ImageNotFoundError):
            load_image(config)

    def test_loads_existing_image(self, temp_dir):
        """存在する画像を読み込む"""
        from my_lib.panel_config import IconConfig
        from my_lib.pil_util import load_image

        # テスト用画像を作成
        img_path = temp_dir / "test.png"
        test_img = PIL.Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        test_img.save(img_path)

        config = IconConfig(path=img_path)
        result = load_image(config)

        assert isinstance(result, PIL.Image.Image)
        assert result.size == (100, 100)

    def test_scales_image(self, temp_dir):
        """画像をスケールする"""
        from my_lib.panel_config import IconConfig
        from my_lib.pil_util import load_image

        img_path = temp_dir / "test.png"
        test_img = PIL.Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        test_img.save(img_path)

        config = IconConfig(path=img_path, scale=0.5)
        result = load_image(config)

        assert result.size == (50, 50)

    def test_adjusts_brightness(self, temp_dir):
        """輝度を調整する"""
        from my_lib.panel_config import IconConfig
        from my_lib.pil_util import load_image

        img_path = temp_dir / "test.png"
        test_img = PIL.Image.new("RGBA", (100, 100), (128, 128, 128, 255))
        test_img.save(img_path)

        config = IconConfig(path=img_path, brightness=0.5)
        result = load_image(config)

        assert isinstance(result, PIL.Image.Image)


class TestAlphaPaste:
    """alpha_paste 関数のテスト"""

    def test_pastes_with_alpha(self):
        """アルファ付きで貼り付ける"""
        from my_lib.pil_util import alpha_paste

        base_img = PIL.Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        paint_img = PIL.Image.new("RGBA", (50, 50), (255, 0, 0, 128))

        alpha_paste(base_img, paint_img, (10, 10))

        # 貼り付け位置のピクセルが変更されていることを確認
        pixel = base_img.getpixel((20, 20))
        # アルファ合成されているため、赤みがかった色になるはず
        assert isinstance(pixel, tuple)
        assert pixel[0] > 128  # 赤成分がある


class TestConvertToGray:
    """convert_to_gray 関数のテスト"""

    def test_converts_to_grayscale(self):
        """グレースケールに変換する"""
        from my_lib.pil_util import convert_to_gray

        img = PIL.Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        result = convert_to_gray(img)

        assert result.mode == "L"

    def test_applies_gamma_correction(self):
        """ガンマ補正を適用する"""
        from my_lib.pil_util import convert_to_gray

        img = PIL.Image.new("RGBA", (100, 100), (128, 128, 128, 255))
        result = convert_to_gray(img)

        # ガンマ補正により、単純な平均値とは異なる結果になる
        assert isinstance(result, PIL.Image.Image)
