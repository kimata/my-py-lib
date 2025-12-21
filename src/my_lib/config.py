#!/usr/bin/env python3
"""
YAML 型式で定義された設定ファイルを読み込むライブラリです。

Usage:
  config.py [-c CONFIG] [-S] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -S                : YAML 記述をもとにして、JSON Schema の雛形を生成します。
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

import genson
import jsonschema
import yaml

CONFIG_PATH: str = "config.yaml"


def get_data(
    config: dict[str, Any], conf_path: list[str], suffix_path: list[str] | None = None
) -> Any:
    if suffix_path is None:
        suffix_path = []
    conf: Any = config
    for key in conf_path + suffix_path:
        conf = conf.get(key, None)

    return conf


def get_path(
    config: dict[str, Any], conf_path: list[str], suffix_path: list[str] | None = None
) -> pathlib.Path:
    if suffix_path is None:
        suffix_path = []
    return pathlib.Path(get_data(config, conf_path, suffix_path))


def abs_path(config_path: str = CONFIG_PATH) -> pathlib.Path:
    return pathlib.Path(pathlib.Path.cwd(), config_path)


def load(config_path: str = CONFIG_PATH, schema_path: str | None = None) -> dict[str, Any]:
    config_path_obj = pathlib.Path(config_path).resolve()

    schema_path_obj: pathlib.Path | None = None
    if schema_path is not None:
        schema_path_obj = pathlib.Path(schema_path).resolve()

    logging.info(
        "Load config: %s%s", config_path_obj, f" (schema: {schema_path_obj})" if schema_path_obj is not None else ""
    )

    with config_path_obj.open() as file:
        yaml_data: dict[str, Any] = yaml.load(file, Loader=yaml.SafeLoader)

    if schema_path_obj is not None:
        with schema_path_obj.open() as file:
            schema: dict[str, Any] = json.load(file)

            try:
                jsonschema.validate(instance=yaml_data, schema=schema)
            except jsonschema.exceptions.ValidationError:
                logging.error("設定ファイルのフォーマットに問題があります。")  # noqa: TRY400
                raise

    if isinstance(yaml_data, dict):
        yaml_data["base_dir"] = abs_path(config_path).parent

    return yaml_data


# NOTE: スキーマの雛形を生成
def generate_schema(config_path: str) -> None:
    with pathlib.Path(config_path).open() as file:
        builder = genson.SchemaBuilder("https://json-schema.org/draft/2020-12/schema")
        builder.add_object(yaml.load(file, Loader=yaml.SafeLoader))

        print(json.dumps(builder.to_schema(), indent=4))  # noqa: T201


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger
    import my_lib.pretty

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    schema_mode = args["-S"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    if schema_mode:
        generate_schema(config_file)
    else:
        logging.info(my_lib.pretty.format(load(config_file)))
