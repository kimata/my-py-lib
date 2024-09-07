#!/usr/bin/env python3
"""
YAML 型式で定義された設定ファイルを読み込みます．

Usage:
  config.py [-c CONFIG] [-S] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -S                : YAML 記述をもとにして，JSON Schema の雛形を生成します．
  -d                : デバッグモードで動作します．
"""

import json
import logging
import pathlib

import genson
import yaml

CONFIG_PATH = "config.yaml"


def load(config_path=CONFIG_PATH):
    config_path = pathlib.Path(config_path).resolve()

    logging.info("Load config: %s", config_path)

    with config_path.open(mode="r") as file:
        return yaml.load(file, Loader=yaml.SafeLoader)


# NOTE: スキーマの雛形を生成
def generate_schema(config_path):
    with pathlib.Path(config_path).open() as file:
        builder = genson.SchemaBuilder()
        builder.add_object(yaml.load(file, Loader=yaml.SafeLoader))

        print(json.dumps(builder.to_schema(), indent=4))


if __name__ == "__main__":
    import pprint

    import docopt
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    schema_mode = args["-S"]
    debug_mode = args["-d"]

    my_lib.logger.init("my-lib.config", level=logging.DEBUG if debug_mode else logging.INFO)

    if schema_mode:
        generate_schema(config_file)
    else:
        pprint.pprint(load(config_file))
