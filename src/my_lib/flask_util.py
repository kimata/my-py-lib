#!/usr/bin/env python3
import functools
import gzip
import hashlib
import io
import socket
from pathlib import Path

import flask


def gzipped(f):
    @functools.wraps(f)
    def view_func(*args, **kwargs):
        @flask.after_this_request
        def zipper(response):
            accept_encoding = flask.request.headers.get("Accept-Encoding", "")

            if "gzip" not in accept_encoding.lower():
                return response

            response.direct_passthrough = False

            if (
                response.status_code < 200
                or response.status_code >= 300
                or "Content-Encoding" in response.headers
            ):
                return response
            gzip_buffer = io.BytesIO()
            gzip_file = gzip.GzipFile(mode="wb", fileobj=gzip_buffer)
            gzip_file.write(response.data)
            gzip_file.close()

            response.data = gzip_buffer.getvalue()
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Vary"] = "Accept-Encoding"
            response.headers["Content-Length"] = len(response.data)

            if flask.g.pop("disable_cache", False):
                response.headers["Cache-Control"] = "no-store, must-revalidate"
                response.headers["Expires"] = "0"
            else:
                response.headers["Cache-Control"] = "max-age=86400"

            return response

        return f(*args, **kwargs)

    return view_func


def support_jsonp(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        callback = flask.request.args.get("callback", False)
        if callback:
            content = callback + "(" + f().data.decode().strip() + ")"
            return flask.current_app.response_class(content, mimetype="text/javascript")
        else:
            return f(*args, **kwargs)

    return decorated_function


def remote_host(request):
    try:
        return socket.gethostbyaddr(request.remote_addr)[0]
    except Exception:
        return request.remote_addr


def auth_user(request):
    return request.headers.get("X-Auth-Request-Email", "Unknown")


def calculate_etag(data=None, file_path=None, weak=False):
    if file_path and Path(file_path).exists():
        stat = Path(file_path).stat()
        etag_base = f"{stat.st_mtime}-{stat.st_size}"
        etag = hashlib.md5(etag_base.encode()).hexdigest()  # noqa: S324
    elif data is not None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        etag = hashlib.md5(data).hexdigest()  # noqa: S324
    else:
        return None

    return f'W/"{etag}"' if weak else f'"{etag}"'


def check_etag(etag, request_headers):
    if not etag:
        return False

    if_none_match = request_headers.get("If-None-Match")
    if not if_none_match:
        return False

    if if_none_match.strip() == "*":
        return True

    etags = [tag.strip() for tag in if_none_match.split(",")]

    etag_value = etag.strip('"').replace("W/", "")
    for client_etag in etags:
        client_etag_value = client_etag.strip().strip('"').replace("W/", "")
        if etag_value == client_etag_value:
            return True

    return False


def etag_cache(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)

        if isinstance(response, flask.Response) and response.status_code == 200:
            etag = response.headers.get("ETag")
            if not etag:
                etag = calculate_etag(data=response.get_data())
                response.headers["ETag"] = etag

            if check_etag(etag, flask.request.headers):
                return flask.make_response("", 304)

            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "max-age=86400, must-revalidate"

        return response

    return decorated_function


def etag_file(file_path):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            etag = calculate_etag(file_path=file_path, weak=True)

            if etag and check_etag(etag, flask.request.headers):
                response = flask.make_response("", 304)
                response.headers["ETag"] = etag
                response.headers["Cache-Control"] = "max-age=86400, must-revalidate"
                return response

            response = f(*args, **kwargs)

            if isinstance(response, flask.Response) and response.status_code == 200:
                response.headers["ETag"] = etag
                if "Cache-Control" not in response.headers:
                    response.headers["Cache-Control"] = "max-age=86400, must-revalidate"

            return response

        return decorated_function

    return decorator


def _generate_etag_from_data(etag_data, weak=True):
    """ETAGデータからETAGを生成する内部関数"""
    if isinstance(etag_data, str):
        return calculate_etag(file_path=etag_data, weak=weak)
    elif isinstance(etag_data, (bytes, str)):
        return calculate_etag(data=etag_data, weak=weak)
    elif isinstance(etag_data, dict) and "file_path" in etag_data:
        return calculate_etag(file_path=etag_data["file_path"], weak=weak)
    elif isinstance(etag_data, dict) and "data" in etag_data:
        return calculate_etag(data=etag_data["data"], weak=weak)
    return None


def etag_conditional(etag_func=None, cache_control="max-age=86400, must-revalidate", weak=True):
    """
    汎用ETAGキャッシュデコレーター

    Args:
        etag_func: ETag生成のためのデータを取得する関数。None の場合はレスポンスデータからETagを生成
        cache_control: Cache-Controlヘッダーの値
        weak: WeakなETAGを使用するかどうか

    Examples:
        # レスポンスデータからETAGを自動生成
        @etag_conditional()
        def api_data():
            return {"data": "some content"}

        # カスタムETag生成関数を使用
        def get_etag_data():
            return {"file_path": "/path/to/file.txt"}

        @etag_conditional(etag_func=get_etag_data)
        def custom_handler():
            return "content"

    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # ETAGを生成
            etag = None
            if etag_func:
                etag_data = etag_func(*args, **kwargs)
                etag = _generate_etag_from_data(etag_data, weak)

            # If-None-Matchヘッダーをチェック
            if etag and check_etag(etag, flask.request.headers):
                response = flask.make_response("", 304)
                response.headers["ETag"] = etag
                if cache_control:
                    response.headers["Cache-Control"] = cache_control
                return response

            # 元の関数を実行
            response = f(*args, **kwargs)

            # レスポンスにETAGヘッダーを追加
            if isinstance(response, flask.Response) and response.status_code == 200:
                if etag:
                    response.headers["ETag"] = etag
                elif not response.headers.get("ETag"):
                    response_etag = calculate_etag(data=response.get_data(), weak=weak)
                    response.headers["ETag"] = response_etag

                if cache_control and "Cache-Control" not in response.headers:
                    response.headers["Cache-Control"] = cache_control

            return response

        return decorated_function

    return decorator


def file_etag(filename_func=None, cache_control="max-age=86400, must-revalidate"):
    """
    ファイルベースETAGキャッシュデコレーター

    Args:
        filename_func: ファイルパスを取得する関数。Noneの場合は'filename'パラメータを使用
        cache_control: Cache-Controlヘッダーの値

    Examples:
        # filename パラメータから自動取得
        @file_etag()
        def serve_file(filename):
            return send_file(filename)

        # カスタムファイルパス取得関数を使用
        def get_file_path(resource_id):
            return f"/static/{resource_id}.html"

        @file_etag(filename_func=get_file_path)
        def serve_resource(resource_id):
            return send_file(get_file_path(resource_id))

    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # ファイルパスを取得
            if filename_func:
                file_path = filename_func(*args, **kwargs)
            else:
                # デフォルトでfilenameパラメータを使用
                file_path = kwargs.get("filename") or (args[0] if args else None)

            if file_path and Path(file_path).exists():
                etag = calculate_etag(file_path=file_path, weak=True)

                # If-None-Matchヘッダーをチェック
                if etag and check_etag(etag, flask.request.headers):
                    response = flask.make_response("", 304)
                    response.headers["ETag"] = etag
                    if cache_control:
                        response.headers["Cache-Control"] = cache_control
                    return response

            # 元の関数を実行
            response = f(*args, **kwargs)

            # レスポンスにETAGヘッダーを追加
            if (
                isinstance(response, flask.Response)
                and response.status_code == 200
                and file_path
                and Path(file_path).exists()
            ):
                etag = calculate_etag(file_path=file_path, weak=True)
                response.headers["ETag"] = etag
                if cache_control and "Cache-Control" not in response.headers:
                    response.headers["Cache-Control"] = cache_control

            return response

        return decorated_function

    return decorator
