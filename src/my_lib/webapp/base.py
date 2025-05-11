#!/usr/bin/env python3
import flask
import my_lib.flask_util
import my_lib.webapp.config

blueprint = flask.Blueprint("webapp-base", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


@blueprint.route("/", defaults={"filename": "index.html"})
@blueprint.route("/<path:filename>")
@my_lib.flask_util.gzipped
def webapp(filename):
    return flask.send_from_directory(my_lib.webapp.config.STATIC_DIR_PATH, filename)


blueprint_default = flask.Blueprint("webapp-default", __name__)


@blueprint_default.route("/")
@my_lib.flask_util.gzipped
def root():
    return flask.redirect(f"{my_lib.webapp.config.URL_PREFIX}/")
