# 개인용 채용 에이전트

현재 구현: Lever/Greenhouse 공고 수집 → 인턴·신입·주니어 제목 및 직무 필터 → 사용자별 SQLite 기록 → 새 공고 Discord webhook 알림. 실패한 알림은 다음 실행에서 재시도합니다. 서버 응답 후 DB 기록 전 종료되면 중복 알림이 생길 수 있습니다.

현재 미구현: Gmail OAuth 및 메일 분석, Notion 동기화, Google Calendar 일정 생성·갱신, 지원 자료 생성 및 승인 후 제출. 계정 연결이나 상시 실행은 아직 설정되지 않았습니다.

## 최종 목표를 기준으로 커리어 경로 검토

최종 목표는 **모터스포츠·야구·스포츠 업계에서 일하기, 분야 우선순위는 모터스포츠 → 야구 → 기타 스포츠**로 설정합니다. 데이터 분석은 여러 후보 직무 중 하나입니다. 현재 경험으로 해당 업계에 직접 지원하는 경로와 다른 업계에서 필요한 경험을 쌓고 이동하는 경로를 비교합니다. 순서는 `domain_priorities` 배열에서 변경합니다. `role_scope: industry_entry`는 업계 진입을 목표로 직무 범위를 넓게 검토하는 설정입니다.

`career-goal.example.json`을 `career-goal.local.json`으로 복사해 사용합니다. 개인 설정과 이력서용 `resumes/` 폴더는 Git에서 제외합니다. 이력서는 UTF-8 Markdown/TXT 형식을 지원합니다.

```sh
python3 career.py
python3 career.py --resume resumes/resume.md
```

결과는 `data/career-roadmap.md`에 저장합니다. 이력서에 언급된 경험의 원문과 미확인 역량, 경로별 선택 조건·중간 단계·검증 기준·한계를 표시합니다. **첫 버전은 규칙과 경로 템플릿 기반 초안이며, AI가 개인별 최적 경로를 결정하는 엔진은 아직 아닙니다.** 기술이 언급됐다는 사실을 숙련도나 지원 가능성으로 해석하지 않습니다. 이력서가 없으면 후보 경로를 보여줄 뿐 개인별 순위를 정하지 않습니다. 학위·비자·경력 요건의 자동 검증과 실제 공고 기반 경로 갱신은 후속 구현이 필요합니다.

공고 수집에서는 희망 업계 관련 단서가 있는 공고를 모터스포츠 → 야구 → 기타 스포츠 순으로 정렬합니다. 해당 업계 공고는 개발·분석뿐 아니라 기술 지원·운영 등도 직무 키워드 제한 없이 검토합니다. 같은 업계에서 분석 직무를 개발이나 다른 직무보다 자동 우대하지 않습니다. 그 뒤에 업계 이동을 위한 기술 경험 후보와 연관 미확인 공고를 표시합니다. 여러 분야가 함께 언급되면 우선순위가 높은 분야를 선택합니다. Discord 알림에는 분야와 목표 연결 이유를 표시하고 미전송 알림도 같은 순서로 처리합니다. 이는 키워드 근거이며 회사의 실제 사업이나 업무 범위를 확정하지 않습니다. 기존 신입·인턴·경력 제한 필터는 그대로 적용합니다. 제목에 신입·인턴 표현이 없는 공고는 여전히 누락될 수 있습니다. 개인별 직무 적합성은 아직 자동 판별하지 않습니다. 기본 수집처는 여전히 Palantir 한 곳이며 스포츠 관련 회사 보드는 별도 추가가 필요합니다.

## 실행

Python 3.10 이상, 외부 패키지 설치 없이 실행합니다. 이 디렉터리에서:

```sh
python3 agent.py --dry-run
python3 -m unittest -v
```

`.env.example`을 `.env`로 복사하고 Discord 채널 설정 → 연동 → 웹후크에서 만든 URL을 로컬 `.env`에 입력합니다. 다음 명령은 실제 Discord 전송을 합니다.

```sh
python3 agent.py
python3 agent.py --loop
```

`--loop`는 즉시 첫 실행 후 설정된 간격으로 반복합니다. 터미널 종료나 컴퓨터 절전 중에는 실행되지 않습니다. 상시 운영하려면 서버와 프로세스 관리 또는 OS 스케줄러 구성이 추가로 필요합니다.

## 검색 범위

`config.json`의 sources에 회사별 채용 보드를 추가하세요. 기본값은 Palantir Lever 보드 하나입니다. 전체 인터넷 검색이나 국내 채용 사이트 수집은 아직 구현하지 않았습니다. Greenhouse는 `{"provider":"greenhouse","company":"회사 보드 토큰"}` 형식입니다.

첫 필터는 키워드 방식입니다. 제목에 경력 수준이 없는 신입 가능 공고는 누락될 수 있고, 졸업 시기·비자·Python 사용 여부는 아직 판별하지 않습니다. 다음 단계에서 본문 기반 구조화와 사용자 이력 비교가 필요합니다. 지역 제한은 없습니다.

## 확정한 후속 연동 설계

- Gmail: Google OAuth 로그인과 `gmail.readonly` 권한. `채용` 라벨로 범위를 좁혀 처리하되, OAuth 권한 자체는 해당 라벨에만 한정되지 않습니다. Google Cloud 프로젝트, Gmail/Calendar API 활성화, OAuth 클라이언트가 필요합니다.
- Google Calendar: 별도 채용 캘린더에 일정 저장, 원문 메일 ID와 이벤트 ID를 매핑해 변경·취소를 반영. 시각이나 시간대가 모호하면 확인 대기 상태로 둡니다.
- Notion: 통합 토큰과 공유된 데이터 소스에 회사·공고·지원 상태·마감·면접·캘린더 링크 저장. 사용자/공고별 외부 항목 ID를 저장해 중복 생성을 방지합니다.
- Discord: 첫 버전은 webhook 알림. 지원 승인 버튼은 별도 봇과 상호작용 처리 기능이 필요합니다.
- 이메일 내용은 데이터로만 처리하고 메일 안의 지시로 도구를 실행하지 않습니다. 일정 후보와 지원 초안은 검토 상태를 거칩니다.
- Gmail과 Calendar는 같은 Google 계정으로 연동할 수 있습니다. 이메일 주소만으로 연결되지 않으며, 비밀번호를 수집하지 않습니다. 토큰은 로컬 secrets 폴더에 두고 버전 관리에서 제외합니다. 서비스 확장 시 사용자별 암호화 저장·연결 해제 구현이 필요합니다.

공식 문서: [Lever](https://github.com/lever/postings-api), [Greenhouse](https://docs.greenhouse.io/job-board.html), [Discord webhook](https://docs.discord.com/developers/resources/webhook), [Gmail 권한](https://developers.google.com/workspace/gmail/api/auth/scopes), [Calendar 권한](https://developers.google.com/workspace/calendar/api/auth).
