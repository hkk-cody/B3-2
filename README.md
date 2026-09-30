# AI Git 초안 생성기

Git의 **staged 변경(`git add`로 인덱스에 올린, 다음 커밋에 포함될 변경)**을 읽어 한국어 커밋 메시지와 Pull Request 제목·본문을 만드는 Python CLI입니다. 변경 내용을 Codyssey의 OpenAI 호환 API에 보내고, 응답 형식을 검증한 뒤 복사해서 사용할 초안을 터미널에 출력합니다.

```bash
git add .
python main.py commit
python main.py pr
```

분석 대상은 항상 staged 변경입니다. 초안이 실제 커밋 내용과 일치하도록, `git add`로 커밋할 변경을 먼저 stage한 뒤 실행하세요.

과제 원문은 [subject.md](subject.md), 구현 계획은 [PLAN.md](PLAN.md)에 있습니다. 자동 커밋·push·PR 등록은 하지 않습니다.

기초 개념부터 실제 코드 흐름, 보안·테스트, 실습과 발표 예상 질문까지 자세한 설명은 [학습 가이드](docs/LEARNING_GUIDE.md)에 정리했습니다.

## 1. 설치

Python **3.10 이상**과 Git이 필요합니다. macOS의 기본 `python3`가 3.9라면 별도로 설치한 Python 3.10 이상을 사용하세요.

```bash
git clone git@github.com:hkk-cody/B3-2.git
cd B3-2
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py --help
```

Windows PowerShell에서는 가상환경 활성화 명령으로 `.venv\Scripts\Activate.ps1`을 사용합니다.

현재 작업 폴더에는 검증용 Python 3.12 가상환경 `.venv`를 만들어 두었습니다. 이 폴더에서는 `source .venv/bin/activate`부터 시작할 수 있습니다. 가상환경은 Git에 포함되지 않으므로 새로 clone한 환경에서는 위 설치 과정을 진행해야 합니다.

## 2. API Key 설정

**프로젝트 루트의 `.env` 파일에 Codyssey에서 발급한 OpenAI 호환 API Key를 넣으면 됩니다.** 프로그램이 실행할 때 `AI_API_KEY`를 환경변수로 불러옵니다. 키는 [Codyssey API 콘솔](https://usr.codyssey.kr/public-api-console)에서 확인합니다.

현재 작업 폴더에는 `.env`가 준비되어 있습니다. 키를 처음 설정하거나 변경할 때 해당 파일의 `AI_API_KEY=` 뒤에 실제 키를 입력하고 저장하세요.

```dotenv
AI_API_KEY=여기에_Codyssey_OpenAI_호환_키를_입력
AI_BASE_URL=https://copa.codyssey.kr/v1
AI_MODEL=gpt-5-mini
```

새로 clone한 환경에서는 먼저 예제 파일을 복사합니다. 이미 `.env`가 있다면 복사하지 않고 기존 파일을 수정하세요.

```bash
cp .env.example .env
```

`.env`는 Git과 diff 전송에서 제외됩니다. 저장소에는 빈 입력 형식을 담은 `.env.example`만 포함합니다. `.env`가 없거나 키가 비어 있어도 `--dry-run`은 사용할 수 있습니다.

기존 터미널 환경변수 설정 방식도 지원합니다.

```bash
export AI_API_KEY="YOUR_CODYSSEY_OPENAI_COMPATIBLE_KEY"
```

macOS의 zsh에서 입력한 Key가 화면이나 셸 명령 기록에 남지 않도록 설정하려면:

```zsh
read -rs 'AI_API_KEY?Codyssey API Key: '
export AI_API_KEY
```

PowerShell에서는 `$env:AI_API_KEY = "YOUR_CODYSSEY_OPENAI_COMPATIBLE_KEY"`로 설정합니다. 환경변수는 현재 터미널 세션에 적용됩니다.

비어 있지 않은 터미널 환경변수 > 현재 분석 대상 저장소 루트의 `.env` > 프로그램 기본값 순서로 설정을 선택합니다. `.env`의 키로 바꾸려면 터미널에서 `unset AI_API_KEY` 후 다시 실행하세요. 같은 우선순위가 `AI_BASE_URL`과 `AI_MODEL`에도 적용됩니다. `--model`을 지정하면 `AI_MODEL`보다 우선합니다. 상위 폴더나 다른 저장소의 `.env`는 탐색하지 않습니다. 다른 저장소를 분석할 때는 그 저장소 루트에 `.env`를 두거나 터미널 환경변수를 사용하세요. 이 세 항목 외의 설정은 가져오지 않고 `${...}` 치환이나 셸 명령 실행도 하지 않습니다. 파싱에는 [python-dotenv](https://github.com/theskumar/python-dotenv)를 사용합니다.

2026-09-10에 확인한 Codyssey 콘솔의 **문서 → 텍스트(OpenAI) → Python** 예제를 기준으로 다음 형식을 사용합니다.

| 항목           | 설정                                             |
| -------------- | ------------------------------------------------ |
| 기본 API 주소  | `https://copa.codyssey.kr/v1`                    |
| POST 요청 주소 | `https://copa.codyssey.kr/v1/chat/completions`   |
| 인증           | `Authorization: Bearer <Codyssey에서 발급한 키>` |
| 기본 모델      | `gpt-5-mini`                                     |
| 입력           | `model`, `messages`                              |
| 생성 문구      | `choices[0].message.content`                     |

`AI_BASE_URL`에는 `/chat/completions`를 붙이지 않습니다. `https://copa.codyssey.kr`처럼 호스트만 넣으면 `/v1`을 보완합니다. 키를 URL에 넣지 않도록 인증정보·쿼리가 없는 HTTPS 주소만 허용합니다.

JSON 스키마를 프롬프트에 포함해 출력 형식을 요청하고 Python에서 검증합니다. 콘솔 예제에 없는 `response_format` 강제 기능이나 Responses 전용 필드는 사용하지 않습니다. Codyssey 콘솔에 표시되는 OpenAI 호환 키·모델 접근 권한과 잔여 토큰이 필요합니다. 제공 모델은 콘솔의 현재 목록을 확인하세요.

## 3. 처음 실행하기

코드나 문서를 수정한 뒤, 분석할 **저장소의 루트 폴더**에서 실행합니다. 처음 추가한 파일은 `git add`로 staged 상태로 만들어야 diff에 포함됩니다.

```bash
# 변경 파일과 diff 확인
git status
git diff

# 추가하거나 수정한 특정 파일을 선택하여 stage (분석 대상이 됨)
git add main.py

# API Key 없이, 전송할 요청 본문부터 확인
python main.py commit --dry-run

# 커밋 메시지 생성
python main.py commit

# 실제 커밋을 만들기 전에 PR 초안도 생성
python main.py pr
```

이 저장소를 처음 구현한 상태에서는 `main.py`, `gitgen/` 등이 untracked일 수 있습니다. 분석하려는 파일을 명시적으로 `git add`한 뒤 실행하세요. 이미 clone한 깨끗한 저장소라면 먼저 의미 있는 수정을 해야 합니다.

생성된 내용을 검토한 다음 직접 커밋·push·PR 작성을 진행합니다.

다른 저장소에서도 실행할 수 있습니다. 해당 저장소 루트로 이동한 뒤 이 도구의 Python과 `main.py`를 절대 경로로 지정하세요.

```bash
cd /path/to/target-repository
git add .
/path/to/B3-2/.venv/bin/python /path/to/B3-2/main.py pr --dry-run
```

## 4. 옵션

옵션은 `commit` 또는 `pr` **뒤에** 지정합니다.

| 옵션            | 기본값                       | 설명                                    |
| --------------- | ---------------------------- | --------------------------------------- |
| `--model`       | `AI_MODEL` 또는 `gpt-5-mini` | Codyssey 모델 ID                        |
| `--temperature` | 생략, 서버 기본값            | 생성 무작위성 0~2. 지원 모델에서만 지정 |
| `--max-tokens`  | `4096`                       | 추론을 포함한 생성 토큰 한도, 16~32768  |
| `--safe-mode`   | 비활성                       | 민감정보 마스킹과 전송량 제한 활성화    |
| `--dry-run`     | 비활성                       | API 호출 없이 마스킹된 요청 본문 출력   |

```bash
python main.py commit --model gpt-5-mini --max-tokens 4096
python main.py pr --safe-mode
```

과제 예시의 `-model`, `-temperature`, `-max-tokens`, `-safe-mode`도 별칭으로 지원합니다. 안전 모드는 기본적으로 꺼져 있으며, `--safe-mode` 옵션을 지정하면 활성화되어 민감 파일 제외, 비밀값 마스킹, 전송량 제한(최대 10개 파일·200줄)이 적용됩니다.

temperature가 낮을수록 표현의 무작위성을 줄이는 방향으로 작동하지만, 같은 결과나 사실 정확성을 보장하지는 않습니다. 모델별 지원 범위가 달라 기본 실행에서는 이 필드를 보내지 않습니다. `--temperature 0.4`처럼 명시하면 지정값을 전달하며, 해당 모델이 지원하지 않아 HTTP 400이 발생하면 옵션을 생략하도록 안내합니다.

`--max-tokens`는 문자 수가 아니라 생성 토큰 수의 상한이며 API의 `max_completion_tokens`에 전달됩니다. 추론 토큰도 포함하므로 너무 작으면 본문을 완성하기 전에 잘릴 수 있고, 너무 큰 값은 더 많은 사용량을 허용합니다. 기본값은 4096입니다. [Chat Completions 파라미터 참고](https://developers.openai.com/api/reference/cli/resources/chat/subresources/completions/methods/create).

## 5. 어떤 변경을 분석하나요?

- **staged 변경(`git diff --cached`)만** 분석합니다. 초안이 실제 다음 커밋에 들어갈 내용과 일치하도록 하기 위함입니다.
- 아직 `git add` 하지 않은 unstaged 변경은 분석하지 않습니다. 커밋할 변경을 `git add`로 먼저 stage하세요.
- untracked 파일도 목록만 안내하고 내용을 읽거나 전송하지 않습니다. 필요하면 `git add` 후 실행하세요.
- staged 변경이 없으면 `git add`로 stage하라는 안내 메시지를 출력하고 정상 종료합니다. API 호출은 0회입니다.
- PR 명령도 **staged 변경**을 분석합니다. 이미 커밋된 브랜치 전체와 기준 브랜치를 비교하지 않습니다. 초안은 커밋 전에 생성하세요.
- 병합 충돌이 있으면 먼저 해결해야 합니다. binary 파일은 Git이 제공하는 변경 사실만 전달합니다.

Git 수집에는 `git status`와 `git diff`만 사용합니다. 인덱스나 작업 파일을 수정하지 않으며 외부 diff 프로그램도 실행하지 않습니다.

## 6. 출력 예시

아래는 테스트용 모의 API 응답을 프로그램으로 렌더링한 예시입니다. **실제 Codyssey API 호출 결과나 실제 테스트 수행 증빙은 아닙니다.** 실제 응답은 diff와 입력 맥락에 따라 달라집니다.

키를 설정한 뒤 확인한 **실제 Codyssey 생성 결과**는 [API 검증 기록](docs/API_VERIFICATION.md)에 있습니다. 커밋·PR 모두 각각 API 1회로 생성에 성공했습니다.

```text
--- Change Summary ---
출력 메시지를 변경했습니다.

--- Commit Message ---
fix: 출력 메시지 수정

- app.py의 출력 메시지 변경
----------------------
```

```text
--- Change Summary ---
출력 메시지를 변경했습니다.

--- PR Title ---
fix: 출력 메시지 수정

--- PR Body ---
## Why
- 변경 배경 확인 필요

## What
- app.py의 출력 메시지 변경

## How to Test
- python app.py를 실행하여 변경된 출력 메시지를 확인

----------------------
```

결과는 표준 출력(stdout), 진행 상황·오류·API 호출 횟수는 표준 오류(stderr)에 출력합니다. 생성 텍스트를 파일로 저장하려면:

```bash
python main.py pr > /tmp/pr-draft.txt
```

이 파일에는 변경 요약과 구획 헤더도 포함되므로 PR 작성 시 필요한 제목·본문 구획을 복사합니다.

## 7. 검증과 오류 처리

커밋 제목은 최대 72자이며 50자를 넘으면 짧게 쓰도록 안내합니다. PR 제목은 최대 80자입니다. 앞뒤 공백을 제거한 Python `len()` 기준입니다. 제목의 줄바꿈·제어 문자, 빈 필드, 잘못된 JSON과 배열도 검증합니다.

커밋 본문에는 핵심 변경 1~2개를 불릿으로 넣습니다. PR의 Why·What·How to Test 헤더와 불릿은 Python에서 렌더링합니다. 형식 검사만으로 의미의 정확성을 보장할 수 없으므로 변경 내용·배경·테스트 사실은 사람이 확인해야 합니다.

| 상황                     | 처리 / 대응                                                                              |
| ------------------------ | ---------------------------------------------------------------------------------------- |
| Python 3.9 이하          | Python 3.10 이상으로 실행                                                                |
| 저장소 밖·하위 폴더      | `.git`이 있는 저장소 루트로 이동                                                         |
| API Key 없음             | 프로젝트 루트 `.env`의 `AI_API_KEY` 입력 또는 환경변수 설정. 미리보기는 `--dry-run` 사용 |
| HTTP 400                 | `--temperature` 생략, 모델의 지원 파라미터·토큰 한도 확인                                |
| HTTP 401 / 403 / 404     | Codyssey의 OpenAI 호환 키 / 프로토콜·모델 권한 / 기본 주소·모델명 확인                   |
| HTTP 429                 | Codyssey 콘솔의 잔여 토큰·키별 한도·요청 제한 확인                                       |
| 서버·네트워크 오류       | 네트워크 확인 후 재실행. 자동 재시도 없음                                                |
| 응답 미완료·출력 잘림    | `--max-tokens`를 늘리거나 분석 범위 축소                                                 |
| JSON·제목·필드 규칙 위반 | 위반 규칙을 전달해 1회 재생성                                                            |
| 재생성도 실패            | 오류를 표시하고 종료. 잘못된 초안을 최종 결과로 출력하지 않음                            |

정상 생성은 API 호출 1회, 형식 수정이 필요한 경우 총 2회입니다. 실패한 HTTP 요청도 호출 횟수에 포함합니다. HTTP 클라이언트에는 자동 재시도를 설정하지 않았습니다. 연결·읽기 대기 timeout은 각각 30초이며, 전체 실행 시간 상한을 뜻하지 않습니다.

종료 코드는 정상·변경 없음·미리보기 `0`, Git/API/검증 오류 `1`, 옵션·Python 버전 오류 `2`, 사용자 중단 `130`입니다.

## 8. 안전 모드와 비용

diff는 기본적으로 Codyssey의 OpenAI 호환 API로 전송됩니다. `--dry-run`으로 요청 주소와 마스킹된 실제 요청 본문을 먼저 확인할 수 있습니다. Key를 보내는 인증 헤더는 미리보기에 포함되지 않습니다.

| 정책           | 기준                                                                                               |
| -------------- | -------------------------------------------------------------------------------------------------- |
| 기본 제외      | `.env`, `.env.*`, `*.env`, 개인 키·인증서 파일(`.pem`, `.key` 등), `.ssh/`, `.aws/`, `.gnupg/`       |
| 이름 변경      | 이전 경로 또는 새 경로가 제외 대상이면 해당 변경 제외                                              |
| 마스킹         | 설정된 API Key, 알려진 토큰 형태(sk-, ghp- 등), 비밀번호·토큰 할당, 이메일, 인증 헤더, 개인 키 블록 |
| 적용 범위      | diff 본문, 전송할 파일명, 오류/안내 로그                                                            |
| 파일 수 제한   | staged 변경 경로순 최대 10개 파일                                                                  |
| diff 줄 수     | staged 변경 최대 200줄 (초과 시 잘림 및 부분 분석 안내)                                            |

제외되거나 잘린 입력이 있으면 “부분 분석”으로 표시합니다.

사용 한도와 모델별 차감 기준은 Codyssey API 콘솔에서 확인하고, 불필요한 반복 실행을 피하세요. 데이터 보존 방식은 Codyssey 및 연결된 제공자의 정책을 따릅니다.

## 9. 테스트

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

임시 Git 저장소와 모의 HTTP 응답으로 Git 상태, 신규·삭제·이름 변경·binary 파일명, 마스킹, 전송 한도(10개 파일·200줄), 제목 길이, commit/pr 프롬프트 격리, API 오류와 최대 2회 호출, CLI 전체 흐름을 확인합니다.

검증 결과: Python 3.12에서 **144개 자동 테스트 통과**. `.env` 로딩·환경변수 우선순위·키 비노출, Codyssey 요청 주소·인증·응답 형식과 재생성 흐름, commit/pr 전용 프롬프트 분리 격리를 검증했습니다. [실제 API 검증 기록](docs/API_VERIFICATION.md). Python 3.10 실행은 아직 검증하지 않았습니다.

다른 변경 내용으로 연결과 출력 품질을 다시 확인하려면 다음 명령을 사용하세요.

```bash
python main.py commit
python main.py pr
```

전송 가능한 staged diff가 있어야 호출됩니다. 실제 생성 결과를 diff와 대조해 사실성·누락·표현을 확인하고, 과제 제출 시 실제 실행 화면이나 출력 예시를 추가하세요.

## 10. 구조와 제출

| 파일                                     | 역할                                                     |
| ---------------------------------------- | -------------------------------------------------------- |
| `main.py` / `gitgen/cli.py`              | 진입점·옵션·실행 흐름                                    |
| `gitgen/config.py`                       | 환경변수·프로젝트 루트 `.env`에서 키·기본 주소·모델 로딩 |
| `gitgen/git_context.py`                  | Git 상태와 diff 수집                                     |
| `gitgen/safety.py`                       | 제외·마스킹·입력 제한                                    |
| `gitgen/prompts.py`                      | 커밋·PR 전용 분리 프롬프트·JSON 스키마                    |
| `gitgen/api_client.py`                   | Codyssey Chat Completions 요청·응답·HTTP 오류            |
| `gitgen/generation.py` / `validators.py` | 결과 검증·최대 1회 수정 요청                             |
| `gitgen/render.py`                       | 커밋·PR 텍스트 렌더링                                    |
| `tests/`                                 | 비용 없는 자동 검증                                      |

실제 Key로 commit/pr 생성 확인과 결과 기록을 완료했습니다. 제출 전에는 소스와 문서를 GitHub에 push해야 합니다. 도구가 원격 작업을 대신하지 않으므로 개발자가 직접 진행합니다. 선택 보너스인 이전 미션 PR·팀 컨벤션 설정·안전 모드 정책 커스터마이징은 이번 필수 구현에 포함하지 않았습니다.
