# QA_FAST

간단한 FastAPI 기반의 pub/sub 구조 예제입니다. `pub`(8000)과 `sub`(8001) 두 서버와 Postgres(포트 5433)를 사용합니다.

## 선행 요구 사항
- Windows PowerShell
- Docker Desktop (Compose)
- Python 3.10+

## 1) Postgres 컨테이너 기동
```powershell
cd QA_FAST
docker compose up -d
```

기본 접속 정보: `postgres:postgres@localhost:5433/qa_fast`

## 2) 가상환경 생성 및 의존성 설치
```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r pub\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r sub\requirements.txt
```

## 3) sub 서버 실행 (포트 8001)
```powershell
setx DATABASE_URL "postgresql+psycopg://postgres:postgres@localhost:5433/qa_fast"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir sub --host 0.0.0.0 --port 8001 --reload
```

## 4) pub 서버 실행 (포트 8000)
`pub`은 `sub`에 메시지를 전송하므로 `SUB_BASE_URL` 환경 변수 설정을 권장합니다.
```powershell
$env:SUB_BASE_URL = "http://127.0.0.1:8001"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir pub --host 0.0.0.0 --port 8000 --reload
```

## 5) 헬스 체크
- pub:  GET http://127.0.0.1:8000/healthz → { "status": "ok" }
- sub:  GET http://127.0.0.1:8001/healthz → { "status": "ok" }

## 참고
- DB 데이터는 `./.data/postgres` 볼륨에 영속화됩니다.
- 기본 DB URL은 코드에서 `postgresql+psycopg://postgres:postgres@localhost:5433/qa_fast` 로 설정되어 있습니다.


