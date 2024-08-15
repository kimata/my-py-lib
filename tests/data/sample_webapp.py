#!/usr/bin/env python3
import flask
import my_lib.webapp.config

blueprint = flask.Blueprint("sample", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)


@blueprint.route("/exec/log_write", methods=["GET"])
@my_lib.flask_util.support_jsonp
def exec_log_write():
    return ""
