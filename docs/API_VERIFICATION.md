# Codyssey 실제 API 검증 기록

검증일: 2026-09-10

프로젝트 `.env`에 설정된 키로 Codyssey 서버에 실제 요청하여 커밋 메시지와 PR 초안 생성을 확인했다. 키를 출력하거나 기록하지 않았다.

| 항목             | 결과                                           |
| ---------------- | ---------------------------------------------- |
| 요청 주소        | `https://copa.codyssey.kr/v1/chat/completions` |
| 모델             | `gpt-5-mini`                                   |
| 커밋 생성        | 성공, API 1회, 종료 코드 0                     |
| PR 생성          | 성공, API 1회, 종료 코드 0                     |
| 재생성           | 두 명령 모두 불필요                            |
| 총 실제 API 호출 | 2회                                            |

## 검증 범위

임시 Git 저장소에 `greetings.py`를 만들고 이름 앞뒤의 공백을 제거하며 공백만 입력하면 `ValueError`를 발생시키는 작은 변경을 staged 상태로 준비했다. 프로젝트 `.env`를 읽은 뒤 같은 프로세스에서 실제 CLI의 `main()`에 `commit`과 `pr`을 각각 전달했다. CLI는 항상 staged 변경만 분석하므로 별도의 staged 옵션은 사용하지 않았다. 각 명령은 별도의 임시 저장소에서 실행했다. 프로그램 본체의 Git 수집·안전 처리·REST 요청·응답 검증·출력 과정을 사용했으며 API 응답을 모의 처리하지 않았다.

API 요청 전에 샘플 함수가 아래 두 조건을 만족하는지 실제로 검사했다 (초기 검증 당시에는 `--test-context`를 사용했으나, 현재는 CLI가 diff 기반으로 단순화되어 옵션 없이 실행함).

- `greet(" Alice ")` → `"Hello, Alice!"`
- `greet("   ")` → `ValueError`

생성된 제목은 길이·한 줄 규칙을 통과했고, PR에는 Why·What·How to Test 섹션과 불릿이 포함되었다. 두 결과를 샘플 diff와 대조해 입력 정리·빈 이름 예외 처리·실제 테스트 결과를 올바르게 설명하는지 확인했다. 원래 프로젝트의 인덱스·커밋·원격 저장소는 변경하지 않았다.

이 기록은 작은 텍스트 변경에 대한 성공 사례다. 모든 모델·입력 크기·오류 상황의 실제 서버 동작을 보장하지 않는다. 토큰 사용량은 별도로 수집하지 않았으며, 잔여량은 Codyssey 콘솔에서 확인할 수 있다.

## 실제 커밋 생성 출력

```text
Exit code: 0
[INFO] Git status 수집 완료: 1개 파일 변경 감지
[INFO] M  'greetings.py'
[INFO] 안전 처리 완료: diff 11줄, 민감 파일 제외 0개, 한도 제외 0개, 잘린 diff 0개
[INFO] AI API 요청 중...
[DONE] 초안 생성 완료. 내용과 테스트 사실을 검토한 뒤 복사하여 적용하세요.
[INFO] API 호출 횟수: 1회

--- Change Summary ---
greet 함수에서 입력 이름을 strip하여 공백만 입력된 경우 ValueError를 발생시키도록 검증을 추가하고, 정상 입력은 공백을 제거한 값으로 인사말을 반환하도록 변경함.

--- Commit Message ---
fix: 공백만 입력된 이름으로 인사말 생성 오류 방지

- name.strip()로 입력을 정리하고 정리된 이름이 비어있으면 ValueError("Name is required")를 발생시킴
- 정상 입력의 경우 공백이 제거된 이름으로 포맷된 인사말을 반환하도록 greet 함수 반환값을 변경함
----------------------
```

## 실제 PR 생성 출력

```text
Exit code: 0
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
- 이전 구현은 입력값에 공백만 들어오면 빈 이름으로 인사말을 생성하는 문제를 발생시킬 수 있음
- 사용자 입력을 정리하고 필수 입력 누락을 명확하게 처리하기 위해 입력값을 strip하고 비어있으면 예외를 던지도록 함

## What
- name.strip()로 앞뒤 공백을 제거하여 clean_name 변수에 저장하도록 변경함
- clean_name이 비어있으면 ValueError("Name is required")를 발생시키고, 그렇지 않으면 clean_name으로 인사말을 반환하도록 수정함

## How to Test
- greet(" Alice ")가 "Hello, Alice!"을 반환하는지 확인함 (검증: 통과)
- greet("   ")가 ValueError를 발생시키는지 확인함 (검증: 통과)

----------------------
```
