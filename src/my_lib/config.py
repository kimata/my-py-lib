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

import json
import logging
import pathlib

import genson
import jsonschema
import yaml

CONFIG_PATH = "config.yaml"


def get_data(config, conf_path, suffix_path=[]):  # noqa: B006
    conf = config
    for key in conf_path + suffix_path:
        conf = conf.get(key, None)

    return conf


def get_path(config, conf_path, suffix_path=[]):  # noqa: B006
    return pathlib.Path(get_data(config, conf_path, suffix_path))


def abs_path(config_path=CONFIG_PATH):
    return pathlib.Path(pathlib.Path.cwd(), config_path)


def load(config_path=CONFIG_PATH, schema_path=None):
    config_path = pathlib.Path(config_path).resolve()

    if schema_path is not None:
        schema_path = pathlib.Path(schema_path).resolve()

    logging.info(
        "Load config: %s%s", config_path, f" (schema: {schema_path})" if schema_path is not None else ""
    )

    with config_path.open() as file:
        yaml_data = yaml.load(file, Loader=yaml.SafeLoader)

    if schema_path is not None:
        with schema_path.open() as file:
            schema = json.load(file)

            try:
                jsonschema.validate(instance=yaml_data, schema=schema)
            except jsonschema.exceptions.ValidationError:
                logging.error("設定ファイルのフォーマットに問題があります。")  # noqa: TRY400
                raise

    if isinstance(yaml_data, dict):
        yaml_data["base_dir"] = abs_path(config_path).parent

    return yaml_data


# NOTE: スキーマの雛形を生成
def generate_schema(config_path):
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
