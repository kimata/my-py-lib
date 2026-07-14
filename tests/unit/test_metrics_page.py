#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.metrics.page モジュールのユニットテスト
"""

from __future__ import annotations


class TestPageHead:
    """page_head のテスト"""

    def test_contains_title_and_favicon(self):
        import my_lib.metrics.page

        head = my_lib.metrics.page.page_head("テスト ダッシュボード", "/test/favicon.ico")
        assert "<title>テスト ダッシュボード</title>" in head
        assert 'href="/test/favicon.ico"' in head
        assert "chart.js" in head
        assert "bulma" in head
        assert "chartjs-chart-boxplot" not in head

    def test_boxplot_plugin_optional(self):
        import my_lib.metrics.page

        head = my_lib.metrics.page.page_head("t", "/f.ico", boxplot=True)
        assert "chartjs-chart-boxplot" in head

    def test_extra_head_appended(self):
        import my_lib.metrics.page

        head = my_lib.metrics.page.page_head("t", "/f.ico", extra_head='<meta name="x">')
        assert '<meta name="x">' in head


class TestWidgets:
    """ウィジェット部品のテスト"""

    def test_section_header_has_permalink(self):
        import my_lib.metrics.page

        html = my_lib.metrics.page.section_header("basic-stats", "fa-chart-bar", "基本統計")
        assert 'id="basic-stats"' in html
        assert "copyPermalink('basic-stats')" in html
        assert "fa-chart-bar" in html

    def test_stat_card_wraps_items(self):
        import my_lib.metrics.page

        items = my_lib.metrics.page.stat_item("総回数", "42", "has-text-primary")
        card = my_lib.metrics.page.stat_card("実績", items)
        assert "総回数" in card
        assert "42" in card
        assert "has-text-primary" in card
        assert "card-header-title" in card

    def test_chart_container(self):
        import my_lib.metrics.page

        html = my_lib.metrics.page.chart_container("dailyChart")
        assert 'id="dailyChart"' in html
        assert "chart-container" in html

    def test_permalink_js_defines_functions(self):
        import my_lib.metrics.page

        js = my_lib.metrics.page.PERMALINK_JS
        for name in ("initializePermalinks", "copyPermalink", "fallbackCopyToClipboard"):
            assert f"function {name}" in js


class TestFaviconResponse:
    """favicon_ico_response のテスト"""

    def test_returns_ico_response(self):
        import flask
        from PIL import Image

        import my_lib.metrics.page

        app = flask.Flask(__name__)
        with app.test_request_context():
            image = Image.new("RGBA", (32, 32), (52, 152, 219, 255))
            response = my_lib.metrics.page.favicon_ico_response(image)

        assert response.status_code == 200
        assert response.mimetype == "image/x-icon"
        assert response.headers["Cache-Control"] == "public, max-age=3600"
        assert response.data[:4] == b"\x00\x00\x01\x00"  # ICO マジックナンバー
