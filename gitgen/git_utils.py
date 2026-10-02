import subprocess


def run_git_command(args: list[str]) -> tuple[int, str, str]:
    """
    Git 명령어를 실행하고 (returncode, stdout, stderr)를 반환합니다.
    
    Args: 
        args: git [args] 형태로 실행할 명령어 리스트
              (명령어를 분리 전달해서 Command Injection을 방어)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,  # stdout과 stderr을 파이썬 내부로 캡처
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

    return "main"


def get_git_status() -> dict:
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
            else: # Safety Fallback
                files.append(line)

    return {
        "files": files,
        "count": len(files),
        "raw": stdout,
    }


def get_git_diff() -> dict:
    """
    git diff 결과를 수집합니다.
    - Staged 변경 사항 (git diff --cached)
    - Unstaged 변경 사항 (git diff)
    둘 다 수집하여 통합 diff 및 줄 수를 계산합니다.
    """
    diff_parts = []

    # 1. Staged diff
    code_staged, staged_diff, _ = run_git_command(["diff", "--cached"])
    if code_staged == 0 and staged_diff:
        diff_parts.append("# [Staged Changes]\n" + staged_diff)

    # 2. Unstaged diff
    code_unstaged, unstaged_diff, _ = run_git_command(["diff"])
    if code_unstaged == 0 and unstaged_diff:
        diff_parts.append("# [Unstaged Changes]\n" + unstaged_diff)

    full_diff = "\n\n".join(diff_parts).strip()
    line_count = len(full_diff.splitlines()) if full_diff else 0

    return {
        "diff": full_diff,
        "line_count": line_count,
        "staged_diff": staged_diff if code_staged == 0 else "",
        "unstaged_diff": unstaged_diff if code_unstaged == 0 else "",
    }
