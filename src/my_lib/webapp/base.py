#!/usr/bin/env python3
from __future__ import annotations

import flask

import my_lib.flask_util
import my_lib.webapp.config

blueprint = flask.Blueprint("webapp-base", __name__)


def _get_file_path(filename: str) -> str | None:
    if my_lib.webapp.config.STATIC_DIR_PATH is None:
        return None
    static_dir = my_lib.webapp.config.STATIC_DIR_PATH.resolve()
    requested_path = (static_dir / filename).resolve()

    if not str(requested_path).startswith(str(static_dir)):
        return None

    return str(requested_path)


@blueprint.route("/", defaults={"filename": "index.html"})
@blueprint.route("/<path:filename>")
@my_lib.flask_util.file_etag(filename_func=_get_file_path)
@my_lib.flask_util.gzipped
def webapp(filename: str) -> flask.Response:
    try:
        if my_lib.webapp.config.STATIC_DIR_PATH is None:
            flask.abort(500)

        static_dir = my_lib.webapp.config.STATIC_DIR_PATH.resolve()
        requested_path = (static_dir / filename).resolve()

        if not str(requested_path).startswith(str(static_dir)):
            flask.abort(404)

        # NOTE: static_dir は上で STATIC_DIR_PATH が None でないことを確認後に取得しているので
        # 型チェッカーが Path 型として認識できる
        if requested_path.exists():
            etag = my_lib.flask_util.calculate_etag(file_path=str(requested_path), weak=True)

            if etag and my_lib.flask_util.check_etag(etag, flask.request.headers):
                response = flask.make_response("", 304)
                response.headers["ETag"] = etag
                response.headers["Cache-Control"] = "max-age=86400, must-revalidate"
                return response

            response = flask.send_from_directory(static_dir, filename)

            if response.status_code == 200:
                response.headers["ETag"] = etag
                response.headers["Cache-Control"] = "max-age=86400, must-revalidate"

            return response
        else:
            return flask.send_from_directory(static_dir, filename)
    except (ValueError, OSError):
        flask.abort(404)


blueprint_default = flask.Blueprint("webapp-default", __name__)


@blueprint_default.route("/")
@my_lib.flask_util.gzipped
def root() -> flask.Response:
    return flask.redirect(f"{my_lib.webapp.config.URL_PREFIX}/")  # type: ignore[return-value]
