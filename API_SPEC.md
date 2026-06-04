# Greenhouse Disease Detection — REST API 명세

**Base URL**: `http://<server-host>:8000`
**Content-Type**: `application/json` (특별히 명시한 엔드포인트는 `multipart/form-data`)
**버전**: 2.0 | **최종 수정**: 2026-06-04

> 운영 백엔드는 `server/` (FastAPI + ONNX). `backend/` (Node) 는 deprecated.
> OpenAPI 자동 문서: `http://<host>:8000/docs`, `http://<host>:8000/redoc`

---

## 인증

MVP 단계에서는 인증 없음. 추후 `Authorization: Bearer <JWT>` 헤더 추가 예정.

---

## 공통 응답 규칙

| HTTP 상태 | 의미 |
|-----------|------|
| 200 | 정상 |
| 400 | 잘못된 요청 (필수 파라미터 누락 등) |
| 404 | 리소스를 찾을 수 없음 |
| 422 | 유효성 검증 실패 (FastAPI Pydantic) |
| 500 | 서버 내부 오류 |

오류 응답 예 (FastAPI 기본):
```json
{ "detail": "구역을 찾을 수 없습니다." }
```

---

## 식별자 / Enum 정의

### `field_id`
**UUID v4 문자열.** (이전 1~5 정수에서 변경)
구역 이름(`a1`~`e4`, 총 20개)으로 lookup은 `GET /fields` 결과에서 `name` → `id`로 수행.

### `disease_type` (대문자 단어, 23 클래스를 8 카테고리로 매핑)

| 값 | 한국어 |
|----|--------|
| `NORMAL` | 정상 |
| `BLIGHT` | 역병 |
| `RUST` | 녹병 |
| `SPOT` | 점무늬병 |
| `MOSAIC` | 모자이크바이러스 |
| `MOLD` | 잎곰팡이병 |
| `ROT` | 검은썩음병 |
| `PEST` | 응애 |
| `UNKNOWN` | 판별 불가 |

### `field.status` (구역 색상 표시용)

| 값 | 의미 | 판정 룰 |
|----|------|---------|
| `NORMAL` | 정상 | `disease_type == NORMAL` |
| `WARNING` | 주의 | 질병 감지 + `confidence < 0.9` |
| `DANGER` | 위험 | 질병 감지 + `confidence >= 0.9` |

### `inference_source`

| 값 | 의미 |
|----|------|
| `server` | 서버 ONNX 추론 (`best_crop_model.onnx`) |
| `ondevice` | 앱(Android)이 TFLite로 미리 추론한 결과 사용 |

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |
| POST | `/analyze` | 이미지 업로드 → AI 분석 → 결과 저장 |
| GET | `/fields` | 전체 구역 목록 + 각 구역 최신 분석 결과 |
| GET | `/status/{field_id}` | 특정 구역 상세 상태 |
| GET | `/history` | 분석 히스토리 (페이지네이션) |
| GET | `/images` | 이미지 갤러리 |
| GET | `/notifications` | 미확인 알림 목록 |
| PATCH | `/notifications/{id}/read` | 알림 읽음 처리 |
| POST | `/admin/seed` | 구역 데이터 수동 시드 (테스트용) |
| POST | `/admin/run-daily-capture` | 일일 자동 캡처 즉시 실행 (테스트용) |

정적 마운트 (앱이 호출할 일은 없지만 참고):

| 경로 | 내용 |
|------|------|
| `/admin/` | 관리자 웹 대시보드 (`admin/index.html`) |
| `/images/<uuid>.jpg` | 업로드된 분석 이미지 |
| `/` | `/admin/` 로 리다이렉트 |

---

## 1. GET `/health`

서버 가동 여부 확인.

응답 `200`:
```json
{ "status": "ok", "timestamp": "2026-06-04T07:35:14.123456+00:00" }
```

---

## 2. POST `/analyze`

이미지를 멀티파트로 받아 분석한 후 결과를 저장하고 (질병 시) 알림을 생성한다.

### 요청 — `multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `field_id` | UUID | Y | `GET /fields` 의 `id` |
| `file` | binary | Y | JPEG / PNG 이미지 |
| `disease_type` | string | N | 앱이 TFLite로 미리 분석한 결과. 주면 서버 추론 생략 |
| `confidence` | float (0~1) | N | 앱 추론 신뢰도. `disease_type` 과 함께 줘야 함 |

### 응답 `200`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "field_id": "1d02255a-115c-4f9e-8719-361855603486",
  "image_id": "9c38c6c0-3a6f-474c-97a6-aec4030148b0",
  "disease_type": "RUST",
  "confidence": 0.99,
  "analyzed_at": "2026-06-04T16:28:47.024042",
  "notification_sent": true,
  "message": "녹병이 감지되었습니다",
  "field_status": "DANGER",
  "inference_source": "server"
}
```

### curl 예시

```bash
# 서버 ONNX 추론
curl -X POST http://localhost:8000/analyze \
  -F "field_id=1d02255a-115c-4f9e-8719-361855603486" \
  -F "file=@leaf.jpg"

# 앱 TFLite 결과 전송 (서버 추론 생략)
curl -X POST http://localhost:8000/analyze \
  -F "field_id=1d02255a-115c-4f9e-8719-361855603486" \
  -F "file=@leaf.jpg" \
  -F "disease_type=BLIGHT" \
  -F "confidence=0.92"
```

### 오류

| 코드 | 상황 |
|------|------|
| 404 | `field_id` 에 해당하는 구역 없음 |
| 422 | `file` 누락 또는 `field_id` UUID 형식 오류 |

---

## 3. GET `/fields`

전체 20개 구역 (a1~e4) + 각 구역 최신 분석 결과를 반환한다.
관리자 대시보드 / 앱의 Farm 화면 초기 로딩에서 사용.

### 응답 `200`

```json
[
  {
    "id": "1d02255a-115c-4f9e-8719-361855603486",
    "name": "a1",
    "location": "구역 A-1",
    "status": "DANGER",
    "created_at": "2026-06-04T16:28:07.327048",
    "latest_analysis": {
      "id": "80743a62-f559-488e-81be-9c93a475bfa9",
      "disease_type": "RUST",
      "confidence": 0.99,
      "analyzed_at": "2026-06-04T16:28:47.024042",
      "image_path": "/images/cc901aa4-3ee4-4652-8a6c-7651de48b056.JPG"
    }
  },
  { "id": "...", "name": "a2", "status": "NORMAL", "latest_analysis": null }
]
```

`latest_analysis` 는 분석 이력이 없는 구역에서 `null`.

---

## 4. GET `/status/{field_id}`

특정 구역 1개의 상세 상태. 응답 구조는 `/fields` 의 1개 항목과 동일.

### 경로 파라미터

| 이름 | 타입 |
|------|------|
| `field_id` | UUID |

### 오류

| 코드 | 상황 |
|------|------|
| 404 | 해당 UUID 구역 없음 |

---

## 5. GET `/history`

분석 히스토리 (최신순). 페이지네이션 + 구역 필터 + 질병만 필터.

### 쿼리 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---------|------|------|------|
| `field_id` | UUID | - | 특정 구역만 조회 |
| `limit` | int | 20 | 최대 100 |
| `offset` | int | 0 | 페이지네이션 |
| `disease_only` | bool | false | true 시 `NORMAL` 제외 |

### 응답 `200`

```json
{
  "data": [
    {
      "id": "80743a62-f559-488e-81be-9c93a475bfa9",
      "field_id": "955c25d2-99e9-46fc-a57b-e034d8ed3244",
      "disease_type": "RUST",
      "confidence": 0.99,
      "analyzed_at": "2026-06-04T16:28:47.024042",
      "image_path": "/images/cc901aa4-3ee4-4652-8a6c-7651de48b056.JPG"
    }
  ],
  "total": 27,
  "limit": 20,
  "offset": 0
}
```

---

## 6. GET `/images`

이미지 갤러리 (Image 화면). 분석 결과(질병명/신뢰도)와 함께 반환.

### 쿼리 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---------|------|------|------|
| `field_id` | UUID | - | 특정 구역만 |
| `limit` | int | 30 | |
| `offset` | int | 0 | |

### 응답 `200`

```json
[
  {
    "id": "9c38c6c0-3a6f-474c-97a6-aec4030148b0",
    "field_id": "1d02255a-115c-4f9e-8719-361855603486",
    "field_name": "a1",
    "file_path": "/images/cc901aa4-3ee4-4652-8a6c-7651de48b056.JPG",
    "file_size_kb": 11,
    "captured_at": "2026-06-04T16:28:47.024042",
    "disease_type": "RUST",
    "confidence": 0.99
  }
]
```

---

## 7. GET `/notifications`

미확인 알림 (`is_read=false`) 만 최신순 반환. 앱이 폴링하는 엔드포인트.

### 응답 `200`

```json
[
  {
    "id": "5cd74a80-8ccd-414e-aa65-d7bd157b86be",
    "field_id": "955c25d2-99e9-46fc-a57b-e034d8ed3244",
    "message": "[b1] 녹병이 감지되었습니다 (신뢰도 99%)",
    "is_read": false,
    "created_at": "2026-06-04T16:28:47.024042"
  }
]
```

---

## 8. PATCH `/notifications/{id}/read`

알림을 읽음 상태로 표시. 앱이 푸시 팝업 닫을 때 호출.

### 경로 파라미터

| 이름 | 타입 |
|------|------|
| `id` (== `notification_id`) | UUID |

### 응답 `200`

```json
{ "message": "읽음 처리 완료" }
```

### 오류

| 코드 | 상황 |
|------|------|
| 404 | 알림 없음 |

---

## 9. POST `/admin/seed`

구역 데이터가 비어있을 때 a1~e4 (20개) 를 수동으로 생성. 서버 첫 기동 시 자동 실행되므로 일반적으로는 호출 불필요.

### 응답 `200`

```json
{ "message": "시드 완료" }
```

---

## 10. POST `/admin/run-daily-capture`

매일 14:00 KST 자동 실행되는 일일 캡처를 즉시 트리거 (테스트용).
`SCHEDULER_IMAGE_DIR` 의 이미지에서 각 구역마다 1장씩 무작위로 뽑아 `/analyze` 와 동일한 흐름을 수행.

### 응답 `200`

```json
{
  "processed": 20,
  "alerts": 16,
  "details": [
    {
      "field": "a1",
      "image": "AppleCedarRust1.JPG",
      "disease": "RUST",
      "confidence": 0.98,
      "status": "DANGER",
      "alert": true
    }
  ]
}
```

---

## Android / Flutter 연동 참고

### Retrofit 인터페이스 예

```java
public interface GreenhouseApi {

    @Multipart
    @POST("analyze")
    Call<AnalyzeResponse> analyze(
        @Part("field_id")     RequestBody fieldId,
        @Part MultipartBody.Part file,
        @Part("disease_type") RequestBody diseaseType,  // null 가능
        @Part("confidence")   RequestBody confidence    // null 가능
    );

    @GET("fields")
    Call<List<FieldResponse>> getFields();

    @GET("status/{field_id}")
    Call<FieldResponse> getStatus(@Path("field_id") String fieldId);

    @GET("history")
    Call<HistoryListResponse> getHistory(
        @Query("field_id")     String  fieldId,    // null 가능
        @Query("limit")        int     limit,
        @Query("offset")       int     offset,
        @Query("disease_only") boolean diseaseOnly
    );

    @GET("notifications")
    Call<List<NotificationResponse>> getNotifications();

    @PATCH("notifications/{id}/read")
    Call<MessageResponse> markRead(@Path("id") String id);
}
```

### Base URL

| 환경 | URL |
|------|-----|
| Android 에뮬레이터 | `http://10.0.2.2:8000` |
| iOS 시뮬레이터 | `http://localhost:8000` |
| 실제 기기 (같은 LAN) | `http://<컴퓨터-IP>:8000` |

CORS 는 `*` 허용 (MVP 단계).

---

## 데이터 흐름 요약

```
[A] 앱이 촬영한 사진 업로드 (사용자/수동)
    Camera → POST /analyze (multipart, optional ondevice 결과)
    → uploaded_images/<uuid>.jpg 저장
    → ONNX 또는 ondevice 결과로 분석
    → analysis_results + (질병이면) notifications INSERT
    → fields.status UPDATE
    → 응답에 message + field_status + inference_source 포함

[B] 매일 14:00 KST 자동 캡처 (스케줄러)
    APScheduler CronTrigger
    → 전 구역(20개) 순회
    → SCHEDULER_IMAGE_DIR 에서 임의 이미지 선택
    → 위 [A] 와 동일한 분석 흐름

[C] 관리자/앱이 폴링
    GET /fields        → 4x5 그리드 색상
    GET /notifications → 미확인 알림 목록
    PATCH /notifications/{id}/read → 팝업 닫기
```

---

## 환경 변수

`server/.env` (`server/.env.example` 참고):

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=greenhouse_db
DB_USER=postgres
DB_PASSWORD=...

IMAGE_UPLOAD_DIR=./uploaded_images

# 일일 자동 캡처 스케줄러
SCHEDULER_ENABLED=true
SCHEDULE_HOUR=14
SCHEDULE_MINUTE=0
SCHEDULE_TZ=Asia/Seoul
SCHEDULER_IMAGE_DIR=../kaggle_dataset/test/test
```

---

## 변경 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|---------|
| 1.0 | 2026-05-27 | 최초 작성 (Node.js 백엔드, int field_id, base64 이미지, `/api/v1` prefix) |
| 2.0 | 2026-06-04 | FastAPI 백엔드 기준 전면 재작성. UUID field_id, multipart 업로드, prefix 제거. `inference_source`/`field_status`/`message` 추가. `/images`, `/health`, `/admin/run-daily-capture` 신규. disease_type 8개 enum 정정 |
