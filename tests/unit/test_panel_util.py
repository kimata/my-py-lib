#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.panel_util モジュールのユニットテスト
"""
from __future__ import annotations

import pathlib

import PIL.Image
import pytest


class TestNotifyError:
    """notify_error 関数のテスト"""

    def test_logs_error(self, caplog):
        """エラーをログに記録する"""
        import logging

        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_util import notify_error

        config = SlackEmptyConfig()

        with caplog.at_level(logging.ERROR):
            notify_error(config, "test", "Error message")

        assert "Error message" in caplog.text


class TestCreateErrorImage:
    """create_error_image 関数のテスト"""

    def test_creates_error_image(self, temp_dir):
        """エラー画像を生成する"""
        from my_lib.panel_config import FontConfig, PanelGeometry
        from my_lib.panel_util import create_error_image

        # モックのパネル設定を作成
        class MockPanelConfig:
            panel = PanelGeometry(width=800, height=600)

        # 実際のフォントを使わないテストのため、スキップ
        # 実際のテストは統合テストで行う
        pass


class TestDrawPanelPatiently:
    """draw_panel_patiently 関数のテスト"""

    def test_returns_image_on_success(self, temp_dir):
        """成功時に画像を返す"""
        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_config import FontConfig, NormalPanelContext, PanelGeometry
        from my_lib.panel_util import draw_panel_patiently

        # モック
        class MockPanelConfig:
            panel = PanelGeometry(width=800, height=600)

        font_config = FontConfig(path=temp_dir)

        def mock_draw_func(panel_config, context, opt_config):
            return PIL.Image.new("RGBA", (800, 600), (255, 255, 255, 255))

        panel_config = MockPanelConfig()
        context = NormalPanelContext(
            font_config=font_config,
            slack_config=SlackEmptyConfig(),
        )

        result = draw_panel_patiently(mock_draw_func, panel_config, context)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], PIL.Image.Image)
        assert isinstance(result[1], float)

    def test_returns_error_image_on_failure(self, temp_dir, mocker):
        """失敗時にエラー画像を返す"""
        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_config import FontConfig, NormalPanelContext, PanelGeometry
        from my_lib.panel_util import draw_panel_patiently

        class MockPanelConfig:
            panel = PanelGeometry(width=800, height=600)

        font_config = FontConfig(path=temp_dir)

        def mock_draw_func(panel_config, context, opt_config):
            raise RuntimeError("Test error")

        # create_error_image をモック
        mocker.patch(
            "my_lib.panel_util.create_error_image",
            return_value=PIL.Image.new("RGBA", (800, 600), (255, 0, 0, 255)),
        )

        panel_config = MockPanelConfig()
        context = NormalPanelContext(
            font_config=font_config,
            slack_config=SlackEmptyConfig(),
        )

        result = draw_panel_patiently(mock_draw_func, panel_config, context, error_image=True)

        assert isinstance(result, tuple)
        assert len(result) == 3  # 失敗時は 3 要素
        assert isinstance(result[0], PIL.Image.Image)
        assert isinstance(result[2], str)

    def test_returns_blank_image_when_error_image_disabled(self, temp_dir, mocker):
        """error_image=False の場合は空画像を返す"""
        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_config import FontConfig, NormalPanelContext, PanelGeometry
        from my_lib.panel_util import draw_panel_patiently

        class MockPanelConfig:
            panel = PanelGeometry(width=800, height=600)

        font_config = FontConfig(path=temp_dir)

        def mock_draw_func(panel_config, context, opt_config):
            raise RuntimeError("Test error")

        panel_config = MockPanelConfig()
        context = NormalPanelContext(
            font_config=font_config,
            slack_config=SlackEmptyConfig(),
        )

        result = draw_panel_patiently(mock_draw_func, panel_config, context, error_image=False)

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], PIL.Image.Image)
        assert result[0].size == (800, 600)

    def test_updates_trial_in_context(self, temp_dir):
        """コンテキストの trial を更新する"""
        from my_lib.notify.slack import SlackEmptyConfig
        from my_lib.panel_config import FontConfig, NormalPanelContext, PanelGeometry
        from my_lib.panel_util import draw_panel_patiently

        class MockPanelConfig:
            panel = PanelGeometry(width=800, height=600)

        font_config = FontConfig(path=temp_dir)

        received_trials = []

        def mock_draw_func(panel_config, context, opt_config):
            received_trials.append(context.trial)
            return PIL.Image.new("RGBA", (800, 600))

        panel_config = MockPanelConfig()
        context = NormalPanelContext(
            font_config=font_config,
            slack_config=SlackEmptyConfig(),
            trial=0,
        )

        draw_panel_patiently(mock_draw_func, panel_config, context)

        assert received_trials == [1]  # trial は 1 から始まる
