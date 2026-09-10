def render(command: str, draft: dict, *, partial: bool = False, has_reason: bool = True, has_tests: bool = True) -> str:
    lines = ["--- Change Summary ---", draft["summary"]]
    if partial:
        lines.append("[부분 분석] 일부 파일·diff·맥락이 제외되거나 잘렸습니다.")
    if command == "commit":
        lines += ["", "--- Commit Message ---", draft["title"], ""]
        lines += [f"- {change}" for change in draft["changes"]]
    else:
        lines += ["", "--- PR Title ---", draft["title"], "", "--- PR Body ---"]
        for heading, field in [("Why", "why"), ("What", "what"), ("How to Test", "how_to_test")]:
            lines += [f"## {heading}"]
            items = draft[field]
            if field == "why" and not has_reason:
                items = ["변경 배경 확인 필요: --context로 변경 이유를 제공하세요."]
            if field == "how_to_test" and not has_tests:
                lines.append("- 미실행: 테스트 실행 정보가 제공되지 않았습니다. 아래 제안은 직접 검증하세요.")
            if field == "what" and partial:
                lines.append("- 부분 분석: 일부 변경이 제외되었습니다. 전체 diff를 직접 확인하세요.")
            lines += [f"- {item}" for item in items]
            lines.append("")
    lines.append("----------------------")
    return "\n".join(lines)
