import re


def mask_sensitive_info(text: str) -> str:
    """
    민감정보(API 키, 토큰, 비밀번호, 이메일 등)를 감지하여 마스킹합니다.
    """
    if not text:
        return text

    masked = text

    # 1. API 키 패턴 (OpenAI, AWS, Google, Github 등)
    # sk-..., ghp_..., AKIA..., AIza...
    masked = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "[MASKED_API_KEY]", masked)
    masked = re.sub(r"ghp_[a-zA-Z0-9]{36}", "[MASKED_GITHUB_TOKEN]", masked)
    masked = re.sub(r"AKIA[0-9A-Z]{16}", "[MASKED_AWS_KEY]", masked)
    masked = re.sub(r"AIza[0-9A-Za-z_\-]{35}", "[MASKED_GOOGLE_KEY]", masked)

    # 2. Key/Secret/Password 변수 할당 패턴
    pattern_secret = r"(?i)(api[_-]?key|token|secret|password|passwd|auth)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
    masked = re.sub(pattern_secret, r"\1=[MASKED_SECRET]", masked)

    # 3. 이메일 주소 패턴
    pattern_email = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    masked = re.sub(pattern_email, "[MASKED_EMAIL]", masked)

    return masked


def apply_safe_mode(
    diff_text: str, changed_files: list[str]
) -> tuple[str, list[str]]:
    """
    안전 모드(safe-mode) 적용:
    민감정보(API Key, 패스워드, 이메일 등) 마스킹
    """
    safe_diff = mask_sensitive_info(diff_text)
    return safe_diff, changed_files


def validate_and_format_commit(commit_text: str) -> str:
    """
    커밋 메시지 형식 검증 및 다듬기:
    - 커밋 제목: 50자 이내 권장(최대 72자). 72자 초과 시 정리.
    - 본문: 변경된 파일 언급 or 불릿 항목 포함 여부 확인 후 서식 다듬기.
    """
    if not commit_text:
        return ""

    # 앞뒤 공백 및 마크다운 코드블록 백틱 제거
    cleaned = commit_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    cleaned = cleaned.strip()

    lines = cleaned.splitlines()
    if not lines:
        return ""

    title = lines[0].strip()
    # 제목 길이 규칙: 최대 72자
    if len(title) > 72:
        title = title[:69] + "..."

    result_lines = [title]
    has_started_body = False

    for line in lines[1:]:
        sline = line.strip()
        if not sline and not has_started_body:
            continue
        if not has_started_body:
            has_started_body = True
            result_lines.append("")  # 제목과 본문 사이 빈 줄
        result_lines.append(line)

    return "\n".join(result_lines).strip()


def validate_and_format_pr(pr_text: str) -> tuple[str, str]:
    """
    PR 제목/본문 형식 검증 및 다듬기:
    - PR 제목: 최대 80자
    - PR 본문: Why, What, How to Test 섹션 헤더 필수 + 각 섹션 최소 1개 불릿 확인 및 보완
    반환: (title, body)
    """
    if not pr_text:
        return "PR 제목이 생성되지 않았습니다.", ""

    cleaned = pr_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    cleaned = cleaned.strip()

    title = ""

    # 'Title:' 또는 'PR Title:' 라인 추출 시도
    lines = cleaned.splitlines()
    title_idx = -1
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if re.match(r"^(#\s*)?(PR\s*)?Title\s*:\s*", line_clean, re.IGNORECASE):
            title = re.sub(r"^(#\s*)?(PR\s*)?Title\s*:\s*", "", line_clean, flags=re.IGNORECASE).strip()
            title_idx = i
            break
        elif line_clean.startswith("# ") and not any(k in line_clean.lower() for k in ["why", "what", "how"]):
            title = line_clean.replace("# ", "").strip()
            title_idx = i
            break

    # 제목을 명시적 태그로 못 찾았을 경우 첫 번째 의미 있는 라인을 제목으로 사용
    if not title and lines:
        for i, line in enumerate(lines):
            line_clean = line.strip()
            if line_clean and not line_clean.startswith("##"):
                title = line_clean
                title_idx = i
                break

    if not title:
        title = "코드 변경 사항 반영"

    # 제목 최대 80자 제한
    if len(title) > 80:
        title = title[:77] + "..."

    # 본문 추출
    remaining_lines = lines[title_idx + 1 :] if title_idx != -1 else lines
    raw_body = "\n".join(remaining_lines).strip()

    # 필수 섹션 검증: Why, What, How to Test
    sections = {"Why": [], "What": [], "How to Test": []}
    current_sec = None

    for line in raw_body.splitlines():
        sline = line.strip()
        lower_line = sline.lower()

        # 섹션 헤더 탐지
        if re.search(r"\bwhy\b", lower_line) and any(lower_line.startswith(p) for p in ["#", "why"]):
            current_sec = "Why"
            continue
        elif re.search(r"\bwhat\b", lower_line) and any(lower_line.startswith(p) for p in ["#", "what"]):
            current_sec = "What"
            continue
        elif re.search(r"\bhow to test\b", lower_line) and any(lower_line.startswith(p) for p in ["#", "how"]):
            current_sec = "How to Test"
            continue

        if current_sec:
            sections[current_sec].append(line)

    # 섹션별 불릿 검증 및 보완
    formatted_body_parts = []

    for sec_name, default_msg in [
        ("Why", "코드 변경 사항 반영 및 기능 개선을 위한 작업입니다."),
        ("What", "변경 사항에 대한 구현 및 코드 최적화 완료"),
        ("How to Test", "관련 테스트 실행 및 정상 동작 여부 확인"),
    ]:
        formatted_body_parts.append(f"## {sec_name}")
        bullets = [line for line in sections[sec_name] if line.strip().startswith(("-", "*"))]
        if bullets:
            formatted_body_parts.extend(sections[sec_name])
        else:
            content_lines = [line.strip() for line in sections[sec_name] if line.strip()]
            if content_lines:
                for line in content_lines:
                    formatted_body_parts.append(f"- {line.lstrip('-* ')}")
            else:
                formatted_body_parts.append(f"- {default_msg}")
        formatted_body_parts.append("")

    body = "\n".join(formatted_body_parts).strip()
    return title, body
