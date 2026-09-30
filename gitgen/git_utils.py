import subprocess
from typing import Dict, List, Tuple


def run_git_command(args: List[str]) -> Tuple[int, str, str]:
    """Git 명령어를 실행하고 (returncode, stdout, stderr)를 반환합니다."""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 1, "", "git 명령어를 찾을 수 없습니다. Git이 설치되어 있는지 확인하세요."
    except Exception as e:
        return 1, "", str(e)


def is_git_repo() -> bool:
    """현재 디렉토리가 Git 저장소 내부인지 확인합니다."""
    code, stdout, _ = run_git_command(["rev-parse", "--is-inside-work-tree"])
    return code == 0 and stdout == "true"


def get_current_branch() -> str:
    """현재 브랜치 이름을 가져옵니다."""
    code, stdout, _ = run_git_command(["branch", "--show-current"])
    if code == 0 and stdout:
        return stdout

    # detached HEAD 또는 초기 커밋 전 상황 대응
    code, stdout, _ = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    if code == 0 and stdout:
        return stdout
    return "main"


def get_git_status() -> Dict:
    """
    git status --porcelain 명령으로 변경된 파일 목록을 가져옵니다.
    반환값:
        {
            "files": list[str],
            "count": int,
            "raw": str
        }
    """
    code, stdout, stderr = run_git_command(["status", "--porcelain"])
    if code != 0:
        return {"files": [], "count": 0, "raw": "", "error": stderr}

    files = []
    if stdout:
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # 'M filename', '?? filename', 'A  filename' 형태
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                files.append(parts[1])
            else:
                files.append(line)

    return {
        "files": files,
        "count": len(files),
        "raw": stdout,
    }


def get_git_diff() -> Dict:
    """
    git diff 결과를 수집합니다.
    - Staged 변경 사항 (git diff --cached)
    - Unstaged 변경 사항 (git diff)
    둘 다 수집하여 통합 diff 및 줄 수를 계산합니다.
    """
    # 1. Staged diff
    _, staged_diff, _ = run_git_command(["diff", "--cached"])

    # 2. Unstaged diff
    _, unstaged_diff, _ = run_git_command(["diff"])

    diff_parts = []
    if staged_diff:
        diff_parts.append("# [Staged Changes]\n" + staged_diff)
    if unstaged_diff:
        diff_parts.append("# [Unstaged Changes]\n" + unstaged_diff)

    # 3. staged/unstaged diff가 없지만 파일 변경/추가 상태가 있는 경우
    if not staged_diff and not unstaged_diff:
        code_st, stdout_st, _ = run_git_command(["status", "--porcelain"])
        if code_st == 0 and stdout_st:
            diff_parts.append("# [Detected Status Changes / Untracked Files]\n" + stdout_st)

    full_diff = "\n\n".join(diff_parts).strip()
    line_count = len(full_diff.splitlines()) if full_diff else 0

    return {
        "diff": full_diff,
        "line_count": line_count,
        "staged_diff": staged_diff,
        "unstaged_diff": unstaged_diff,
    }
