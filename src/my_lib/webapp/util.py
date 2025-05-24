#!/usr/bin/env python3
import os
import tracemalloc

import my_lib.flask_util
import my_lib.time
import my_lib.webapp.config
import psutil
import uptime

import flask

blueprint = flask.Blueprint("webapp-util", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

snapshot_prev = None


@blueprint.route("/api/memory", methods=["GET"])
@my_lib.flask_util.support_jsonp
def print_memory():
    return {"memory": psutil.Process(os.getpid()).memory_info().rss}


# NOTE: メモリリーク調査用
@blueprint.route("/api/snapshot", methods=["GET"])
@my_lib.flask_util.support_jsonp
def snap():
    global snapshot_prev  # noqa: PLW0603

    if not snapshot_prev:
        tracemalloc.start()
        snapshot_prev = tracemalloc.take_snapshot()

        return {"msg": "taken snapshot"}
    else:
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.compare_to(snapshot_prev, "lineno")
        snapshot_prev = snapshot

        return flask.jsonify([str(stat) for stat in top_stats[:10]])


@blueprint.route("/api/sysinfo", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_sysinfo():
    return flask.jsonify(
        {
            "date": my_lib.time.now().isoformat(),
            "timezone": my_lib.time.get_tz(),
            "image_build_date": os.environ.get("IMAGE_BUILD_DATE", ""),
            "uptime": uptime.boottime().isoformat(),
            "loadAverage": "{:.2f}, {:.2f}, {:.2f}".format(*os.getloadavg()),
        }
    )
