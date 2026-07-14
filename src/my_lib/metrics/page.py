#!/usr/bin/env python3
"""メトリクスダッシュボードページの共通部品集

各アプリのダッシュボード (rasp-water / unit-cooler / eink-weather-panel 等) が
重複して持っていたページ骨格・CSS・パーマリンク JS・Bulma ウィジェット・
favicon レスポンスを部品として提供する。

NOTE: ダッシュボード全体の registry 化は行わない (パネルの HTML / Chart.js
設定はドメイン固有性が高く、共通化してもコード量・可読性の利得がないため)。
各アプリはこの部品を組み合わせて自前の blueprint を構成する。
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import flask

if TYPE_CHECKING:
    from PIL import Image

BULMA_CSS_CDN = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">'
CHART_JS_CDN = '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
CHART_JS_BOXPLOT_CDN = '<script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-boxplot"></script>'
FONT_AWESOME_CDN = (
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
)

# ダッシュボード共通スタイル (チャート枠・統計カード・パーマリンク・モバイル対応)
COMMON_CSS = """
        .metrics-card { margin-bottom: 1rem; }
        @media (max-width: 768px) {
            .metrics-card { margin-bottom: 0.75rem; }
        }
        .stat-number { font-size: 2rem; font-weight: bold; }
        .chart-container { position: relative; height: 350px; margin: 0.5rem 0; }
        @media (max-width: 768px) {
            .chart-container { height: 300px; margin: 0.25rem 0; }
            .container.is-fluid { padding: 0.25rem !important; }
            .section { padding: 0.5rem 0.25rem !important; }
            .card { margin-bottom: 1rem !important; }
            .columns { margin: 0 !important; }
            .column { padding: 0.25rem !important; }
        }
        .japanese-font {
            font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
                         "Noto Sans CJK JP", "Yu Gothic", sans-serif;
        }
        .permalink-header {
            position: relative;
            display: inline-block;
        }
        .permalink-icon {
            opacity: 0;
            transition: opacity 0.2s ease-in-out;
            cursor: pointer;
            color: #4a90e2;
            margin-left: 0.5rem;
            font-size: 0.8em;
        }
        .permalink-header:hover .permalink-icon {
            opacity: 1;
        }
        .permalink-icon:hover {
            color: #357abd;
        }
"""

# セクション見出しのパーマリンク機能 (コピー + ハッシュスクロール)
PERMALINK_JS = """
        function initializePermalinks() {
            // ページ読み込み時にハッシュがある場合はスクロール
            if (window.location.hash) {
                const element = document.querySelector(window.location.hash);
                if (element) {
                    setTimeout(() => {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 500); // チャート描画完了を待つ
                }
            }
        }

        function copyPermalink(sectionId) {
            const url = window.location.origin + window.location.pathname + '#' + sectionId;

            // Clipboard APIを使用してURLをコピー
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(url).then(() => {
                    showCopyNotification();
                }).catch(err => {
                    console.error('Failed to copy: ', err);
                    fallbackCopyToClipboard(url);
                });
            } else {
                // フォールバック
                fallbackCopyToClipboard(url);
            }

            // URLにハッシュを設定（履歴には残さない）
            window.history.replaceState(null, null, '#' + sectionId);
        }

        function fallbackCopyToClipboard(text) {
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();

            try {
                document.execCommand('copy');
                showCopyNotification();
            } catch (err) {
                console.error('Fallback: Failed to copy', err);
                // 最後の手段として、プロンプトでURLを表示
                prompt('URLをコピーしてください:', text);
            }

            document.body.removeChild(textArea);
        }

        function showCopyNotification() {
            const notification = document.createElement('div');
            notification.textContent = 'パーマリンクをコピーしました！';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #23d160;
                color: white;
                padding: 12px 20px;
                border-radius: 4px;
                z-index: 1000;
                font-size: 14px;
            `;
            document.body.appendChild(notification);
            setTimeout(() => {
                notification.remove();
            }, 2000);
        }
"""


def page_head(title: str, favicon_path: str, *, boxplot: bool = False, extra_head: str = "") -> str:
    """ダッシュボードページの <head> 部を生成する (Bulma + Chart.js + Font Awesome)

    Args:
        title: ページタイトル
        favicon_path: favicon の URL パス
        boxplot: Chart.js の boxplot プラグインを読み込むか
        extra_head: 追加の head 要素 (プロジェクト固有 CSS 等)

    """
    boxplot_cdn = CHART_JS_BOXPLOT_CDN if boxplot else ""
    return f"""<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="icon" type="image/x-icon" href="{favicon_path}">
    {BULMA_CSS_CDN}
    {CHART_JS_CDN}
    {boxplot_cdn}
    {FONT_AWESOME_CDN}
    <style>
{COMMON_CSS}
    </style>
    {extra_head}
</head>"""


def page_header(icon: str, title: str, subtitle: str) -> str:
    """ページ先頭の見出し (Font Awesome アイコン + タイトル + サブタイトル)"""
    return f"""
                <h1 class="title is-2 has-text-centered">
                    <span class="icon is-large"><i class="fas {icon}"></i></span>
                    {title}
                </h1>
                <p class="subtitle has-text-centered">{subtitle}</p>
"""


def section_header(anchor: str, icon: str, title: str) -> str:
    """パーマリンク付きセクション見出し"""
    return f"""
        <h2 class="title is-4 permalink-header" id="{anchor}">
            <span class="icon"><i class="fas {icon}"></i></span>
            {title}
            <span class="permalink-icon" onclick="copyPermalink('{anchor}')">
                <i class="fas fa-link"></i>
            </span>
        </h2>
"""


def stat_item(heading: str, value: str, color_class: str = "") -> str:
    """統計カード内の1項目 (見出し + 値)"""
    return f"""
                            <div class="column is-one-third">
                                <div class="has-text-centered">
                                    <p class="heading">{heading}</p>
                                    <p class="stat-number {color_class}">{value}</p>
                                </div>
                            </div>
"""


def stat_card(title: str, items_html: str) -> str:
    """統計項目をまとめたカード"""
    return f"""
        <div class="columns">
            <div class="column">
                <div class="card metrics-card">
                    <div class="card-header">
                        <p class="card-header-title">{title}</p>
                    </div>
                    <div class="card-content">
                        <div class="columns is-multiline">
{items_html}
                        </div>
                    </div>
                </div>
            </div>
        </div>
"""


def chart_container(canvas_id: str) -> str:
    """Chart.js 描画用のコンテナ"""
    return f"""
                        <div class="chart-container">
                            <canvas id="{canvas_id}"></canvas>
                        </div>
"""


def favicon_ico_response(image: Image.Image, *, max_age: int = 3600) -> flask.Response:
    """PIL 画像を ICO 形式の favicon レスポンスに変換する

    Args:
        image: 32x32 相当の PIL 画像
        max_age: Cache-Control の max-age (秒)

    """
    try:
        output = io.BytesIO()
        image.save(output, format="ICO", sizes=[(32, 32)])
        output.seek(0)

        return flask.Response(
            output.getvalue(),
            mimetype="image/x-icon",
            headers={
                "Cache-Control": f"public, max-age={max_age}",
                "Content-Type": "image/x-icon",
            },
        )
    except Exception:
        logging.exception("favicon生成エラー")
        return flask.Response("", status=500)
