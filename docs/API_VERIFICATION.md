# 실제 AI API 검증 기록

검증일: 2026-09-30

프로젝트 `.env`에 설정된 Google Gemini 공식 OpenAI 호환 엔드포인트를 통해 실제 API를 호출하여 커밋 메시지와 PR 초안 생성이 정상 작동함을 확인했습니다. (보안을 위해 실제 API 키는 기록하지 않습니다.)

| 항목 | 결과 |
| :--- | :--- |
| 요청 주소 (Base URL) | `https://generativelanguage.googleapis.com/v1beta/openai` |
| 모델 | `gemini-flash-latest` |
| 커밋 생성 (`commit`) | 성공, AI API 1회 호출, 종료 코드 0 |
| PR 생성 (`pr`) | 성공, AI API 1회 호출, 종료 코드 0 |
| 총 실제 API 호출 | 2회 |

---

## 1. 실제 커밋 생성 출력 (`python main.py commit`)

```text
[INFO] Git status 수집 완료: 22개 파일 변경 감지
[INFO] Git diff 수집 완료: 2265줄
[INFO] 실행 파라미터: model=gemini-flash-latest, temp=1.0, max_tokens=2000, safe_mode=OFF
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1회
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
refactor: CLI 구조 개편 및 핵심 모듈 단순화

- main.py, gitgen/, README.md
- main.py의 서브커맨드 핸들러를 분리하고 CLI 실행 흐름을 직관적으로 개선
- gitgen 내부 모듈을 ai_client, git_utils, validator 중심으로 통폐합 및 리팩토링
- 변경된 아키텍처에 맞춰 프로젝트 문서(README.md)와 프롬프트 템플릿 갱신
----------------------
```

### 검증 포인트 만족 여부:
- [x] 커밋 제목 1줄 (최대 72자)
- [x] Conventional Commits 접두사(`refactor:`) 준수
- [x] 제목과 본문 사이 빈 줄 유지
- [x] 본문에 변경된 주요 파일(`main.py, gitgen/, README.md`) 1~3개 언급
- [x] 핵심 변경 사항 불릿('- ') 요약
- [x] API 호출 횟수(`1회`) 명시

---

## 2. 실제 PR 초안 생성 출력 (`python main.py pr`)

```text
[INFO] 현재 브랜치: main
[INFO] Git status 수집 완료: 22개 파일 변경 감지
[INFO] Git diff 수집 완료: 2265줄
[INFO] 실행 파라미터: model=gemini-flash-latest, temp=1.0, max_tokens=3000, safe_mode=OFF
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1회
[DONE] PR 초안 생성 완료

--- PR Title ---
refactor: gitgen 모듈 아키텍처 단순화 및 CLI 파이프라인 개편

--- PR Body ---
## Why
- 기존에 지나치게 잘게 쪼개져 있던 모듈 구조(`generation`, `render`, `safety`, `validators` 등)로 인한 복잡도를 줄이고 유지보수성을 높이기 위함입니다.
- CLI 진입점(`main.py`)과 핵심 로직(`git_utils`, `ai_client`, `validator`)의 책임을 명확히 분리하여 가독성과 코드 응집도를 개선하기 위함입니다.

## What
- 모듈 통합 및 리팩토링: `api_client`, `git_context`, `safety`, `render`, `validators` 등을 `ai_client.py`, `git_utils.py`, `validator.py`로 통폐합
- CLI 파이프라인 재설계: `main.py` 내에 `commit` 및 `pr` 서브커맨드 핸들러를 직관적인 절차형 흐름으로 재구성
- 프롬프트 및 출력 포맷팅 검증 간소화: JSON 스키마 강제 방식 대신 직접적인 텍스트 검증 및 마스킹 로직(`validate_and_format_*`) 적용
- 테스트 및 문서 정비: 모듈 재구조화에 맞춰 `README.md` 사용 가이드 갱신 및 테스트 코드 통합

## How to Test
- `pytest`를 실행하여 단위 테스트 통과 여부 검증
- 임의의 파일 수정 후 `python main.py commit`을 실행하여 커밋 메시지 포맷(제목 1줄 + 빈 줄 + 파일/불릿 요약) 생성 확인
- `python main.py pr`을 실행하여 PR Title 및 3대 필수 섹션(`## Why`, `## What`, `## How to Test`)과 불릿 항목 출력 확인
- `python main.py commit --safe-mode`를 실행하여 민감 정보 마스킹 및 diff 줄 수 제한이 정상 적용되는지 확인
----------------
```

### 검증 포인트 만족 여부:
- [x] PR 제목 1줄 (최대 80자)
- [x] 필수 3대 섹션 헤더(`## Why`, `## What`, `## How to Test`) 포함
- [x] 각 섹션마다 최소 1개 이상의 구체적인 불릿('- ') 포함
- [x] 구분선으로 터미널에서 쉽게 복사 가능
- [x] API 호출 횟수(`1회`) 명시
