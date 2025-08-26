# QA_FAST

간단한 FastAPI 기반 서비스 스켈레톤입니다.

## 요구 사항
- Python 3.10+

## 설치 및 실행 (Windows PowerShell)
```powershell
cd QA_FAST
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 헬스체크
- GET /healthz → { "status": "ok" }

## 테스트 실행
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
