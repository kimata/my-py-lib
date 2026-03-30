#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import cast

import flask

import my_lib.flask_util
import my_lib.webapp.config


def _build_file_path_resolver(static_dir_path: Path):
    static_dir = static_dir_path.resolve()

    def resolver(filename: str) -> str | None:
        requested_path = (static_dir / filename).resolve()
        if not str(requested_path).startswith(str(static_dir)):
            return None
        return str(requested_path)

    return resolver


def create_static_blueprint(
    *,
    environment: my_lib.webapp.config.WebappEnvironment,
    name: str = "webapp-base",
) -> flask.Blueprint:
    blueprint = flask.Blueprint(name, __name__)
    static_dir = environment.static_dir_path.resolve()
    file_path_resolver = _build_file_path_resolver(static_dir)

    @blueprint.route("/", defaults={"filename": "index.html"})
    @blueprint.route("/<path:filename>")
    @my_lib.flask_util.file_etag(filename_func=file_path_resolver)
    @my_lib.flask_util.gzipped
    def webapp(filename: str) -> flask.Response:
        try:
            requested_path = (static_dir / filename).resolve()
            if not str(requested_path).startswith(str(static_dir)):
                flask.abort(404)

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

            return flask.send_from_directory(static_dir, filename)
        except (ValueError, OSError):
            flask.abort(404)
            return cast(flask.Response, None)

    return blueprint


def create_root_redirect_blueprint(
    *,
    url_prefix: str,
    name: str = "webapp-default",
) -> flask.Blueprint:
    blueprint = flask.Blueprint(name, __name__)

    @blueprint.route("/")
    @my_lib.flask_util.gzipped
    def root() -> flask.Response:
        return cast(flask.Response, flask.redirect(f"{url_prefix}/"))

    return blueprint
