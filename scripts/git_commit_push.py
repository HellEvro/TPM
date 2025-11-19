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
        encoding='utf-8',
        errors='replace',
    )
    return result


def git_pull_with_merge() -> None:
    """Выполняет git pull с merge для получения удаленных изменений."""
    # Сначала получаем удаленные изменения
    fetch_result = run_git_command(["git", "fetch"])
    if fetch_result.returncode != 0:
        print((fetch_result.stderr or "").strip() or "Не удалось получить удаленные изменения.")
        sys.exit(fetch_result.returncode)
    
    # Проверяем, есть ли удаленные коммиты
    check_result = run_git_command(["git", "rev-list", "--count", "HEAD..@{upstream}"])
    has_remote_commits = False
    if check_result.returncode == 0 and check_result.stdout:
        try:
            count = int(check_result.stdout.strip())
            has_remote_commits = count > 0
        except ValueError:
            pass
    
    if has_remote_commits:
        print("Обнаружены удаленные коммиты. Выполняю merge...")
        # Выполняем merge с стратегией --no-edit для автоматического merge commit
        merge_result = run_git_command(["git", "pull", "--no-rebase", "--no-edit"])
        if merge_result.returncode != 0:
            print((merge_result.stderr or "").strip() or "Ошибка при merge удаленных изменений.")
            print("Возможно, требуется разрешить конфликты вручную.")
            sys.exit(merge_result.returncode)
        if merge_result.stdout and merge_result.stdout.strip():
            print(merge_result.stdout.strip())


def ensure_changes_present() -> None:
    """Exit early if there are no changes to commit."""
    status = run_git_command(["git", "status", "--porcelain"])
    if status.returncode != 0:
        print((status.stderr or "").strip() or "Не удалось получить статус репозитория.")
        sys.exit(status.returncode)

    if not (status.stdout and status.stdout.strip()):
        print("Изменения отсутствуют — коммит не требуется.")
        sys.exit(0)


def git_add_all() -> None:
    result = run_git_command(["git", "add", "-A"])
    if result.returncode != 0:
        print((result.stderr or "").strip() or "Не удалось подготовить файлы к коммиту.")
        sys.exit(result.returncode)


def git_commit(message: str) -> None:
    result = run_git_command(["git", "commit", "-m", message])
    if result.returncode != 0:
        print((result.stderr or "").strip() or "Коммит не выполнен.")
        sys.exit(result.returncode)
    if result.stdout and result.stdout.strip():
        print(result.stdout.strip())


def git_push() -> None:
    result = run_git_command(["git", "push"])
    if result.returncode != 0:
        print((result.stderr or "").strip() or "Push завершился с ошибкой.")
        sys.exit(result.returncode)
    if result.stdout and result.stdout.strip():
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
    # Сначала получаем удаленные изменения и делаем merge
    git_pull_with_merge()
    # Проверяем наличие локальных изменений
    ensure_changes_present()
    git_add_all()
    git_commit(args.message)
    git_push()


if __name__ == "__main__":
    main()

