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
import re
from typing import Any

import genson
import jsonschema
import yaml

CONFIG_PATH: str = "config.yaml"


class ConfigValidationError(Exception):
    """YAML 設定ファイルの検証エラー."""

    def __init__(self, message: str, details: str) -> None:
        """例外を初期化する。

        Args:
            message: エラーメッセージ
            details: 詳細なエラー情報

        """
        super().__init__(message)
        self.details = details


class ConfigParseError(Exception):
    """YAML パースエラー."""

    def __init__(self, message: str, details: str) -> None:
        """例外を初期化する。

        Args:
            message: エラーメッセージ
            details: 詳細なエラー情報

        """
        super().__init__(message)
        self.details = details


class ConfigFileNotFoundError(Exception):
    """設定ファイルが見つからないエラー."""

    def __init__(self, message: str, details: str) -> None:
        """例外を初期化する。

        Args:
            message: エラーメッセージ
            details: 詳細なエラー情報

        """
        super().__init__(message)
        self.details = details


def _format_path(path: list[str | int]) -> str:
    """エラーパスを人間が読みやすい形式に変換."""
    if not path:
        return "ルート"

    formatted_parts: list[str] = []
    for part in path:
        if isinstance(part, int):
            formatted_parts.append(f"[{part}]")
        elif formatted_parts:
            formatted_parts.append(f".{part}")
        else:
            formatted_parts.append(str(part))

    return "".join(formatted_parts)


def _format_value(value: Any, max_length: int = 50) -> str:
    """値を表示用にフォーマット."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        display = f'"{value}"'
    elif isinstance(value, dict):
        display = "{...}" if value else "{}"
    elif isinstance(value, list):
        display = "[...]" if value else "[]"
    else:
        display = str(value)

    if len(display) > max_length:
        return display[: max_length - 3] + "..."
    return display


def _get_type_name_jp(python_type: str) -> str:
    """JSON Schema の型名を日本語に変換."""
    type_names: dict[str, str] = {
        "string": "文字列",
        "integer": "整数",
        "number": "数値",
        "boolean": "真偽値",
        "object": "オブジェクト",
        "array": "配列",
        "null": "null",
    }
    return type_names.get(python_type, python_type)


def _get_python_type_jp(instance: Any) -> str:
    """Python の型名を日本語に変換."""
    actual_type = type(instance).__name__
    type_map = {
        "str": "文字列",
        "int": "整数",
        "float": "数値",
        "bool": "真偽値",
        "dict": "オブジェクト",
        "list": "配列",
        "NoneType": "null",
    }
    return type_map.get(actual_type, actual_type)


def _find_yaml_line(yaml_lines: list[str], path: list[str | int]) -> int | None:  # noqa: C901, PLR0912
    """YAML ファイル内でパスに対応する行番号を見つける."""
    if not path:
        return None

    current_indent = -1
    path_index = 0

    for line_num, line in enumerate(yaml_lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(stripped)

        if indent <= current_indent and path_index > 0:
            current_indent = -1
            path_index_reset = 0
            for _j, check_line in enumerate(yaml_lines[: line_num + 1]):
                check_stripped = check_line.lstrip()
                if not check_stripped or check_stripped.startswith("#"):
                    continue
                check_indent = len(check_line) - len(check_stripped)
                if check_indent <= current_indent:
                    path_index_reset = 0
                    current_indent = -1
                target = path[path_index_reset]
                if isinstance(target, str):
                    pattern = rf"^{re.escape(target)}\s*:"
                    if re.match(pattern, check_stripped):
                        current_indent = check_indent
                        path_index_reset += 1
                        if path_index_reset >= len(path):
                            break
            path_index = path_index_reset
            if path_index >= len(path):
                continue

        target = path[path_index]
        if isinstance(target, str):
            pattern = rf"^{re.escape(target)}\s*:"
            if re.match(pattern, stripped):
                current_indent = indent
                path_index += 1
                if path_index >= len(path):
                    return line_num
        elif isinstance(target, int):
            if stripped.startswith("-"):
                pass

    return None


def _extract_yaml_context(yaml_lines: list[str], path: list[str | int], context: int = 2) -> str:
    """YAML ファイルから該当箇所とその周辺を抽出."""
    line_num = _find_yaml_line(yaml_lines, path)

    if line_num is None and path:
        line_num = _find_yaml_line(yaml_lines, path[:-1])

    if line_num is None:
        return ""

    start = max(0, line_num - context)
    end = min(len(yaml_lines), line_num + context + 1)

    lines_output: list[str] = []
    for i in range(start, end):
        marker = ">>>" if i == line_num else "   "
        lines_output.append(f"  {marker} {i + 1:4d} | {yaml_lines[i]}")

    return "\n".join(lines_output)


def _format_required_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str]
) -> None:
    """Format required error."""
    required_props = error.validator_value
    if isinstance(required_props, str):
        required_props = [required_props]

    # 実際に不足しているプロパティを計算
    existing_keys = set(error.instance.keys()) if isinstance(error.instance, dict) else set()
    missing = [p for p in required_props if p not in existing_keys]

    # 不足がない場合は早期リターン（論理的にはあり得ないが防御的に）
    if not missing:
        return

    missing_str = ", ".join(f'"{p}"' for p in missing)
    lines.append("  問題: 必須プロパティが不足しています")
    lines.append(f"  不足: {missing_str}")
    if isinstance(error.instance, dict):
        existing = ", ".join(f'"{k}"' for k in sorted(error.instance)) if error.instance else "(なし)"
        lines.append(f"  現在の定義: {existing}")
    required_str = ", ".join(f'"{p}"' for p in sorted(required_props))
    lines.append(f"  必須プロパティ: {required_str}")


def _format_additional_properties_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str]
) -> None:
    """Format additionalProperties error."""
    allowed = set(error.schema.get("properties", {}))
    if isinstance(error.instance, dict):
        extra = [k for k in error.instance if k not in allowed]
        extra_str = ", ".join(f'"{k}"' for k in extra)
        lines.append("  問題: 定義されていないプロパティがあります")
        lines.append(f"  過剰: {extra_str}")
        existing = ", ".join(f'"{k}"' for k in sorted(error.instance)) if error.instance else "(なし)"
        lines.append(f"  現在の定義: {existing}")
        if allowed:
            allowed_str = ", ".join(f'"{k}"' for k in sorted(allowed))
            lines.append(f"  許可されているプロパティ: {allowed_str}")


def _format_type_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str]
) -> None:
    """Format type error."""
    expected = error.validator_value
    expected_str = (
        " または ".join(_get_type_name_jp(t) for t in expected)
        if isinstance(expected, list)
        else _get_type_name_jp(expected)
    )
    actual_type_jp = _get_python_type_jp(error.instance)

    lines.append("  問題: 型が不正です")
    lines.append(f"  期待: {expected_str}")
    lines.append(f"  実際: {actual_type_jp} ({_format_value(error.instance)})")


def _format_enum_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str]
) -> None:
    """Format enum error."""
    allowed_str = ", ".join(_format_value(v) for v in error.validator_value)
    lines.append("  問題: 許可されていない値です")
    lines.append(f"  指定値: {_format_value(error.instance)}")
    lines.append(f"  許可される値: {allowed_str}")


def _format_pattern_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str]
) -> None:
    """Format pattern error."""
    lines.append("  問題: 値がパターンに一致しません")
    lines.append(f"  指定値: {_format_value(error.instance)}")
    lines.append(f"  パターン: {error.validator_value}")


def _format_length_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str], *, is_min: bool
) -> None:
    """Format minLength/maxLength error."""
    problem = "短すぎます" if is_min else "長すぎます"
    limit_label = "最小長" if is_min else "最大長"
    length = len(error.instance) if isinstance(error.instance, str) else 0
    lines.append(f"  問題: 文字列が{problem}")
    lines.append(f"  指定値: {_format_value(error.instance)} (長さ: {length})")
    lines.append(f"  {limit_label}: {error.validator_value}")


def _format_range_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str], *, is_min: bool
) -> None:
    """Format minimum/maximum error."""
    problem = "小さすぎます" if is_min else "大きすぎます"
    limit_label = "最小値" if is_min else "最大値"
    lines.append(f"  問題: 値が{problem}")
    lines.append(f"  指定値: {error.instance}")
    lines.append(f"  {limit_label}: {error.validator_value}")


def _format_items_error(
    error: jsonschema.exceptions.ValidationError, lines: list[str], *, is_min: bool
) -> None:
    """Format minItems/maxItems error."""
    problem = "少なすぎます" if is_min else "多すぎます"
    limit_label = "最小要素数" if is_min else "最大要素数"
    count = len(error.instance) if isinstance(error.instance, list) else 0
    lines.append(f"  問題: 配列の要素数が{problem}")
    lines.append(f"  現在の要素数: {count}")
    lines.append(f"  {limit_label}: {error.validator_value}")


def _format_simple_error(lines: list[str], problem: str, instance: Any) -> None:
    """シンプルなエラーをフォーマット."""
    lines.append(f"  問題: {problem}")
    lines.append(f"  指定値: {_format_value(instance)}")


def _format_validation_error(  # noqa: C901, PLR0912
    error: jsonschema.exceptions.ValidationError,
    yaml_lines: list[str],
) -> str:
    """ValidationError を日本語のわかりやすいメッセージに変換."""
    path = list(error.path)
    path_str = _format_path(path)
    validator = error.validator

    lines: list[str] = [f"  場所: {path_str}"]

    if validator == "required":
        _format_required_error(error, lines)
    elif validator == "additionalProperties":
        _format_additional_properties_error(error, lines)
    elif validator == "type":
        _format_type_error(error, lines)
    elif validator == "enum":
        _format_enum_error(error, lines)
    elif validator == "pattern":
        _format_pattern_error(error, lines)
    elif validator == "minLength":
        _format_length_error(error, lines, is_min=True)
    elif validator == "maxLength":
        _format_length_error(error, lines, is_min=False)
    elif validator == "minimum":
        _format_range_error(error, lines, is_min=True)
    elif validator == "maximum":
        _format_range_error(error, lines, is_min=False)
    elif validator == "minItems":
        _format_items_error(error, lines, is_min=True)
    elif validator == "maxItems":
        _format_items_error(error, lines, is_min=False)
    elif validator == "uniqueItems":
        _format_simple_error(lines, "配列に重複した要素があります", error.instance)
    elif validator == "format":
        lines.append("  問題: 値のフォーマットが不正です")
        lines.append(f"  指定値: {_format_value(error.instance)}")
        lines.append(f"  期待フォーマット: {error.validator_value}")
    elif validator == "const":
        lines.append("  問題: 値が期待される定数と一致しません")
        lines.append(f"  指定値: {_format_value(error.instance)}")
        lines.append(f"  期待値: {_format_value(error.validator_value)}")
    elif validator in ("oneOf", "anyOf"):
        _format_simple_error(lines, "いずれのスキーマにも一致しません", error.instance)
    elif validator == "not":
        _format_simple_error(lines, "禁止されているスキーマに一致しています", error.instance)
    else:
        lines.append(f"  問題: {error.message}")
        lines.append(f"  指定値: {_format_value(error.instance)}")

    context = _extract_yaml_context(yaml_lines, path)
    if context:
        lines.append("  該当箇所:")
        lines.append(context)

    return "\n".join(lines)


def _format_yaml_error(error: yaml.YAMLError, yaml_content: str) -> str:
    """YAML パースエラーを日本語でわかりやすく表示."""
    yaml_lines = yaml_content.splitlines()

    lines: list[str] = [
        "=" * 60,
        "YAML 構文エラー",
        "=" * 60,
        "",
    ]

    if isinstance(error, yaml.scanner.ScannerError):
        problem = error.problem or "不明なエラー"
        problem_jp = _translate_yaml_problem(problem)

        lines.append(f"  問題: {problem_jp}")

        if error.problem_mark is not None:
            line_num = error.problem_mark.line
            column = error.problem_mark.column
            lines.append(f"  場所: {line_num + 1} 行目、{column + 1} 文字目")

            context_lines = _extract_yaml_lines_around(yaml_lines, line_num)
            if context_lines:
                lines.append("  該当箇所:")
                lines.append(context_lines)

                pointer_line = "  " + " " * 14 + " " * column + "^"
                lines.append(pointer_line)

        if error.context is not None:
            context_jp = _translate_yaml_context(error.context)
            lines.append(f"  補足: {context_jp}")

    elif isinstance(error, yaml.parser.ParserError):
        problem = error.problem if error.problem else "構文エラー"
        problem_jp = _translate_yaml_problem(problem)

        lines.append(f"  問題: {problem_jp}")

        if error.problem_mark is not None:
            line_num = error.problem_mark.line
            column = error.problem_mark.column
            lines.append(f"  場所: {line_num + 1} 行目、{column + 1} 文字目")

            context_lines = _extract_yaml_lines_around(yaml_lines, line_num)
            if context_lines:
                lines.append("  該当箇所:")
                lines.append(context_lines)

        if error.context is not None:
            context_jp = _translate_yaml_context(error.context)
            lines.append(f"  補足: {context_jp}")

    else:
        lines.append(f"  問題: {error!s}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def _translate_yaml_problem(problem: str) -> str:
    """YAML エラーメッセージを日本語に翻訳."""
    translations: dict[str, str] = {
        "mapping values are not allowed here": "この場所ではマッピング値（コロン）は使用できません",
        "could not find expected ':'": "期待されるコロン (:) が見つかりません",
        "expected <block end>, but found": "ブロックの終端が期待されましたが、別のものが見つかりました",
        "while scanning a simple key": "キーをスキャン中にエラーが発生しました",
        "could not find expected key": "期待されるキーが見つかりません",
        "found unexpected ':'": "予期しないコロン (:) が見つかりました",
        "found unexpected end of stream": "予期しないストリームの終端が見つかりました",
        "expected a comment or a line break": "コメントまたは改行が期待されます",
        "found character that cannot start any token": "トークンを開始できない文字が見つかりました",
        "found unknown escape character": "不明なエスケープ文字が見つかりました",
        "expected alphabetic or numeric character": "英数字が期待されます",
    }

    for eng, jp in translations.items():
        if eng in problem:
            return jp

    if "found" in problem and "expected" in problem:
        return f"構文エラー: {problem}"

    return problem


def _translate_yaml_context(context: str) -> str:
    """YAML コンテキストメッセージを日本語に翻訳."""
    translations: dict[str, str] = {
        "while parsing a block mapping": "ブロックマッピングの解析中",
        "while scanning a simple key": "シンプルキーのスキャン中",
        "while parsing a flow mapping": "フローマッピングの解析中",
        "while parsing a flow sequence": "フローシーケンスの解析中",
        "while scanning a quoted scalar": "クォートされたスカラーのスキャン中",
        "while parsing a block collection": "ブロックコレクションの解析中",
    }

    for eng, jp in translations.items():
        if eng in context:
            return jp

    return context


def _extract_yaml_lines_around(yaml_lines: list[str], line_num: int, context: int = 2) -> str:
    """指定行の周辺を抽出."""
    start = max(0, line_num - context)
    end = min(len(yaml_lines), line_num + context + 1)

    lines_output: list[str] = []
    for i in range(start, end):
        marker = ">>>" if i == line_num else "   "
        lines_output.append(f"  {marker} {i + 1:4d} | {yaml_lines[i]}")

    return "\n".join(lines_output)


def validate_config(
    yaml_data: dict[str, Any],
    schema: dict[str, Any],
    yaml_lines: list[str],
) -> None:
    """YAML データをスキーマで検証し、エラーがあれば日本語で詳細を表示."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(yaml_data))

    if not errors:
        return

    error_messages: list[str] = [
        "=" * 60,
        "設定ファイルの検証エラー",
        "=" * 60,
        "",
    ]

    for i, error in enumerate(errors, 1):
        error_messages.append(f"エラー {i}:")
        error_messages.append(_format_validation_error(error, yaml_lines))
        error_messages.append("")

    error_messages.append("=" * 60)

    details = "\n".join(error_messages)
    logging.error("\n%s", details)

    raise ConfigValidationError(
        f"設定ファイルに {len(errors)} 件の検証エラーがあります",
        details,
    )


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


def abs_path(config_path: str | pathlib.Path = CONFIG_PATH) -> pathlib.Path:
    return pathlib.Path(pathlib.Path.cwd(), config_path)


def load(
    config_path: str | pathlib.Path = CONFIG_PATH,
    schema_path: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    config_path_obj = pathlib.Path(config_path).resolve()

    schema_path_obj: pathlib.Path | None = None
    if schema_path is not None:
        schema_path_obj = pathlib.Path(schema_path).resolve()

    schema_info = f" (schema: {schema_path_obj})" if schema_path_obj is not None else ""
    logging.info("Load config: %s%s", config_path_obj, schema_info)

    if not config_path_obj.exists():
        details_lines = [
            "=" * 60,
            "設定ファイルが見つかりません",
            "=" * 60,
            "",
            f"  ファイルパス: {config_path_obj}",
            "",
            "  確認事項:",
            "    - ファイルパスが正しいか確認してください",
            "    - ファイルが存在するか確認してください",
            "    - ファイル名のスペルミスがないか確認してください",
            "",
            "=" * 60,
        ]
        details = "\n".join(details_lines)
        logging.error("\n%s", details)
        raise ConfigFileNotFoundError(
            f"設定ファイルが見つかりません: {config_path_obj}",
            details,
        )

    with config_path_obj.open() as file:
        yaml_content = file.read()

    yaml_lines = yaml_content.splitlines()

    try:
        yaml_data: dict[str, Any] = yaml.load(yaml_content, Loader=yaml.SafeLoader)
    except yaml.YAMLError as e:
        details = _format_yaml_error(e, yaml_content)
        logging.error("\n%s", details)  # noqa: TRY400
        raise ConfigParseError("YAML ファイルの構文エラー", details) from e

    if schema_path_obj is not None:
        with schema_path_obj.open() as file:
            schema: dict[str, Any] = json.load(file)
            validate_config(yaml_data, schema, yaml_lines)

    if isinstance(yaml_data, dict):
        yaml_data["base_dir"] = abs_path(config_path).parent

    return yaml_data


# NOTE: スキーマの雛形を生成
def generate_schema(config_path: str | pathlib.Path) -> None:
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
