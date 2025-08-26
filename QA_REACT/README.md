# QA_REACT

간단한 WS/SSE 채팅 클라이언트입니다. 서버는 QA_FAST(pub 8000, sub 8001)를 사용합니다.

## 실행
1) 의존성 설치
```
npm i
```

2) 개발 서버 실행
```
npm run dev
```

3) 접속
- http://127.0.0.1:5173

프록시
- `/ws` → pub(8000) WS
- `/sse` → sub(8001) SSE


