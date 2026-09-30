from typing import List


def get_commit_prompt(changed_files: List[str], diff_text: str) -> List[dict]:
    """
    커밋 메시지 생성을 위한 AI 프롬프트를 구성합니다.
    """
    file_list_str = "\n".join(f"- {f}" for f in changed_files) if changed_files else "없음"

    system_content = (
        "당신은 실무 소프트웨어 개발자를 위한 Git 커밋 메시지 자동 생성 어시스턴트입니다.\n"
        "주어진 Git 변경 파일 목록과 git diff 내용을 분석하여 명확하고 실무 표준에 부합하는 커밋 메시지를 작성하세요.\n\n"
        "작성 규칙:\n"
        "1. 커밋 제목은 1줄로 작성하며, 50자 이내 권장(최대 72자)입니다.\n"
        "2. Conventional Commits 양식(feat, fix, refactor, docs, chore, test 등)을 따르세요.\n"
        "   예: feat: Git 변경 사항 기반 커밋 메시지 자동 생성 기능 추가\n"
        "3. 커밋 제목 다음 줄은 반드시 한 줄의 빈 줄을 두세요.\n"
        "4. 커밋 본문에는 다음 내용이 반드시 포함되어야 합니다:\n"
        "   - 변경된 주요 파일(또는 모듈) 1~3개 언급\n"
        "   - 핵심 변경 사항 1~3개를 불릿('- ')으로 간결하게 요약\n"
        "5. 마크다운 코드 블록(```)이나 부가적인 설명(예: '여기에 커밋 메시지가 있습니다')은 절대로 출력하지 말고 오직 커밋 메시지만 반환하세요."
    )

    user_content = (
        f"[변경된 파일 목록]\n{file_list_str}\n\n"
        f"[Git Diff 내용]\n{diff_text}\n\n"
        "위 변경 사항을 기반으로 커밋 메시지를 작성해주세요."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def get_pr_prompt(branch_name: str, changed_files: List[str], diff_text: str) -> List[dict]:
    """
    PR 제목 및 본문 초안 생성을 위한 AI 프롬프트를 구성합니다.
    """
    file_list_str = "\n".join(f"- {f}" for f in changed_files) if changed_files else "없음"

    system_content = (
        "당신은 실무 소프트웨어 개발자를 위한 GitHub Pull Request(PR) 초안 작성 어시스턴트입니다.\n"
        "주어진 브랜치 정보, 변경 파일 목록, git diff를 분석하여 PR 제목과 PR 본문을 작성하세요.\n\n"
        "작성 규칙:\n"
        "1. PR 제목은 1줄로 작성하며, 최대 80자를 넘지 않아야 합니다.\n"
        "   형식: Title: <PR 제목>\n"
        "   예: Title: feat: 커밋/PR 자동 생성 기능 추가\n"
        "2. PR 본문은 반드시 다음 3가지 섹션 헤더를 순서대로 포함해야 합니다:\n"
        "   ## Why\n"
        "   ## What\n"
        "   ## How to Test\n"
        "3. 각 섹션(Why, What, How to Test) 아래에는 최소 1개 이상의 불릿('- ')을 포함하여 내용을 구체적으로 작성하세요.\n"
        "   - Why: 변경 배경 및 목적 (왜 이 작업이 필요한지)\n"
        "   - What: 핵심 변경 사항 요약 (무엇을 어떻게 바꿨는지)\n"
        "   - How to Test: 테스트 방법 및 검증 절차 (어떻게 테스트하는지)\n"
        "4. 마크다운 코드 블록(```)으로 전체를 감싸지 마세요."
    )

    user_content = (
        f"[현재 브랜치]: {branch_name}\n\n"
        f"[변경된 파일 목록]\n{file_list_str}\n\n"
        f"[Git Diff 내용]\n{diff_text}\n\n"
        "위 변경 사항을 기반으로 PR Title과 PR 본문을 작성해주세요."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
