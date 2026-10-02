"""
gitgen - AI 기반 Git 커밋 메시지 및 PR 초안 자동 생성 패키지
"""

__version__ = "1.0.0"
APP_VERSION = __version__

from gitgen.config import (
    DEFAULT_BASE_URL,
    DEFAULT_COMMIT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PR_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    load_env,
)
from gitgen.ai_client import AIClient
from gitgen.git_utils import (
    get_current_branch,
    get_git_diff,
    get_git_status,
    is_git_repo,
    run_git_command,
)
from gitgen.prompts import get_commit_prompt, get_pr_prompt
from gitgen.validator import (
    apply_safe_mode,
    mask_sensitive_info,
    validate_and_format_commit,
    validate_and_format_pr,
)

__all__ = [
    "__version__",
    "APP_VERSION",
    "AIClient",
    "apply_safe_mode",
    "get_commit_prompt",
    "get_current_branch",
    "get_git_diff",
    "get_git_status",
    "get_pr_prompt",
    "is_git_repo",
    "load_env",
    "mask_sensitive_info",
    "run_git_command",
    "validate_and_format_commit",
    "validate_and_format_pr",
]
