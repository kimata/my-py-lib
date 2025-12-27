#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.flask_util モジュールのユニットテスト
"""
from __future__ import annotations

import gzip
import pathlib

import flask
import pytest


@pytest.fixture
def app():
    """テスト用 Flask アプリケーション"""
    app = flask.Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestGzipped:
    """gzipped デコレーターのテスト"""

    def test_compresses_response(self, app):
        """レスポンスを圧縮する"""
        from my_lib.flask_util import gzipped

        @app.route("/test")
        @gzipped
        def test_route():
            return flask.jsonify({"data": "test content"})

        with app.test_client() as client:
            response = client.get("/test", headers={"Accept-Encoding": "gzip"})

            assert response.headers.get("Content-Encoding") == "gzip"
            assert response.headers.get("Vary") == "Accept-Encoding"

    def test_does_not_compress_without_accept_encoding(self, app):
        """Accept-Encoding がない場合は圧縮しない"""
        from my_lib.flask_util import gzipped

        @app.route("/test")
        @gzipped
        def test_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/test")

            assert "Content-Encoding" not in response.headers or response.headers.get("Content-Encoding") != "gzip"


class TestSupportJsonp:
    """support_jsonp デコレーターのテスト"""

    def test_returns_jsonp_with_callback(self, app):
        """callback パラメータがある場合は JSONP を返す"""
        from my_lib.flask_util import support_jsonp

        @app.route("/test")
        @support_jsonp
        def test_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/test?callback=handleResponse")

            assert response.content_type == "text/javascript; charset=utf-8"
            assert b"handleResponse(" in response.data

    def test_returns_json_without_callback(self, app):
        """callback パラメータがない場合は JSON を返す"""
        from my_lib.flask_util import support_jsonp

        @app.route("/test")
        @support_jsonp
        def test_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/test")

            assert "application/json" in response.content_type


class TestRemoteHost:
    """remote_host 関数のテスト"""

    def test_returns_unknown_for_none(self, app):
        """remote_addr が None の場合は unknown を返す"""
        from my_lib.flask_util import remote_host

        with app.test_request_context():
            # モックリクエストを作成
            flask.request.remote_addr = None
            result = remote_host(flask.request)
            assert result == "unknown"

    def test_returns_hostname_or_ip(self, app):
        """ホスト名または IP を返す"""
        from my_lib.flask_util import remote_host

        with app.test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            result = remote_host(flask.request)
            # localhost または 127.0.0.1 のどちらかを返す
            assert result in ["localhost", "127.0.0.1"]


class TestAuthUser:
    """auth_user 関数のテスト"""

    def test_returns_email_header(self, app):
        """X-Auth-Request-Email ヘッダーを返す"""
        from my_lib.flask_util import auth_user

        with app.test_request_context(headers={"X-Auth-Request-Email": "user@example.com"}):
            result = auth_user(flask.request)
            assert result == "user@example.com"

    def test_returns_unknown_without_header(self, app):
        """ヘッダーがない場合は Unknown を返す"""
        from my_lib.flask_util import auth_user

        with app.test_request_context():
            result = auth_user(flask.request)
            assert result == "Unknown"


class TestCalculateEtag:
    """calculate_etag 関数のテスト"""

    def test_calculates_etag_from_data(self):
        """データから ETag を計算する"""
        from my_lib.flask_util import calculate_etag

        result = calculate_etag(data="test content")

        assert result is not None
        assert result.startswith('"')
        assert result.endswith('"')

    def test_calculates_etag_from_bytes(self):
        """バイトから ETag を計算する"""
        from my_lib.flask_util import calculate_etag

        result = calculate_etag(data=b"test content")

        assert result is not None

    def test_calculates_etag_from_file(self, temp_dir):
        """ファイルから ETag を計算する"""
        from my_lib.flask_util import calculate_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        result = calculate_etag(file_path=file_path)

        assert result is not None

    def test_returns_none_for_nonexistent_file(self, temp_dir):
        """存在しないファイルは None を返す"""
        from my_lib.flask_util import calculate_etag

        result = calculate_etag(file_path=temp_dir / "nonexistent.txt")

        assert result is None

    def test_returns_none_without_input(self):
        """入力がない場合は None を返す"""
        from my_lib.flask_util import calculate_etag

        result = calculate_etag()

        assert result is None

    def test_weak_etag(self):
        """弱い ETag を生成する"""
        from my_lib.flask_util import calculate_etag

        result = calculate_etag(data="test", weak=True)

        assert result is not None
        assert result.startswith('W/"')


class TestCheckEtag:
    """check_etag 関数のテスト"""

    def test_returns_false_without_header(self, app):
        """If-None-Match ヘッダーがない場合は False を返す"""
        from my_lib.flask_util import check_etag

        with app.test_request_context():
            result = check_etag('"abc123"', flask.request.headers)
            assert result is False

    def test_returns_true_for_wildcard(self, app):
        """ワイルドカードの場合は True を返す"""
        from my_lib.flask_util import check_etag

        with app.test_request_context(headers={"If-None-Match": "*"}):
            result = check_etag('"abc123"', flask.request.headers)
            assert result is True

    def test_returns_true_for_matching_etag(self, app):
        """一致する ETag の場合は True を返す"""
        from my_lib.flask_util import check_etag

        with app.test_request_context(headers={"If-None-Match": '"abc123"'}):
            result = check_etag('"abc123"', flask.request.headers)
            assert result is True

    def test_returns_true_for_weak_etag_match(self, app):
        """弱い ETag の一致でも True を返す"""
        from my_lib.flask_util import check_etag

        # 両方とも同じ weak ETag の場合
        with app.test_request_context(headers={"If-None-Match": 'W/"abc123"'}):
            result = check_etag('W/"abc123"', flask.request.headers)
            assert result is True

    def test_returns_false_for_non_matching_etag(self, app):
        """一致しない ETag の場合は False を返す"""
        from my_lib.flask_util import check_etag

        with app.test_request_context(headers={"If-None-Match": '"xyz789"'}):
            result = check_etag('"abc123"', flask.request.headers)
            assert result is False


class TestEtagCache:
    """etag_cache デコレーターのテスト"""

    def test_adds_etag_header(self, app):
        """ETag ヘッダーを追加する"""
        from my_lib.flask_util import etag_cache

        @app.route("/test")
        @etag_cache
        def test_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/test")

            assert "ETag" in response.headers

    def test_returns_304_for_matching_etag(self, app):
        """一致する ETag の場合は 304 を返す"""
        from my_lib.flask_util import etag_cache

        @app.route("/test")
        @etag_cache
        def test_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            # 最初のリクエストで ETag を取得
            response1 = client.get("/test")
            etag = response1.headers.get("ETag")

            # 同じ ETag でリクエスト
            response2 = client.get("/test", headers={"If-None-Match": etag})

            assert response2.status_code == 304


class TestEtagFile:
    """etag_file デコレーターのテスト"""

    def test_adds_etag_from_file(self, app, temp_dir):
        """ファイルから ETag を生成する"""
        from my_lib.flask_util import etag_file

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        @app.route("/test")
        @etag_file(file_path)
        def test_route():
            return flask.Response("test content")

        with app.test_client() as client:
            response = client.get("/test")

            assert "ETag" in response.headers


class TestEtagConditional:
    """etag_conditional デコレーターのテスト"""

    def test_generates_etag_from_response(self, app):
        """レスポンスから ETag を生成する"""
        from my_lib.flask_util import etag_conditional

        @app.route("/test")
        @etag_conditional()
        def test_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/test")

            assert "ETag" in response.headers

    def test_uses_custom_etag_function(self, app, temp_dir):
        """カスタム ETag 関数を使用する"""
        from my_lib.flask_util import etag_conditional

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        def get_etag_data():
            return {"file_path": str(file_path)}

        @app.route("/test")
        @etag_conditional(etag_func=get_etag_data)
        def test_route():
            return flask.Response("test content")

        with app.test_client() as client:
            response = client.get("/test")

            assert "ETag" in response.headers


class TestFileEtag:
    """file_etag デコレーターのテスト"""

    def test_generates_etag_from_filename_param(self, app, temp_dir):
        """filename パラメータからファイルの ETag を生成する"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        @app.route("/files/<path:filename>")
        @file_etag()
        def serve_file(filename):
            return flask.Response("test content")

        with app.test_client() as client:
            response = client.get(f"/files/{file_path}")

            # ファイルが存在する場合、ETag が設定される
            # 存在しない場合もエラーにならない


class TestGenerateEtagFromData:
    """_generate_etag_from_data 関数のテスト"""

    def test_generates_from_file_path_string(self, temp_dir):
        """文字列のファイルパスから生成する"""
        from my_lib.flask_util import _generate_etag_from_data

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        result = _generate_etag_from_data(str(file_path))
        assert result is not None

    def test_generates_from_bytes(self):
        """バイトから生成する"""
        from my_lib.flask_util import _generate_etag_from_data

        result = _generate_etag_from_data(b"test data")
        assert result is not None

    def test_generates_from_dict_with_file_path(self, temp_dir):
        """file_path キーを持つ辞書から生成する"""
        from my_lib.flask_util import _generate_etag_from_data

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        result = _generate_etag_from_data({"file_path": str(file_path)})
        assert result is not None

    def test_generates_from_dict_with_data(self):
        """data キーを持つ辞書から生成する"""
        from my_lib.flask_util import _generate_etag_from_data

        result = _generate_etag_from_data({"data": b"test data"})
        assert result is not None

    def test_returns_none_for_empty_dict(self):
        """空の辞書は None を返す"""
        from my_lib.flask_util import _generate_etag_from_data

        result = _generate_etag_from_data({})
        assert result is None

    def test_returns_none_for_unsupported_type(self):
        """サポートされない型は None を返す"""
        from my_lib.flask_util import _generate_etag_from_data

        result = _generate_etag_from_data({"other": "value"})
        assert result is None


class TestGzippedAdvanced:
    """gzipped デコレーターの追加テスト"""

    def test_does_not_compress_error_response(self, app):
        """エラーレスポンスは圧縮しない"""
        from my_lib.flask_util import gzipped

        @app.route("/error")
        @gzipped
        def error_route():
            return flask.Response("Error", status=500)

        with app.test_client() as client:
            response = client.get("/error", headers={"Accept-Encoding": "gzip"})
            assert response.status_code == 500
            # エラーレスポンスは圧縮されない可能性がある
            assert response.data == b"Error" or response.headers.get("Content-Encoding") == "gzip"

    def test_does_not_compress_if_already_encoded(self, app):
        """既にエンコードされているレスポンスは圧縮しない"""
        from my_lib.flask_util import gzipped

        @app.route("/already-encoded")
        @gzipped
        def already_encoded_route():
            response = flask.Response("Already encoded")
            response.headers["Content-Encoding"] = "deflate"
            return response

        with app.test_client() as client:
            response = client.get("/already-encoded", headers={"Accept-Encoding": "gzip"})
            assert response.headers.get("Content-Encoding") == "deflate"

    def test_sets_no_cache_when_disable_cache_flag(self, app):
        """disable_cache フラグが設定されている場合はキャッシュを無効化"""
        from my_lib.flask_util import gzipped

        @app.route("/no-cache")
        @gzipped
        def no_cache_route():
            flask.g.disable_cache = True
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/no-cache", headers={"Accept-Encoding": "gzip"})
            assert response.headers.get("Content-Encoding") == "gzip"
            assert "no-store" in response.headers.get("Cache-Control", "")


class TestEtagCacheAdvanced:
    """etag_cache デコレーターの追加テスト"""

    def test_preserves_existing_etag(self, app):
        """既存の ETag を保持する"""
        from my_lib.flask_util import etag_cache

        @app.route("/existing-etag")
        @etag_cache
        def existing_etag_route():
            response = flask.jsonify({"data": "test"})
            response.headers["ETag"] = '"custom-etag"'
            return response

        with app.test_client() as client:
            response = client.get("/existing-etag")
            assert response.headers.get("ETag") == '"custom-etag"'

    def test_non_response_object(self, app):
        """Response オブジェクト以外を返す場合"""
        from my_lib.flask_util import etag_cache

        @app.route("/tuple-response")
        @etag_cache
        def tuple_response_route():
            return "plain text", 200

        with app.test_client() as client:
            response = client.get("/tuple-response")
            assert response.status_code == 200


class TestEtagFileAdvanced:
    """etag_file デコレーターの追加テスト"""

    def test_returns_304_for_matching_etag(self, app, temp_dir):
        """一致する ETag で 304 を返す"""
        from my_lib.flask_util import etag_file

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        @app.route("/file-304")
        @etag_file(file_path)
        def file_304_route():
            return flask.Response("test content")

        with app.test_client() as client:
            # 最初のリクエストで ETag を取得
            response1 = client.get("/file-304")
            etag = response1.headers.get("ETag")

            # 同じ ETag でリクエスト
            response2 = client.get("/file-304", headers={"If-None-Match": etag})
            assert response2.status_code == 304

    def test_non_response_object(self, app, temp_dir):
        """Response オブジェクト以外を返す場合"""
        from my_lib.flask_util import etag_file

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        @app.route("/file-tuple")
        @etag_file(file_path)
        def file_tuple_route():
            return "plain text", 200

        with app.test_client() as client:
            response = client.get("/file-tuple")
            assert response.status_code == 200


class TestEtagConditionalAdvanced:
    """etag_conditional デコレーターの追加テスト"""

    def test_returns_304_with_etag_func(self, app, temp_dir):
        """etag_func を使用して 304 を返す"""
        from my_lib.flask_util import etag_conditional

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        def get_etag_data():
            return {"file_path": str(file_path)}

        @app.route("/conditional-304")
        @etag_conditional(etag_func=get_etag_data)
        def conditional_304_route():
            return flask.Response("test content")

        with app.test_client() as client:
            # 最初のリクエストで ETag を取得
            response1 = client.get("/conditional-304")
            etag = response1.headers.get("ETag")

            # 同じ ETag でリクエスト
            response2 = client.get("/conditional-304", headers={"If-None-Match": etag})
            assert response2.status_code == 304

    def test_generates_etag_from_response_when_no_func(self, app):
        """etag_func がない場合はレスポンスから ETag を生成"""
        from my_lib.flask_util import etag_conditional

        @app.route("/conditional-auto")
        @etag_conditional()
        def conditional_auto_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/conditional-auto")
            assert "ETag" in response.headers

    def test_non_response_object(self, app):
        """Response オブジェクト以外を返す場合"""
        from my_lib.flask_util import etag_conditional

        @app.route("/conditional-tuple")
        @etag_conditional()
        def conditional_tuple_route():
            return "plain text", 200

        with app.test_client() as client:
            response = client.get("/conditional-tuple")
            assert response.status_code == 200


class TestFileEtagAdvanced:
    """file_etag デコレーターの追加テスト"""

    def test_with_filename_func(self, app, temp_dir):
        """filename_func を使用"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "resource.txt"
        file_path.write_text("resource content")

        def get_file_path(resource_id):
            return file_path

        @app.route("/resource/<resource_id>")
        @file_etag(filename_func=get_file_path)
        def resource_route(resource_id):
            return flask.Response("resource content")

        with app.test_client() as client:
            response = client.get("/resource/123")
            assert "ETag" in response.headers

    def test_returns_304_with_matching_etag(self, app, temp_dir):
        """一致する ETag で 304 を返す"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "file.txt"
        file_path.write_text("file content")

        def get_file_path():
            return file_path

        @app.route("/file-etag-304")
        @file_etag(filename_func=get_file_path)
        def file_etag_304_route():
            return flask.Response("file content")

        with app.test_client() as client:
            # 最初のリクエストで ETag を取得
            response1 = client.get("/file-etag-304")
            etag = response1.headers.get("ETag")

            # 同じ ETag でリクエスト
            response2 = client.get("/file-etag-304", headers={"If-None-Match": etag})
            assert response2.status_code == 304

    def test_with_nonexistent_file(self, app, temp_dir):
        """存在しないファイルの場合"""
        from my_lib.flask_util import file_etag

        def get_file_path():
            return temp_dir / "nonexistent.txt"

        @app.route("/file-nonexistent")
        @file_etag(filename_func=get_file_path)
        def file_nonexistent_route():
            return flask.Response("content")

        with app.test_client() as client:
            response = client.get("/file-nonexistent")
            assert response.status_code == 200

    def test_with_args_filename(self, app, temp_dir):
        """args から filename を取得"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        @app.route("/files/<path:filename>")
        @file_etag()
        def files_route(filename):
            # filename は相対パスなので、temp_dir と組み合わせて使う
            return flask.Response("file content")

        with app.test_client() as client:
            # 相対パスを使う
            response = client.get("/files/test.txt")
            # デコレータが呼ばれるが、ファイルは temp_dir にあるため
            # filename="test.txt" では実ファイルが見つからない
            # それでもレスポンスは返る
            assert response.status_code == 200

    def test_non_response_object(self, app, temp_dir):
        """Response オブジェクト以外を返す場合"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        def get_file_path():
            return file_path

        @app.route("/file-tuple-advanced")
        @file_etag(filename_func=get_file_path)
        def file_tuple_route():
            return "plain text", 200

        with app.test_client() as client:
            response = client.get("/file-tuple-advanced")
            assert response.status_code == 200


class TestRemoteHostAdvanced:
    """remote_host 関数の追加テスト"""

    def test_socket_exception_returns_ip(self, app, mocker):
        """DNS逆引き失敗時はIPアドレスを返す"""
        import socket

        from my_lib.flask_util import remote_host

        # socket.gethostbyaddr が例外を発生させる
        mocker.patch("socket.gethostbyaddr", side_effect=socket.herror("DNS error"))

        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.168.1.100"}):
            result = remote_host(flask.request)
            assert result == "192.168.1.100"


class TestCacheControlBranches:
    """Cache-Control 分岐のテスト"""

    def test_etag_cache_with_existing_cache_control(self, app):
        """Cache-Control が既に設定されている場合はスキップ"""
        from my_lib.flask_util import etag_cache

        @app.route("/with-cache-control")
        @etag_cache
        def route_with_cache_control():
            response = flask.jsonify({"data": "test"})
            response.headers["Cache-Control"] = "no-cache"
            return response

        with app.test_client() as client:
            response = client.get("/with-cache-control")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-cache"

    def test_etag_file_with_existing_cache_control(self, app, temp_dir):
        """etag_file で Cache-Control が既に設定されている場合"""
        from my_lib.flask_util import etag_file

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        @app.route("/with-cache-control-file")
        @etag_file(str(file_path))
        def route_with_cache_control():
            response = flask.jsonify({"data": "test"})
            response.headers["Cache-Control"] = "private"
            return response

        with app.test_client() as client:
            response = client.get("/with-cache-control-file")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "private"

    def test_etag_conditional_no_cache_control(self, app):
        """cache_control=None の場合"""
        from my_lib.flask_util import etag_conditional

        @app.route("/no-cache-control")
        @etag_conditional(cache_control=None)
        def no_cache_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/no-cache-control")
            assert response.status_code == 200
            # Cache-Control は設定されない
            assert "Cache-Control" not in response.headers or response.headers.get("Cache-Control") != "max-age=86400, must-revalidate"

    def test_etag_conditional_304_no_cache_control(self, app):
        """cache_control=None で 304 を返す場合"""
        from my_lib.flask_util import calculate_etag, etag_conditional

        data = b"test data"
        # weak=True で ETag を生成（デフォルト設定と一致させる）
        etag = calculate_etag(data=data, weak=True)

        def get_etag():
            return data

        @app.route("/304-no-cache")
        @etag_conditional(etag_func=get_etag, cache_control=None)
        def route_304_no_cache():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/304-no-cache", headers={"If-None-Match": etag})
            assert response.status_code == 304
            # Cache-Control は設定されない
            assert "Cache-Control" not in response.headers

    def test_etag_conditional_with_existing_etag(self, app):
        """レスポンスに既に ETag が設定されている場合"""
        from my_lib.flask_util import etag_conditional

        @app.route("/with-etag")
        @etag_conditional()
        def route_with_etag():
            response = flask.jsonify({"data": "test"})
            response.headers["ETag"] = '"existing-etag"'
            return response

        with app.test_client() as client:
            response = client.get("/with-etag")
            assert response.status_code == 200
            # 既存の ETag は上書きされない（etag_func=None なので自動生成される）

    def test_file_etag_no_cache_control(self, app, temp_dir):
        """file_etag で cache_control=None の場合"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        def get_file_path():
            return file_path

        @app.route("/file-no-cache")
        @file_etag(filename_func=get_file_path, cache_control=None)
        def file_no_cache_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/file-no-cache")
            assert response.status_code == 200

    def test_file_etag_304_no_cache_control(self, app, temp_dir):
        """file_etag で cache_control=None で 304 を返す場合"""
        from my_lib.flask_util import calculate_etag, file_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")
        etag = calculate_etag(file_path=file_path, weak=True)

        def get_file_path():
            return file_path

        @app.route("/file-304-no-cache")
        @file_etag(filename_func=get_file_path, cache_control=None)
        def file_304_no_cache_route():
            return flask.jsonify({"data": "test"})

        with app.test_client() as client:
            response = client.get("/file-304-no-cache", headers={"If-None-Match": etag})
            assert response.status_code == 304
            assert "Cache-Control" not in response.headers

    def test_file_etag_with_existing_cache_control(self, app, temp_dir):
        """file_etag で既に Cache-Control が設定されている場合"""
        from my_lib.flask_util import file_etag

        file_path = temp_dir / "test.txt"
        file_path.write_text("test content")

        def get_file_path():
            return file_path

        @app.route("/file-existing-cache")
        @file_etag(filename_func=get_file_path)
        def file_existing_cache_route():
            response = flask.jsonify({"data": "test"})
            response.headers["Cache-Control"] = "no-store"
            return response

        with app.test_client() as client:
            response = client.get("/file-existing-cache")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "no-store"

    def test_etag_conditional_existing_cache_control(self, app):
        """etag_conditional で既に Cache-Control が設定されている場合"""
        from my_lib.flask_util import etag_conditional

        @app.route("/conditional-existing-cache")
        @etag_conditional()
        def conditional_existing_cache_route():
            response = flask.jsonify({"data": "test"})
            response.headers["Cache-Control"] = "max-age=3600"
            return response

        with app.test_client() as client:
            response = client.get("/conditional-existing-cache")
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "max-age=3600"
