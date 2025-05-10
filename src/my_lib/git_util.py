#!/usr/bin/env python3
"""
Git の管理ステータスを文字列で返すライブラリです．

Usage:
  git_util.py
"""

import datetime
import logging

import git
import zoneinfo


def revision_str():
    repo = git.Repo(".")
    commit = repo.head.commit
    commit_time = datetime.datetime.fromtimestamp(commit.committed_date, tz=datetime.timezone.utc).astimezone(
        zoneinfo.ZoneInfo("Asia/Tokyo")
    )

    return (
        f'Git hash: {commit.hexsha}{" (dirty)" if repo.is_dirty() else ""}\n'
        f'Git date: {commit_time.strftime("%Y-%m-%d %H:%M:%S %Z")}'
    )


if __name__ == "__main__":
    import docopt
    import my_lib.logger

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    logging.info(revision_str())
