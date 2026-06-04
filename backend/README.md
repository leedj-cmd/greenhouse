# Greenhouse Backend API 서버 (DEPRECATED)

> ⚠️ **이 Node.js 백엔드는 더 이상 사용하지 않습니다.**
> 운영 백엔드는 `server/` (FastAPI + ONNX 추론) 로 통합되었습니다.
>
> | 항목 | 이 폴더 (backend/) | 운영 (server/) |
> |------|--------------------|----------------|
> | 상태 | Deprecated, 참고용 보존 | Active |
> | 추론 | Mock | ONNX (best_crop_model.onnx) |
> | 포트 | 3000 | 8000 |
> | 실행 | `npm run dev` | `uvicorn main:app --reload` |
>
> Node 코드의 자산 (한국어 메시지 사전, history pagination total, /health, confidence 임계값 0.9) 은
> 모두 `server/` 로 흡수되었습니다.
> 새로운 API 작업은 `server/routers/api.py` 에서 진행하세요.

---

비닐하우스 농장 질병 감지 앱의 REST API 서버입니다.

## 실행 방법

### 1. 의존성 설치
```bash
cd backend
npm install
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 DB 접속 정보 수정
```

### 3. DB 초기화 (최초 1회)
```bash
# greenhouse 루트 폴더에서 실행
psql -U postgres -c "CREATE DATABASE greenhouse_db;"
psql -U postgres -d greenhouse_db -f ../schema.sql
```

### 4. 서버 실행
```bash
# 개발 모드 (코드 변경 시 자동 재시작)
npm run dev

# 운영 모드
npm start
```

서버가 실행되면 `http://localhost:3000` 에서 접근 가능합니다.

## 엔드포인트 빠른 테스트

```bash
# 헬스체크
curl http://localhost:3000/health

# 밭 목록 조회
curl http://localhost:3000/api/v1/fields

# 특정 밭 상태 조회
curl http://localhost:3000/api/v1/status/1

# 분석 요청 (Mock 결과 반환)
curl -X POST http://localhost:3000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"field_id": 1, "image_base64": "iVBORw0KGgo="}'

# 히스토리 조회
curl "http://localhost:3000/api/v1/history?field_id=1&limit=5"
```

## 폴더 구조

```
backend/
├── app.js              # 서버 진입점
├── db.js               # PostgreSQL 연결
├── package.json
├── .env.example        # 환경변수 예시
├── routes/
│   ├── analyze.js      # POST /api/v1/analyze
│   ├── history.js      # GET  /api/v1/history
│   ├── status.js       # GET  /api/v1/status/:field_id
│   ├── fields.js       # GET  /api/v1/fields
│   └── notifications.js # PATCH /api/v1/notifications/:id/read
└── uploads/            # 분석 이미지 저장 폴더 (자동 생성)
```

## AI 모델 연동 방법

현재 `routes/analyze.js`의 `mockAnalyze()` 함수가 임시로 랜덤 결과를 반환합니다.  
ML 팀이 모델을 완성하면 아래 두 가지 방법 중 하나로 교체하세요.

### 방법 A — 온디바이스 (TFLite, Android에서 직접 처리)
- Android 앱에서 TFLite 모델로 분석 후, 결과값만 API로 전송
- `/analyze` 요청 body에 `disease_detected`, `disease_type`, `confidence` 추가

### 방법 B — 서버사이드 Python 모델
- Python AI 서버를 별도로 띄운 뒤 `mockAnalyze()`를 axios 호출로 교체
```js
// 예시
const aiResponse = await axios.post('http://ai-server:5000/predict', { image_base64 });
return aiResponse.data;
```
