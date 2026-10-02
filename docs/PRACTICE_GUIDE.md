# 실습 가이드 — CLI 옵션별 명령어와 실행 결과 예시

이 문서는 `gitgen` CLI의 각 명령어와 옵션을 직접 실습하면서 동작을 확인하기 위한 가이드입니다.

---

## 0. 준비

### 1) 환경 활성화
```bash
# 가상환경 활성화
source .venv/bin/activate

# 또는 가상환경 파이썬 직접 실행
.venv/bin/python main.py --help
```

### 2) `.env` 환경변수 설정
프로젝트 루트의 `.env` 파일에 API 키가 설정되어 있어야 합니다:
```env
AI_API_KEY=your_api_key_here
AI_BASE_URL=https://copa.codyssey.kr/v1
AI_MODEL=gpt-5-mini
```

### 3) 실습용 Git 변경 사항 생성
실습을 위해 임의의 파일을 생성하거나 수정합니다: 
```bash
echo "print('hello world')" > sample.py
```

---

## 1. 도움말 확인 (`--help`)

전체 도움말과 각 서브커맨드별 도움말을 확인할 수 있습니다:

```bash
python main.py --help
python main.py commit --help
python main.py pr --help
```

### `python main.py commit --help` 출력:
```text
usage: main.py commit [-h] [--model MODEL] [--temperature TEMPERATURE]
                      [--max-tokens MAX_TOKENS] [--safe-mode]

options:
  -h, --help            show this help message and exit
  --model MODEL, -model MODEL
                        사용할 AI 모델 이름 (기본값: gpt-5-mini)
  --temperature TEMPERATURE, -temperature TEMPERATURE
                        샘플링 온도 (범위: 0.0 ~ 2.0, 기본값: 1.0)
  --max-tokens MAX_TOKENS, -max-tokens MAX_TOKENS
                        생성할 최대 토큰 수 (범위: 16 ~ 32768, 기본값: 2000)
  --safe-mode, -safe-mode
                        민감 정보(API 키, 패스워드, 이메일 등) 마스킹 안전 모드
```

---

## 2. 커밋 메시지 자동 생성 (`commit`)

코드 변경 사항을 분석하여 Conventional Commits 표준에 맞는 커밋 메시지를 생성합니다.

```bash
python main.py commit
```

### 출력 예시:
```text
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] Git diff 수집 완료: 1줄
[INFO] 실행 파라미터: model=gpt-5-mini, temp=1.0, max_tokens=2000, safe_mode=OFF
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1회
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat: 샘플 출력 스크립트 sample.py 추가

- sample.py
- 기본 인사말 출력을 위한 sample.py 파일 신규 생성
----------------------
```

- **규격 검증**: 커밋 제목 1줄(최대 72자), 제목-본문 사이 빈 줄, 변경된 파일 및 핵심 불릿 요약이 포함됩니다.
- **구분선**: 사용자가 쉽게 복사할 수 있도록 `--- Commit Message ---`로 감싸져 출력됩니다.

---

## 3. Pull Request 초안 자동 생성 (`pr`)

브랜치 변경 내역을 바탕으로 표준 PR 템플릿(Why / What / How to Test) 형식의 초안을 생성합니다.

```bash
python main.py pr
```

### 출력 예시:
```text
[INFO] 현재 브랜치: main
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] Git diff 수집 완료: 1줄
[INFO] 실행 파라미터: model=gpt-5-mini, temp=1.0, max_tokens=2500, safe_mode=OFF
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1회
[DONE] PR 초안 생성 완료

--- PR Title ---
feat: 샘플 테스트 스크립트 sample.py 추가

--- PR Body ---
## Why
- 실습 및 테스트 동작 검증을 위한 샘플 스크립트가 필요했습니다.

## What
- sample.py: hello world를 출력하는 기본 파이썬 스크립트 작성

## How to Test
- python sample.py 실행 후 정상 출력 확인
----------------
```

---

## 4. 안전 모드 실습 (`--safe-mode`)

코드 내에 API Key, 토큰, 패스워드, 이메일 등의 민감정보가 포함되어 있는 경우 안전하게 마스킹합니다.

```bash
# 1. 민감 정보가 포함된 파일 생성
echo "SECRET_KEY='sk-123456789012345678901234'" >> config.txt
echo "CONTACT_EMAIL='user@example.com'" >> config.txt

# 2. safe-mode 옵션으로 커밋 생성
python main.py commit --safe-mode
```

### 동작 결과:
- `[INFO] 안전 모드(Safe Mode) 활성화: 민감 정보 마스킹 적용` 메시지가 표시됩니다.
- API Key(`sk-...`, `ghp_...`, `AKIA...`, `AIza...`), 비밀번호/토큰 할당문, 이메일 등이 `[MASKED_API_KEY]`, `[MASKED_SECRET]`, `[MASKED_EMAIL]` 등으로 자동 치환되어 AI API로 전송됩니다.

---

## 5. 모델 및 생성 파라미터 조정

CLI 옵션을 통해 모델이나 샘플링 온도를 유연하게 변경할 수 있습니다:

```bash
# 모델 변경 (예: gemini-2.5-flash 또는 gpt-5-mini)
python main.py commit --model gemini-flash-latest

# 샘플링 온도 변경 (낮을수록 보수적/정형화, 높을수록 창의적)
python main.py commit --temperature 0.5

# 최대 토큰 수 변경
python main.py commit --max-tokens 1500
```

---

## 6. 예외 상황 처리 확인

프로그램은 다양한 비정상 상황에서 사용자 친화적인 에러 메시지를 출력하고 종료합니다:

### 1) 변경 사항이 없는 경우
```text
[INFO] 변경 사항이 없습니다. 작업을 생성하지 않고 종료합니다.
```

### 2) Git 저장소가 아닌 디렉토리에서 실행한 경우
```text
[ERROR] Git 저장소가 아닙니다. Git 저장소 루트에서 실행해주세요.
```

### 3) API Key가 설정되지 않은 경우
```text
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.
예) export AI_API_KEY="YOUR_KEY"
```
