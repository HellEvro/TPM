#!/usr/bin/env python3
"""Utility script to stage, commit, and push repository changes.

Example:
    python scripts/git_commit_push.py "Refactor bot history storage"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Sequence


def run_git_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command, returning the completed process object."""
    result = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=True,
    )
    return result


def ensure_changes_present() -> None:
    """Exit early if there are no changes to commit."""
    status = run_git_command(["git", "status", "--porcelain"])
    if status.returncode != 0:
        print(status.stderr.strip() or "Не удалось получить статус репозитория.")
        sys.exit(status.returncode)

    if not status.stdout.strip():
        print("Изменения отсутствуют — коммит не требуется.")
        sys.exit(0)


def git_add_all() -> None:
    result = run_git_command(["git", "add", "-A"])
    if result.returncode != 0:
        print(result.stderr.strip() or "Не удалось подготовить файлы к коммиту.")
        sys.exit(result.returncode)


def git_commit(message: str) -> None:
    result = run_git_command(["git", "commit", "-m", message])
    if result.returncode != 0:
        print(result.stderr.strip() or "Коммит не выполнен.")
        sys.exit(result.returncode)
    if result.stdout.strip():
        print(result.stdout.strip())


def git_push() -> None:
    result = run_git_command(["git", "push"])
    if result.returncode != 0:
        print(result.stderr.strip() or "Push завершился с ошибкой.")
        sys.exit(result.returncode)
    if result.stdout.strip():
        print(result.stdout.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ставит изменения в git, коммитит и пушит их.",
    )
    parser.add_argument(
        "message",
        help="Описание всех изменений, которые сделал агент.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_changes_present()
    git_add_all()
    git_commit(args.message)
    git_push()


if __name__ == "__main__":
    main()

