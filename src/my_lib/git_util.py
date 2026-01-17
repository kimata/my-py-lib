#!/usr/bin/env python3
"""
Git の管理ステータスを文字列で返すライブラリです。

Usage:
  git_util.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

import git

import my_lib.time


@dataclass(frozen=True)
class RevisionInfo:
    hash: str
    date: datetime.datetime
    is_dirty: bool


def get_revision_info() -> RevisionInfo:
    repo = git.Repo(".")

    commit = repo.head.commit
    commit_time = datetime.datetime.fromtimestamp(commit.committed_date, tz=datetime.UTC).astimezone(
        my_lib.time.get_zoneinfo()
    )

    return RevisionInfo(
        hash=commit.hexsha,
        date=commit_time,
        is_dirty=repo.is_dirty(),
    )


def get_revision_str() -> str:
    revision_info = get_revision_info()

    return (
        f"Git hash: {revision_info.hash}{' (dirty)' if revision_info.is_dirty else ''}\n"
        f"Git date: {revision_info.date.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )


if __name__ == "__main__":
    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    logging.info(get_revision_str())
