"""Read Git state without changing the index, worktree, or remote."""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from .errors import GitgenError


@dataclass(frozen=True)
class Change:
    status: str
    path: str
    old_path: str | None = None

    @property
    def untracked(self) -> bool:
        return self.status == "??"

    def layers(self) -> list[str]:
        # Only staged changes are analyzed so the draft matches the next commit.
        if self.untracked or self.status[0] == " ":
            return []
        return ["staged"]


@dataclass(frozen=True)
class GitContext:
    root: Path
    changes: list[Change]


def run_git(root: Path, arguments: list[str]) -> bytes:
    env = os.environ.copy()
    # Do not let inherited Git overrides inspect a different repository/index.
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key)
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    try:
        result = subprocess.run(
            ["git", "--literal-pathspecs", "-c", "core.quotePath=false", *arguments],
            cwd=root, env=env, capture_output=True, timeout=30, check=False,
        )
    except FileNotFoundError:
        raise GitgenError("Git을 찾을 수 없습니다. Git 설치와 PATH를 확인하세요.") from None
    except subprocess.TimeoutExpired:
        raise GitgenError("Git 명령이 30초 안에 완료되지 않았습니다.") from None
    except OSError:
        raise GitgenError("Git 실행에 실패했습니다. 경로와 접근 권한을 확인하세요.") from None
    if result.returncode:
        # stderr can contain repository content or credentials; do not echo it.
        raise GitgenError(
            f"git {arguments[0]} 실패(종료 코드 {result.returncode}). "
            "저장소 상태와 경로·접근 권한을 확인하세요."
        )
    return result.stdout


def parse_status(raw: bytes) -> list[Change]:
    fields = raw.split(b"\0")
    changes = []
    position = 0
    while position < len(fields) and fields[position]:
        record = fields[position]
        position += 1
        if len(record) < 4 or record[2:3] != b" ":
            raise GitgenError("Git 상태 출력을 해석할 수 없습니다.")
        status = record[:2].decode("ascii", errors="replace")
        path = os.fsdecode(record[3:])
        old_path = None
        if "R" in status or "C" in status:
            if position >= len(fields) or not fields[position]:
                raise GitgenError("Git 이름 변경 정보를 해석할 수 없습니다.")
            old_path = os.fsdecode(fields[position])
            position += 1
        if "U" in status or status in {"AA", "DD"}:
            raise GitgenError("병합 충돌이 있습니다. 충돌을 해결한 뒤 다시 실행하세요.")
        changes.append(Change(status, path, old_path))
    return sorted(changes, key=lambda change: change.path)


def collect(root: Path) -> GitContext:
    root = root.resolve()
    if not (root / ".git").exists():
        raise GitgenError("Git 저장소 루트(.git이 있는 폴더)에서 실행하세요.")
    raw = run_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--renames"])
    return GitContext(root, parse_status(raw))


def read_diff(context: GitContext, change: Change, layer: str) -> str:
    arguments = ["diff"]
    if layer == "staged":
        arguments.append("--cached")
    arguments += [
        "--no-ext-diff", "--no-textconv", "--no-color", "--no-renames",
        "--submodule=short", "--ignore-submodules=none", "--unified=3", "--",
        change.path,
    ]
    if change.old_path:
        arguments.append(change.old_path)
    return run_git(context.root, arguments).decode("utf-8", errors="replace")
