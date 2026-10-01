# AI 기반 Git 커밋 메시지 및 PR 초안 자동 생성 도우미 (`gitgen`)

Git 저장소의 최근 변경 사항(`git status` 및 `git diff`)을 분석하여 실무 표준 규격에 맞는 **커밋 메시지**와 **Pull Request(PR) 초안**을 자동으로 생성해 주는 CLI 도구입니다.

---

## 📁 프로젝트 구조

```
.
├── main.py                 # CLI 진입점 (commit / pr 서브커맨드)
├── gitgen/                 # 핵심 패키지
│   ├── __init__.py         # 패키지 초기화 및 공개 API 정의
│   ├── config.py           # 환경변수 로더 및 기본 설정 상수
│   ├── ai_client.py        # OpenAI 호환 REST API 클라이언트
│   ├── git_utils.py        # Git 상태/diff 수집 유틸리티
│   ├── prompts.py          # 커밋/PR 생성 프롬프트 템플릿
│   └── validator.py        # 출력 형식 검증, 민감정보 마스킹, safe-mode
├── tests/                  # 핵심 기능 테스트 (pytest)
│   ├── conftest.py
│   └── test_gitgen.py
├── docs/                   # 상세 가이드 및 검증 문서
│   ├── API_VERIFICATION.md     # 실제 API 호출 검증 기록
│   ├── PRACTICE_GUIDE.md       # CLI 실습 가이드
│   ├── PARAMETER_COMPARISON.md # temperature/max-tokens 실험 결과
│   └── LEARNING_GUIDE.md       # B3-2 학습 개념서
├── requirements.txt        # 패키지 의존성 파일
├── .env                    # 환경변수 파일 (git 추적 제외)
├── .env.example            # 환경변수 설정 예시
├── .gitignore              # Git 추적 제외 규칙
└── README.md               # 사용 가이드 및 과제 보고서
```

---

## 📌 주요 기능

1. **Git 상태 및 Diff 자동 분석**: `git status`와 `git diff`를 수집하여 코드 변경 내역을 정확히 요약합니다.
2. **커밋 메시지 자동 생성 (`commit`)**:
   - Conventional Commits 형식(`feat:`, `fix:` 등) 적용
   - 커밋 제목 1줄(50자 권장, 최대 72자) 및 본문(변경된 파일 및 핵심 불릿 요약) 자동 생성
3. **Pull Request 초안 자동 생성 (`pr`)**:
   - PR 제목(최대 80자) 및 표준 템플릿(`## Why`, `## What`, `## How to Test`) 구조의 본문 생성
   - 각 섹션별 최소 1개 이상의 구체적인 불릿 항목 구성
4. **출력 형식 검증 및 사후 가공**:
   - 규격 길이 초과 시 자동 다듬기 및 필수 섹션/불릿 누락 방지
   - 구분선으로 명확한 구획 제공
5. **안전 모드 (`--safe-mode`) 제공**:
   - diff 내 API Key, Secret Token, 비밀번호, 이메일 등 민감정보 자동 마스킹
   - 대용량 diff 전송 방지를 위해 파일 수(최대 10개) 및 줄 수(최대 200줄) 제한

---

## 🛠 설치 및 환경 설정

### 1. 개발 환경 요구사항
- Python 3.10 이상 (Python 3.11 권장)
- Git 2.x 이상

### 2. 가상환경 설정 및 패키지 설치

```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 패키지 설치
pip install requests
```

### 3. AI API Key 및 환경변수 설정
AI API Key는 코드에 하드코딩하지 않고 환경변수로 관리합니다.

#### 방법 A: `.env` 파일 사용 (권장)
프로젝트 루트의 `.env` 파일에 다음과 같이 설정합니다.
```bash
cp .env.example .env
```
`.env` 파일 내용:
```env
AI_API_KEY=your_actual_api_key_here
AI_BASE_URL=https://copa.codyssey.kr/v1
AI_MODEL=gpt-5-mini
```

#### 방법 B: 셸 환경변수 직접 내보내기 (`export`)
```bash
export AI_API_KEY="your_actual_api_key_here"
# (선택 사항)
export AI_BASE_URL="https://copa.codyssey.kr/v1"
export AI_MODEL="gpt-5-mini"
```

---

## 🚀 사용법 및 실행 예시

### 1. 커밋 메시지 자동 생성 (`commit`)

코드 작업 후 변경 사항이 있는 상태에서 실행합니다.

```bash
# 기본 실행
python main.py commit

# 안전 모드로 실행
python main.py commit --safe-mode

# 모델 및 파라미터 조정
python main.py commit --model gpt-5-mini --temperature 0.7
```

#### 터미널 출력 예시
```text
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 128줄
[INFO] 실행 파라미터: model=gemini-flash-latest, temp=1.0, max_tokens=2000, safe_mode=OFF
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1회
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat: Git 변경 사항 기반 커밋 메시지 자동 생성 기능 추가

- git_utils.py: git status 및 git diff 수집 로직 구현
- validator.py: 커밋 메시지 길이 및 형식 검증 로직 추가
- API Key 미설정 시 안내 메시지 및 에러 핸들링 강화
----------------------
```

---

### 2. PR 제목/본문 초안 자동 생성 (`pr`)

브랜치 작업 완료 후 PR을 생성하기 전 초안 텍스트를 터미널에서 즉시 확인하고 복사할 수 있습니다.

```bash
# 기본 실행
python main.py pr

# 안전 모드로 실행
python main.py pr --safe-mode
```

#### 터미널 출력 예시
```text
[INFO] 현재 브랜치: feature/commit-pr-generator
[INFO] Git status 수집 완료: 4개 파일 변경 감지
[INFO] Git diff 수집 완료: 185줄
[INFO] 실행 파라미터: model=gemini-flash-latest, temp=1.0, max_tokens=3000, safe_mode=OFF
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1회
[DONE] PR 초안 생성 완료

--- PR Title ---
feat: Git 변경 사항 기반 커밋 메시지 및 PR 초안 자동 생성 도우미 구현

--- PR Body ---
## Why
- 협업 시 매번 수동으로 커밋 메시지와 PR 템플릿을 작성하는 반복 비용을 줄이고자 했습니다.
- 변경된 코드 맥락에 기반한 일관된 포맷의 요약을 제공하여 코드 리뷰 생산성을 높이기 위함입니다.

## What
- git status 및 git diff 결과를 수집하고 파싱하는 git_utils 모듈 구현
- OpenAI 규격 REST API와 연동하여 1회 요청으로 커밋/PR을 생성하는 AIClient 구현
- Why / What / How to Test 3단계 필수 템플릿 및 불릿 검증기 구현
- API Key 미설정, Git 미저장소, 변경 사항 부재 등 예외 상황 처리
- 민감 정보 마스킹 및 전송량 제한을 지원하는 --safe-mode 옵션 추가

## How to Test
- .env 또는 환경변수로 AI_API_KEY 설정
- 코드 수정 후 python main.py commit 실행하여 커밋 메시지 생성 확인
- python main.py pr 실행하여 Why/What/How to Test 섹션 및 불릿 포맷 확인
- python main.py commit --safe-mode 실행하여 안전 모드 동작 확인
----------------
```

---

## ⚙️ CLI 옵션 상세 안내

`commit` 및 `pr` 명령어에서 공통으로 아래 옵션들을 지원합니다.

| 옵션 | 단축/별칭 | 기본값 | 설명 |
| :--- | :--- | :--- | :--- |
| `--model` | `-model` | `gpt-5-mini` | 사용할 AI 모델 이름 지정 |
| `--temperature` | `-temperature` | `1.0` | AI 답변 생성 다양성 제어 (0.0 ~ 2.0) |
| `--max-tokens` | `-max-tokens` | commit: `2000`<br>pr: `2500` | 생성할 최대 토큰 수 제어 (16 ~ 32768) |
| `--safe-mode` | `-safe-mode` | `False` | 민감정보 마스킹 및 diff 전송량 제한 활성화 |

---

## 🔒 보안 및 운영 주의사항

### 1. 민감정보 노출 방지 및 안전 모드 (`--safe-mode`)
- **Git diff 민감정보 포함 주의**: 코드 작성 중 소스 코드나 설정 파일에 API Key, DB 비밀번호, 개인정보(이메일 등)가 실수로 포함된 상태에서 AI API로 전송되면 보안 사고가 발생할 수 있습니다.
- **안전 모드 제공**: 본 도구는 `--safe-mode` 옵션을 지원합니다.
  - 정규표현식을 통해 API Key, 토큰, 비밀번호 할당 구문, 이메일 주소 등을 `[MASKED_SECRET]` 형태로 자동 치환합니다.
  - 전송 대상 파일을 최대 10개, diff 길이를 최대 200줄로 자동 제한하여 과도한 정보 전송을 방지합니다.
- **`.gitignore` 설정**: `.env` 파일과 민감한 설정 파일은 `.gitignore`에 등록되어 원격 저장소에 커밋되지 않도록 보호되어 있습니다.

### 2. 비용 및 API 요청 횟수 제한 (Cost & Rate Limit)
- **1회 실행당 1회 호출**: 불필요한 반복 호출과 비용 낭비를 방지하기 위해 `commit`과 `pr` 명령은 각각 **단 1회의 AI API 호출**로 최종 결과를 도출하도록 최적화되어 있습니다.
- **호출 카운트 로깅**: 매 실행마다 터미널에 `[INFO] AI API 호출 횟수: 1회` 로그를 명시하여 사용자가 API 소비량을 명확히 인지할 수 있습니다.
- **토큰 절약 권장**:
  - 대규모 리팩토링이나 바이너리/대용량 데이터 변경 시에는 불필요한 diff가 전송되지 않도록 변경 사항을 모듈 단위로 나누어 커밋하거나 `--safe-mode`를 적극 활용하세요.

---

## 🧪 테스트 실행

```bash
pytest
```
모든 단위 테스트(민감정보 마스킹, safe-mode 제한, 출력 포맷팅 검증 등)가 정상 통과합니다.
