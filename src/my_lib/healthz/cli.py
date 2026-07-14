#!/usr/bin/env python3
"""healthz CLI の共通ランナー

各アプリの healthz エントリポイントが個別に持っていた
docopt → logger 初期化 → 設定読み込み → HealthzTarget 構築 → 判定 → exit
の骨格を共通化する。アプリ側は Usage docstring と HealthzCliSpec の定義だけを持つ。

使用例::

    #!/usr/bin/env python3
    \"\"\"
    Liveness のチェックを行います

    Usage:
      healthz.py [-c CONFIG] [-p PORT] [-D]

    Options:
      -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
      -p PORT           : WEB サーバのポートを指定します。[default: 5000]
      -D                : デバッグモードで動作します。
    \"\"\"

    import my_lib.healthz
    import my_lib.healthz.cli


    def _targets(config, args):
        return [
            my_lib.healthz.HealthzTarget(
                name="scheduler",
                liveness_file=pathlib.Path(config["liveness"]["file"]["scheduler"]),
                interval=10,
            ),
        ]


    SPEC = my_lib.healthz.cli.HealthzCliSpec(
        logger_name="app.example",
        targets_builder=_targets,
        use_http_port=True,
    )

    if __name__ == "__main__":
        my_lib.healthz.cli.run(SPEC, __doc__)
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

import docopt

import my_lib.config
import my_lib.container_util
import my_lib.healthz
import my_lib.logger

# 設定読み込み。(config_file, docopt args) を受けて設定オブジェクトを返す
ConfigLoader: TypeAlias = Callable[[str, dict[str, Any]], Any]
# Liveness チェック対象の構築。(config, docopt args) を受けて対象リストを返す
TargetsBuilder: TypeAlias = Callable[[Any, dict[str, Any]], "list[my_lib.healthz.HealthzTarget]"]
# 追加チェック。(config, docopt args) を受けて正常なら True を返す
ExtraCheck: TypeAlias = Callable[[Any, dict[str, Any]], bool]
# 失敗時フック。(config, docopt args, 失敗した対象名のリスト) を受ける (Slack 通知等)
FailureHandler: TypeAlias = Callable[[Any, dict[str, Any], list[str]], None]
# HTTP ポートチェックの適用可否。(config, docopt args) を受けて適用するなら True を返す
HttpPortEnabled: TypeAlias = Callable[[Any, dict[str, Any]], bool]


@dataclass(frozen=True)
class HealthzCliSpec:
    """healthz CLI の構成定義

    Attributes:
        logger_name: my_lib.logger.init() に渡すロガー名
        targets_builder: Liveness チェック対象を構築する関数。
            未知の動作モード等は ValueError を送出すると exit code 1 で終了する
        config_loader: 設定読み込み関数。None なら my_lib.config.load(config_file) を使う
        use_http_port: docopt の -p を HTTP ポートチェックに使うか
        http_port_enabled: -p の適用可否を動的に判定する関数 (動作モードで
            WEB サーバの有無が変わるアプリ用)。None なら常に適用
        extra_checks: Liveness 以外の追加チェック (メトリクス DB のセッション状態等)。
            失敗すると関数名が失敗対象として記録される
        failure_handler: チェック失敗時のフック (Slack 通知等)。
            起動直後の通知抑制には within_startup_grace() を併用する

    """

    logger_name: str
    targets_builder: TargetsBuilder
    config_loader: ConfigLoader | None = None
    use_http_port: bool = False
    http_port_enabled: HttpPortEnabled | None = None
    extra_checks: tuple[ExtraCheck, ...] = ()
    failure_handler: FailureHandler | None = None


def within_startup_grace(grace_sec: float) -> bool:
    """コンテナ起動直後の猶予期間内かどうかを返す

    起動直後は liveness ファイルがまだ無いのが正常なため、
    failure_handler での失敗通知を抑制する用途に使う。

    Args:
        grace_sec: 猶予期間 (秒)

    Returns:
        猶予期間内なら True

    """
    uptime = my_lib.container_util.get_uptime()
    if uptime <= grace_sec:
        logging.info("Within startup grace period (%.1f sec), skipping notification.", uptime)
        return True
    return False


def run(spec: HealthzCliSpec, doc: str) -> None:
    """healthz CLI を実行する

    チェックがすべて成功したら exit code 0、失敗があれば 1 で終了する。

    Args:
        spec: CLI の構成定義
        doc: docopt に渡す Usage docstring。少なくとも -c と -D、
            use_http_port=True の場合は -p を定義していること

    """
    args = docopt.docopt(doc)
    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init(spec.logger_name, level=logging.DEBUG if debug_mode else logging.INFO)
    logging.info("設定ファイル: %s", config_file)

    if spec.config_loader is not None:
        config = spec.config_loader(config_file, args)
    else:
        config = my_lib.config.load(config_file)

    try:
        targets = spec.targets_builder(config, args)
    except ValueError:
        logging.exception("Liveness チェック対象の構築に失敗しました")
        sys.exit(1)

    http_port: int | None = None
    if spec.use_http_port and (spec.http_port_enabled is None or spec.http_port_enabled(config, args)):
        http_port = int(args["-p"])

    failed = my_lib.healthz.check_liveness_all_with_ports(targets, http_port=http_port)

    for check in spec.extra_checks:
        if not check(config, args):
            failed.append(getattr(check, "__name__", "extra_check"))

    if not failed:
        logging.info("OK.")
        sys.exit(0)

    logging.error("NG: %s", ", ".join(failed))
    if spec.failure_handler is not None:
        spec.failure_handler(config, args, failed)
    sys.exit(1)
