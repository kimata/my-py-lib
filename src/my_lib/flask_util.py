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
