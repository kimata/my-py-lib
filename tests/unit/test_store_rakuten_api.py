#!/usr/bin/env python3
# ruff: noqa: S101
"""my_lib.store.rakuten の API クライアント（2026 年新仕様）のユニットテスト."""

from __future__ import annotations

import json
from typing import Any
from unittest import mock

import requests

from my_lib.store.rakuten import api
from my_lib.store.rakuten.credentials import RakutenApiConfig


def _make_response(status_code: int, body: dict[str, Any]) -> requests.Response:
    """任意のステータス・JSON 本文を持つ requests.Response を組み立てる"""
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(body).encode()
    response.url = api._API_ENDPOINT
    return response


_ITEM = {
    "itemName": "マキタ TD002G",
    "itemUrl": "https://item.rakuten.co.jp/shop/td002g/",
    "itemPrice": 39800,
    "mediumImageUrls": ["https://thumbnail.image.rakuten.co.jp/td002g.jpg"],
    "shopName": "shop",
    "shopCode": "shop",
    "itemCode": "shop:td002g",
}


class TestRakutenApiConfig:
    """RakutenApiConfig のテスト"""

    def test_parse_with_access_key(self):
        """access_key を含む dict から生成できる"""
        config = RakutenApiConfig.parse(
            {"application_id": "app-id", "access_key": "key", "affiliate_id": "aff"}
        )

        assert config.application_id == "app-id"
        assert config.access_key == "key"
        assert config.affiliate_id == "aff"

    def test_parse_without_access_key(self):
        """access_key 省略時は None（旧設定との互換）"""
        config = RakutenApiConfig.parse({"application_id": "app-id"})

        assert config.access_key is None
        assert config.affiliate_id is None


class TestSearch:
    """search() のテスト"""

    def test_sends_access_key_header_to_new_endpoint(self):
        """新エンドポイントに accessKey ヘッダ付きでリクエストする"""
        config = RakutenApiConfig(application_id="app-id", access_key="secret-key", affiliate_id="aff")
        body = {"count": 1, "page": 1, "pageCount": 1, "Items": [_ITEM]}

        with mock.patch.object(api.requests, "get", return_value=_make_response(200, body)) as get:
            results = api.search(config, api.SearchCondition(keyword="TD002G"), max_items=10)

        assert len(results) == 1
        assert results[0].name == "マキタ TD002G"
        assert results[0].price == 39800

        get.assert_called_once()
        called_url = get.call_args.args[0]
        called_kwargs = get.call_args.kwargs
        assert called_url.startswith("https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/")
        assert called_kwargs["headers"] == {"accessKey": "secret-key"}
        # accessKey はクエリに含めない（URL への露出防止）
        assert "accessKey" not in called_kwargs["params"]
        assert called_kwargs["params"]["applicationId"] == "app-id"
        assert called_kwargs["params"]["affiliateId"] == "aff"
        assert called_kwargs["params"]["formatVersion"] == 2

    def test_accepts_lowercase_items_key(self):
        """応答のトップレベルキーが items（小文字）でもパースできる"""
        config = RakutenApiConfig(application_id="app-id", access_key="key")
        body = {"count": 1, "page": 1, "pageCount": 1, "items": [_ITEM]}

        with mock.patch.object(api.requests, "get", return_value=_make_response(200, body)):
            results = api.search(config, api.SearchCondition(keyword="TD002G"))

        assert len(results) == 1

    def test_returns_empty_without_access_key(self):
        """access_key 未設定なら API を呼ばず空リストを返す"""
        config = RakutenApiConfig(application_id="app-id")

        with mock.patch.object(api.requests, "get") as get:
            results = api.search(config, api.SearchCondition(keyword="TD002G"))

        assert results == []
        get.assert_not_called()

    def test_http_error_is_logged_and_returns_empty(self, caplog):
        """HTTP エラー時はエラーメッセージをログに出して空リストを返す"""
        config = RakutenApiConfig(application_id="app-id", access_key="bad")
        body = {"errors": {"errorCode": 403, "errorMessage": "Invalid Access Key"}}

        with (
            mock.patch.object(api.requests, "get", return_value=_make_response(403, body)),
            caplog.at_level("ERROR"),
        ):
            results = api.search(config, api.SearchCondition(keyword="TD002G"))

        assert results == []
        assert "Invalid Access Key" in caplog.text
        assert "status=403" in caplog.text
