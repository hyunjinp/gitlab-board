# GitLab Issue & Commit Dashboard

FastAPI 기반의 백엔드와 순수 HTML/CSS/JS 프론트엔드로 구성된 GitLab 대시보드입니다. GitLab API와 MariaDB를 활용해 여러 프로젝트의 이슈와 커밋 현황을 한 화면에서 관리할 수 있습니다.

## 주요 기능
- **설정**: GitLab 서버 URL과 Private Token을 저장/불러오기.
- **레포지토리 선택**: 프로젝트 ID를 등록하고 메타데이터 동기화.
- **이슈 현황**
  - 여러 프로젝트의 이슈를 조회하고 담당자별 건수 요약 표시.
  - 제목/내용, 생성자, 담당자, 라벨, 분류, 비고로 검색.
  - 비고/분류 필드 입력 후 저장.
  - 선택 이슈 일괄 Close 및 최신 이슈 새로고침.
  - Excel(xlsx) 다운로드.
- **커밋 현황**: 담당자별 주간 커밋/코드 변경량을 그래프로 표시.

## 실행 방법
1. 의존성 설치
   ```bash
   pip install -r requirements.txt
   ```
2. DB 연결 정보 설정 (기본: `mysql+aiomysql://gitlab_user:gitlab_pass@localhost:3306/gitlab_board`)
   ```bash
   export DATABASE_URL="mysql+aiomysql://<user>:<password>@<host>:<port>/<db>"
   ```
3. 서버 실행
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. 브라우저에서 `http://localhost:8000` 접속.

## 개발 메모
- 첫 요청 시 DB 스키마가 자동 생성됩니다.
- GitLab API는 Private Token 헤더(`PRIVATE-TOKEN`)를 사용합니다.
- 커밋 통계는 지정한 주 수(기본 8주) 동안의 커밋과 라인 변경량을 집계합니다.
