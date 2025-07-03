#!/usr/bin/env python3
import contextlib
import os
import tracemalloc
from pathlib import Path

import psutil
import uptime

import flask
import my_lib.flask_util
import my_lib.time
import my_lib.webapp.config

blueprint = flask.Blueprint("webapp-util", __name__)

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
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage("/")

    cpu_temp = None
    with contextlib.suppress(FileNotFoundError, ValueError, PermissionError):
        cpu_temp = float(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000.0

    result = {
        "date": my_lib.time.now().isoformat(),
        "timezone": my_lib.time.get_tz(),
        "image_build_date": os.environ.get("IMAGE_BUILD_DATE", ""),
        "uptime": uptime.boottime().isoformat(),
        "load_average": "{:.2f}, {:.2f}, {:.2f}".format(*os.getloadavg()),
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_usage_percent": memory_info.percent,
        "memory_free_mb": round(memory_info.available / 1024 / 1024),
        "disk_usage_percent": round((disk_info.used / disk_info.total) * 100, 1),
        "disk_free_mb": round(disk_info.free / 1024 / 1024),
        "process_count": len(psutil.pids()),
    }

    if cpu_temp is not None:
        result["cpu_temperature"] = round(cpu_temp, 1)

    return flask.jsonify(result)
