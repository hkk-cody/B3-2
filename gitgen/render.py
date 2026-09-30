def render(command: str, draft: dict, *, partial: bool = False) -> str:
    lines = ["--- Change Summary ---", draft["summary"]]
    if partial:
        lines.append("[부분 분석] 일부 파일 또는 diff가 제외되거나 잘렸습니다.")
    if command == "commit":
        lines += ["", "--- Commit Message ---", draft["title"], ""]
        lines += [f"- {change}" for change in draft["changes"]]
    else:
        lines += ["", "--- PR Title ---", draft["title"], "", "--- PR Body ---"]
        for heading, field in [("Why", "why"), ("What", "what"), ("How to Test", "how_to_test")]:
            lines += [f"## {heading}"]
            items = draft[field]
            if field == "what" and partial:
                lines.append("- 부분 분석: 일부 변경이 제외되었습니다. 전체 diff를 직접 확인하세요.")
            lines += [f"- {item}" for item in items]
            lines.append("")
    lines.append("----------------------")
    return "\n".join(lines)
