시간표 배정 API
FastAPI 기반으로 구현한 자동 시간표 배정 서비스입니다.과목, 교사, 강의실 정보를 입력하면 조건에 맞는 충돌 없는 최적 시간표를 자동 생성하도록 설계되었습니다.

이 프로젝트는 다음과 같은 목표를 가지고 개발되었습니다:
FastAPI의 구조와 실제 서비스 개발 방식 이해
Router / Service / Models / Schemas 계층 분리 연습
시간표 배정 알고리즘 구현(교사 availability, 충돌 검사, 우선순위 배정 등)
MLOps 실습에서 배운 API 설계·데이터 검증을 실제 프로젝트에 적용
교육용 스케줄링 문제를 백엔드 관점에서 해결하는 경험 제공

 파일 구성 설명
아래는 현재 프로젝트의 주요 파일 역할 설명입니다.
main.py
FastAPI 앱의 엔트리포인트
라우터 등록, 서버 실행
미들웨어(예: CORS) 설정 포함 가능
router.py
시간표 배정 관련 API 엔드포인트 정의
예: /assign, /schedule, /teacher
요청을 받아 service 레이어로 전달
schemas.py
Request / Response 형식을 정의하는 Pydantic 모델
입력값 유효성 검증 자동 처리
models.py
내부에서 사용하는 데이터 모델 구조예: Teacher, Subject, Classroom, Timeslot 등
service.py
• 
실제 시간표 배정 알고리즘 로직 구현
충돌 검사 / 배정 규칙 / 우선순위 정렬 / 백트래킹 로직 포함

자동 배정 알고리즘 요약
프로젝트는 아래 구조로 시간표를 생성합니다:
✔ 1) 입력 데이터 검증 (schemas.py)
Pydantic 기반으로 JSON 요청을 자동 검증
비어 있는 필드나 잘못된 타입을 자동 체크
✔ 2) 충돌 검사 로직 (service.py)
같은 시간대 교사 중복 불가
같은 시간대 강의실 중복 불가
교사 availability 범위 내에서만 배정
하루 최대 시간(limit) 검사
✔ 3) 우선순위 기반 배정
시간이 많은 과목 → 먼저 배정
가능한 요일이 적은 교사 → 먼저 배정
강의실 부족할 경우 작은 교실부터 배정
✔ 4) 백트래킹(Backtracking) 처리
충돌 발생 시 이전 단계로 되돌아가고
다른 조합을 재시도하여 가능한 시간표를 찾아냄
✔ 5) 최종 검증 후 결과 반환
중복 배정 확인
요일/시간 순서로 정렬하여 반환


Client (Swagger UI / 외부 요청)
                │
                ▼
        ┌────────────┐
        │   Router    │  router.py
        └────────────┘
                │
                ▼
        ┌────────────┐
        │  Service    │  service.py
        └────────────┘
                │
        ┌────────────┐
        │  Models     │  models.py
        └────────────┘
                │
        ┌────────────┐
        │ Schemas     │  schemas.py
        └────────────┘
                │
                ▼
      JSON 형태로 일정 반환

