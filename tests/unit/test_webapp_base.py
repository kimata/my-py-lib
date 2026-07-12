#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.webapp.base モジュールのユニットテスト
"""

from __future__ import annotations

import flask
import pytest

import my_lib.webapp.base
import my_lib.webapp.config


@pytest.fixture
def static_dir(tmp_path):
    """テスト用静的ファイルディレクトリ"""
    (tmp_path / "index.html").write_text("<html><body>index</body></html>")
    (tmp_path / "other.html").write_text("<html><body>other</body></html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("console.log('test')")
    return tmp_path


@pytest.fixture
def client(static_dir):
    """静的 Blueprint を登録したテストクライアント"""
    app = flask.Flask(__name__)
    app.config["TESTING"] = True
    environment = my_lib.webapp.config.WebappEnvironment(
        url_prefix=None,
        static_dir_path=static_dir,
    )
    app.register_blueprint(my_lib.webapp.base.create_static_blueprint(environment=environment))
    return app.test_client()


class TestCacheControl:
    """静的ファイル配信の Cache-Control のテスト"""

    def test_html_is_no_cache(self, client):
        """HTML は毎回再検証させる（デプロイ後に古いフロントが使われ続けるのを防ぐ）"""
        response = client.get("/other.html")

        assert response.status_code == 200
        assert response.headers["Cache-Control"] == my_lib.webapp.base.HTML_CACHE_CONTROL
        assert "ETag" in response.headers

    def test_root_is_no_cache(self, client):
        """ルート（index.html への解決）も HTML として扱う"""
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["Cache-Control"] == my_lib.webapp.base.HTML_CACHE_CONTROL

    def test_asset_is_long_cache(self, client):
        """ハッシュ付きアセットは長期キャッシュ"""
        response = client.get("/assets/index-abc123.js")

        assert response.status_code == 200
        assert response.headers["Cache-Control"] == my_lib.webapp.base.ASSET_CACHE_CONTROL

    def test_html_304_is_no_cache(self, client):
        """ETag 再検証の 304 応答でも HTML は no-cache を維持する"""
        first = client.get("/")
        etag = first.headers["ETag"]

        response = client.get("/", headers={"If-None-Match": etag})

        assert response.status_code == 304
        assert response.headers["Cache-Control"] == my_lib.webapp.base.HTML_CACHE_CONTROL

    def test_asset_304_is_long_cache(self, client):
        """ETag 再検証の 304 応答でアセットは長期キャッシュを維持する"""
        first = client.get("/assets/index-abc123.js")
        etag = first.headers["ETag"]

        response = client.get("/assets/index-abc123.js", headers={"If-None-Match": etag})

        assert response.status_code == 304
        assert response.headers["Cache-Control"] == my_lib.webapp.base.ASSET_CACHE_CONTROL
