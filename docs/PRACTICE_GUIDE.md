# 실습 가이드 — CLI 옵션별 명령어와 실행 결과 예시

이 문서는 각 CLI 옵션을 직접 실습하면서 동작을 확인하기 위한 예시 모음입니다. 명령어와 함께 예상 출력을 정리했습니다. 실제 생성 결과(커밋 메시지·PR 본문 본문 내용)는 diff와 맥락에 따라 달라지므로, 여기 실린 AI 생성 텍스트는 참고용 예시입니다. 로그(`[INFO]`, `[DONE]` 등)와 출력 구획 형식은 실제 프로그램과 동일합니다.

> 진행 상황·오류·API 호출 횟수는 표준 오류(stderr), 생성 결과는 표준 출력(stdout)으로 나옵니다.

## 0. 준비

Python **3.10 이상**이 필요합니다. 시스템 기본 `python3`가 3.9면 아래처럼 오류가 납니다.

```text
[ERROR] Python 3.10 이상이 필요합니다. python3 --version을 확인하세요.
```

이 저장소에는 검증용 가상환경 `.venv`(Python 3.12)가 있습니다. 실습은 아래 중 하나로 실행하세요.

```bash
# 방법 1: 가상환경 활성화
source .venv/bin/activate
python main.py --help

# 방법 2: 가상환경 파이썬을 직접 지정
.venv/bin/python main.py --help
```

이 문서의 예시는 `python main.py ...`로 표기합니다. 가상환경을 활성화하지 않았다면 `python`을 `.venv/bin/python`으로 바꿔 실행하세요.

실습용 변경 만들기(선택). 아무 파일이나 수정한 뒤 stage하면 됩니다.

```bash
echo "print('hello world')" >> sample.py
git add sample.py
```

`--dry-run`은 API Key 없이도 실행되므로, 키가 없어도 대부분의 옵션 동작을 확인할 수 있습니다.

## 1. 도움말 보기 (`--help`)

```bash
python main.py --help
python main.py commit --help
python main.py pr --help
```

`commit --help` 출력:

```text
usage: main.py commit [-h] [--model MODEL] [--temperature TEMPERATURE]
                      [--max-tokens MAX_TOKENS] [--safe-mode]
                      [--dry-run]

커밋 메시지 생성

options:
  -h, --help            show this help message and exit
  --model MODEL, -model MODEL
                        Codyssey 모델 (AI_MODEL 또는 기본 gpt-5-mini)
  --temperature TEMPERATURE, -temperature TEMPERATURE
                        생성 무작위성 0~2 (기본: 서버 기본값, 지원 모델에서만 지정)
  --max-tokens MAX_TOKENS, -max-tokens MAX_TOKENS
                        추론 포함 생성 토큰 상한 (기본: 4096)
  --safe-mode, -safe-mode
                        민감정보 마스킹·전송량 제한 (항상 활성)
  --dry-run             API 호출 없이 전송할 요청 본문 미리보기 (Key 불필요)
```

## 2. `--dry-run` — API 호출 없이 요청 본문 미리보기 (Key 불필요)

가장 먼저 실습하기 좋은 옵션입니다. 실제 API를 호출하지 않고(호출 0회), 안전 처리(마스킹·제한)를 거친 뒤 서버로 보낼 JSON 요청 본문을 그대로 보여줍니다.

```bash
python main.py commit --dry-run
```

출력(예시):

```text
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] M  'sample.py'
[INFO] 안전 모드 미적용: diff 3줄 전송 준비 (필요 시 --safe-mode 사용)
[INFO] 요청 주소: https://copa.codyssey.kr/v1/chat/completions
[INFO] API 호출 횟수: 0회
--- API Request Preview (외부 전송 없음) ---
{"model":"gpt-5-mini","messages":[{"role":"system","content":"당신은 Git 변경 내용을 설명하는 개발 도우미다. ..."},{"role":"user","content":"{\"command\":\"commit\",\"git_context\":{\"scope\":\"staged\",...}}"}],"max_completion_tokens":4096}
```

- 인증 헤더(Key)는 미리보기에 **포함되지 않습니다.**
- `--model`, `--max-tokens`, `--temperature`를 바꾸면 이 JSON의 값이 바뀌는 것을 눈으로 확인할 수 있습니다.

## 3. `--model` — 모델 지정

`--dry-run`과 함께 쓰면 요청 본문의 `"model"` 값이 바뀌는지 확인할 수 있습니다.

```bash
python main.py commit --dry-run --model gpt-5-mini
python main.py commit --dry-run -model gpt-5-mini   # 짧은 별칭도 동일
```

요청 본문 앞부분이 다음처럼 지정한 모델로 바뀝니다.

```text
--- API Request Preview (외부 전송 없음) ---
{"model":"gpt-5-mini", ...
```

잘못된 형식을 주면 검증 오류가 납니다.

```bash
python main.py commit --model "bad model name!"
```

```text
usage: main.py commit [-h] [--model MODEL] ...
main.py commit: error: argument --model/-model: model은 128자 이내의 영문·숫자·점·밑줄·콜론·하이픈으로 입력하세요.
```

## 4. `--max-tokens` — 생성 토큰 상한

허용 범위는 **16~32768**, 기본값은 4096입니다. `--dry-run`으로 요청 본문의 `max_completion_tokens` 값이 바뀌는지 확인합니다.

```bash
python main.py commit --dry-run --max-tokens 1024
```

```text
--- API Request Preview (외부 전송 없음) ---
{..., "max_completion_tokens":1024}
```

범위를 벗어나면 오류가 납니다.

```bash
python main.py commit --max-tokens 5
```

```text
usage: main.py commit [-h] [--model MODEL] [--temperature TEMPERATURE]
                      [--max-tokens MAX_TOKENS] [--safe-mode]
                      [--dry-run]
main.py commit: error: argument --max-tokens/-max-tokens: max-tokens는 16~32768 범위여야 합니다.
```

> `--max-tokens`는 문자 수가 아니라 **생성 토큰 수의 상한**이며 추론 토큰도 포함합니다. 너무 작으면 본문이 완성되기 전에 잘릴 수 있습니다.

## 5. `--temperature` — 생성 무작위성

허용 범위는 **0~2**입니다. 지정하지 않으면 이 필드를 서버에 보내지 않습니다(서버 기본값 사용). 지정하면 `--dry-run` 요청 본문에 `"temperature"`가 추가됩니다.

```bash
python main.py commit --dry-run --temperature 0.4
```

```text
--- API Request Preview (외부 전송 없음) ---
{..., "temperature":0.4, "max_completion_tokens":4096}
```

범위를 벗어나면 오류가 납니다.

```bash
python main.py commit --temperature 3
```

```text
main.py commit: error: argument --temperature/-temperature: temperature는 0~2 범위여야 합니다.
```

> 모델에 따라 temperature를 지원하지 않을 수 있습니다. 지원하지 않는 모델에 지정하면 실제 호출 시 HTTP 400이 발생하며, 이때는 옵션을 생략하세요.

## 6. staged 전용 동작 — `git add` 전후 비교

이 도구는 항상 **staged 변경(`git diff --cached`)만** 분석합니다. 초안이 실제 다음 커밋 내용과 일치하도록 하기 위해서입니다.

`git add` 하기 전(unstaged만 있는 상태)에서는 분석할 내용이 없어 API를 호출하지 않고 종료합니다.

```bash
# 파일 수정 후 git add 없이 실행 → staged 없음
echo "print('changed')" > sample.py
python main.py commit --dry-run
```

```text
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO]  M 'sample.py'
[INFO] 분석할 staged 변경 사항이 없습니다. git add로 변경을 stage한 뒤 다시 실행하세요.
[INFO] API 호출 횟수: 0회
```

`git add` 후 실행하면 staged 변경이 분석 대상이 됩니다. `[INFO]` 상태 표기가 ` M`(unstaged) 에서 `M `(staged)로 바뀐 것을 확인할 수 있습니다.

```bash
git add sample.py
python main.py commit --dry-run
```

```text
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] M  'sample.py'
[INFO] 안전 모드 미적용: diff 3줄 전송 준비 (필요 시 --safe-mode 사용)
[INFO] 요청 주소: https://copa.codyssey.kr/v1/chat/completions
[INFO] API 호출 횟수: 0회
--- API Request Preview (외부 전송 없음) ---
...
```

## 7. `--safe-mode` — 민감정보 마스킹·전송량 제한 (선택 활성화)

이 옵션은 기본적으로 꺼져 있으며(`default=False`), `--safe-mode`를 붙였을 때 민감 파일 제외, 비밀값 마스킹, 최대 10개 파일·200줄 전송 제한이 활성화됩니다.

```bash
# 안전 모드 켜기
python main.py commit --dry-run --safe-mode
```

안전 처리 결과는 `[INFO]` 로그로 확인합니다.

```text
[INFO] 안전 모드 적용: diff 3줄, 민감 파일 제외 0개, 한도 제외 0개, 잘린 diff 0개
```

옵션을 생략하면 안전 모드가 꺼진 상태로 동작합니다:

```bash
# 안전 모드 끄기 (기본값)
python main.py commit --dry-run
```

```text
[INFO] 안전 모드 미적용: diff 3줄 전송 준비 (필요 시 --safe-mode 사용)
```

- 안전 모드가 켜진 상태에서 제외되거나 잘린 입력이 있으면 아래 경고가 추가되고, 출력에 `[부분 분석]` 표시가 붙습니다.

```text
[WARN] 부분 분석: 일부 파일 또는 diff가 제외되거나 잘렸습니다.
```

민감정보 마스킹을 실습하려면, 예를 들어 diff에 비밀번호(`password = "1234"`)를 넣고 `--safe-mode`를 줬을 때(`[REDACTED]`)와 안 줬을 때의 `--dry-run` 요청 본문 차이를 비교하세요.

## 8. 실제 커밋 메시지 생성 (`commit`, API Key 필요)

`--dry-run` 없이 실행하면 실제 API를 1회 호출합니다. `AI_API_KEY` 설정이 필요합니다.

```bash
python main.py commit
```

출력(예시 — 실제 텍스트는 diff에 따라 달라짐):

```text
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] M  'greetings.py'
[INFO] 안전 처리 완료: diff 11줄, 민감 파일 제외 0개, 한도 제외 0개, 잘린 diff 0개
[INFO] AI API 요청 중...
[DONE] 초안 생성 완료. 내용과 테스트 사실을 검토한 뒤 복사하여 적용하세요.
[INFO] API 호출 횟수: 1회

--- Change Summary ---
greet 함수에서 입력 이름을 strip하여 공백만 입력된 경우 ValueError를 발생시키도록 검증을 추가함.

--- Commit Message ---
fix: 공백만 입력된 이름으로 인사말 생성 오류 방지

- name.strip()로 입력을 정리하고 비어있으면 ValueError를 발생시킴
- 정상 입력은 공백을 제거한 이름으로 인사말을 반환하도록 변경함
----------------------
```

커밋 제목이 50자를 넘으면(72자 이내여도) 아래 경고가 추가됩니다.

```text
[WARN] 커밋 제목은 50자 이내를 권장합니다. 현재 제목은 최대 72자 규칙을 충족합니다.
```

## 9. 실제 PR 초안 생성 (`pr`, API Key 필요)

```bash
python main.py pr
```

출력(예시):

```text
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] M  'greetings.py'
[INFO] 안전 처리 완료: diff 11줄, 민감 파일 제외 0개, 한도 제외 0개, 잘린 diff 0개
[INFO] AI API 요청 중...
[DONE] 초안 생성 완료. 내용과 테스트 사실을 검토한 뒤 복사하여 적용하세요.
[INFO] API 호출 횟수: 1회

--- Change Summary ---
입력값을 strip하고 공백만인 경우 ValueError를 발생시켜 잘못된 인사말 생성을 방지함

--- PR Title ---
fix: 공백만 입력된 이름으로 인사말 생성 방지

--- PR Body ---
## Why
- 이전 구현은 공백만 입력되면 빈 이름으로 인사말을 생성할 수 있었음
- 변경 배경 확인 필요

## What
- name.strip()로 앞뒤 공백을 제거하여 clean 변수에 저장
- clean이 비어있으면 ValueError를 발생시키고, 아니면 clean으로 인사말 반환

## How to Test
- greet(" Alice ")가 "Hello, Alice!"를 반환하는지 확인
- greet("   ")가 ValueError를 발생시키는지 확인

----------------------
```

## 10. 결과를 파일로 저장하기

생성 결과(stdout)만 파일로 저장하려면 리다이렉션을 사용합니다. 로그(stderr)는 화면에 남습니다.

```bash
python main.py pr > /tmp/pr-draft.txt
```

## 11. 자주 만나는 상황과 메시지

| 상황                              | 출력 메시지                                                                               |
| --------------------------------- | ----------------------------------------------------------------------------------------- |
| 변경 사항 없음                    | `[INFO] 변경 사항이 없습니다.` (API 호출 0회, 종료 코드 0)                                |
| unstaged 변경만 있음 (git add 전) | `[INFO] 분석할 staged 변경 사항이 없습니다. git add로 변경을 stage한 뒤 다시 실행하세요.` |
| untracked 파일만 있음             | `[INFO] 추적되지 않은 파일만 있어 분석할 diff가 없습니다. git add 후 다시 실행하세요.`    |
| API Key 없이 실제 생성 시도       | `[ERROR] AI_API_KEY가 설정되지 않았습니다. ...` (미리보기는 `--dry-run` 사용)             |
| Python 3.9 이하                   | `[ERROR] Python 3.10 이상이 필요합니다. ...`                                              |
| 옵션 값 범위 위반                 | `main.py commit: error: ... 범위여야 합니다.`                                             |

## 12. 실습 추천 순서

1. `python main.py commit --help`로 옵션 전체를 확인한다.
2. 파일을 수정하고 **`git add` 없이** `python main.py commit --dry-run`을 실행해 "staged 변경 사항이 없습니다" 메시지를 확인한다.
3. `git add`로 stage한 뒤 `python main.py commit --dry-run`으로 요청 본문을 확인한다(호출 0회).
4. `--model`, `--max-tokens`, `--temperature`를 하나씩 바꿔 가며 `--dry-run` 요청 본문의 값 변화를 관찰한다.
5. 잘못된 값(예: `--max-tokens 5`, `--temperature 3`)을 넣어 검증 오류 메시지를 확인한다.
6. API Key를 설정한 뒤 `python main.py commit`으로 실제 커밋 메시지를 1회 생성한다.
7. `python main.py pr`로 PR 초안을 생성하고 Why/What/How to Test 섹션을 확인한다.

> 실제 생성(`commit`/`pr`)은 API를 호출하므로 비용이 발생할 수 있습니다. 옵션 동작 확인은 되도록 `--dry-run`으로 하고, 실제 호출은 필요한 만큼만 수행하세요.
