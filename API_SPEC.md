# Greenhouse Disease Detection — REST API 명세

**Base URL**: `http://<server-host>:3000/api/v1`  
**Content-Type**: `application/json`  
**버전**: 1.0 | **최종 수정**: 2026-05-27

---

## 인증

> MVP 단계에서는 인증 없이 운영. 추후 `Authorization: Bearer <JWT>` 헤더 추가 예정.

---

## 공통 에러 응답

| HTTP 상태 | 의미 |
|-----------|------|
| 400 | 잘못된 요청 (필수 파라미터 누락 등) |
| 404 | 리소스를 찾을 수 없음 |
| 500 | 서버 내부 오류 |

```json
{
  "error": "에러 메시지",
  "code": "ERROR_CODE"
}
```

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/analyze` | 이미지 분석 요청 & 결과 저장 |
| GET | `/history` | 분석 히스토리 조회 |
| GET | `/status/:field_id` | 특정 밭 현재 상태 조회 |
| GET | `/fields` | 전체 밭 목록 조회 |
| PATCH | `/notifications/:id/read` | 알림 읽음 처리 |

---

## 1. POST `/analyze`

이미지를 받아 AI 모델로 질병을 분석하고 결과를 DB에 저장합니다.  
질병이 감지된 경우 알림 레코드도 함께 생성됩니다.

### 요청

```json
{
  "field_id": 1,
  "image_base64": "iVBORw0KGgoAAAANS...",
  "timestamp": "2026-05-27T12:30:00Z"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `field_id` | integer | ✅ | 분석 대상 밭 ID (1~5) |
| `image_base64` | string | ✅ | Base64 인코딩된 이미지 (JPEG/PNG) |
| `timestamp` | string (ISO 8601) | ❌ | 촬영 시각. 생략 시 서버 수신 시각 사용 |

### 응답 `200 OK`

```json
{
  "analysis_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "field_id": 1,
  "disease_detected": true,
  "disease_type": "powdery_mildew",
  "confidence": 0.92,
  "message": "가루병이 감지되었습니다",
  "timestamp": "2026-05-27T12:30:05Z"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `analysis_id` | UUID | 분석 결과 고유 ID |
| `field_id` | integer | 분석된 밭 ID |
| `disease_detected` | boolean | 질병 감지 여부 |
| `disease_type` | string \| null | 감지된 질병 유형. 정상이면 `null` |
| `confidence` | float (0.0~1.0) | 모델 신뢰도 |
| `message` | string | 사용자 표시용 메시지 |
| `timestamp` | string (ISO 8601) | 분석 완료 시각 |

**disease_type 값 목록**

| 값 | 설명 |
|----|------|
| `powdery_mildew` | 흰가루병 |
| `leaf_spot` | 점무늬병 |
| `blight` | 역병 |
| `gray_mold` | 잿빛곰팡이병 |
| `mosaic_virus` | 모자이크바이러스 |

### 에러

```json
// 400 — field_id 범위 초과
{ "error": "유효하지 않은 field_id입니다.", "code": "INVALID_FIELD_ID" }

// 400 — 이미지 누락
{ "error": "image_base64는 필수입니다.", "code": "MISSING_IMAGE" }
```

---

## 2. GET `/history`

분석 히스토리를 최신순으로 조회합니다.

### 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `field_id` | integer | ❌ | 없음 (전체) | 특정 밭만 조회 |
| `limit` | integer | ❌ | 20 | 최대 반환 건수 (max 100) |
| `offset` | integer | ❌ | 0 | 페이지네이션 오프셋 |
| `disease_only` | boolean | ❌ | false | true 시 질병 감지된 결과만 반환 |

### 예시 요청

```
GET /api/v1/history?field_id=1&limit=10&disease_only=true
```

### 응답 `200 OK`

```json
{
  "data": [
    {
      "analysis_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "field_id": 1,
      "disease_detected": true,
      "disease_type": "powdery_mildew",
      "confidence": 0.92,
      "image_url": "/images/3fa85f64.jpg",
      "timestamp": "2026-05-27T12:30:00Z"
    },
    {
      "analysis_id": "7d94e321-1234-4abc-9ef0-aabbccddeeff",
      "field_id": 1,
      "disease_detected": false,
      "disease_type": null,
      "confidence": 0.98,
      "image_url": "/images/7d94e321.jpg",
      "timestamp": "2026-05-27T11:45:00Z"
    }
  ],
  "total": 2,
  "limit": 10,
  "offset": 0
}
```

---

## 3. GET `/status/:field_id`

특정 밭의 현재 상태와 최신 분석 결과를 반환합니다.

### 경로 파라미터

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `field_id` | integer | 밭 ID (1~5) |

### 예시 요청

```
GET /api/v1/status/1
```

### 응답 `200 OK`

```json
{
  "field_id": 1,
  "field_name": "1번 밭",
  "location": "구역 A - 북쪽",
  "status": "warning",
  "latest_analysis": {
    "analysis_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "disease_detected": true,
    "disease_type": "powdery_mildew",
    "confidence": 0.92,
    "timestamp": "2026-05-27T12:30:00Z"
  }
}
```

**status 값**

| 값 | 의미 |
|----|------|
| `healthy` | 정상 |
| `warning` | 질병 의심 (confidence 0.7 이상) |
| `critical` | 질병 확정 (confidence 0.9 이상) |

---

## 4. GET `/fields`

전체 밭 목록과 각 밭의 현재 상태를 반환합니다. 앱 초기 로딩 시 사용합니다.

### 응답 `200 OK`

```json
{
  "data": [
    { "field_id": 1, "field_name": "1번 밭", "location": "구역 A - 북쪽", "status": "warning" },
    { "field_id": 2, "field_name": "2번 밭", "location": "구역 B - 북동쪽", "status": "healthy" },
    { "field_id": 3, "field_name": "3번 밭", "location": "구역 C - 동쪽", "status": "healthy" },
    { "field_id": 4, "field_name": "4번 밭", "location": "구역 D - 남동쪽", "status": "critical" },
    { "field_id": 5, "field_name": "5번 밭", "location": "구역 E - 남쪽", "status": "healthy" }
  ]
}
```

---

## 5. PATCH `/notifications/:id/read`

알림을 읽음 상태로 표시합니다. Android 앱에서 팝업을 닫을 때 호출합니다.

### 경로 파라미터

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `id` | UUID | 알림 ID |

### 응답 `200 OK`

```json
{
  "notification_id": "abc12345-...",
  "read_at": "2026-05-27T12:35:00Z"
}
```

---

## Android 팀 연동 참고사항 (Retrofit)

```java
// Retrofit 인터페이스 예시
public interface GreenhouseApi {

    @POST("analyze")
    Call<AnalyzeResponse> analyze(@Body AnalyzeRequest request);

    @GET("history")
    Call<HistoryResponse> getHistory(
        @Query("field_id") Integer fieldId,
        @Query("limit") int limit,
        @Query("offset") int offset,
        @Query("disease_only") boolean diseaseOnly
    );

    @GET("status/{field_id}")
    Call<FieldStatus> getFieldStatus(@Path("field_id") int fieldId);

    @GET("fields")
    Call<FieldListResponse> getFields();

    @PATCH("notifications/{id}/read")
    Call<NotificationReadResponse> markAsRead(@Path("id") String notificationId);
}
```

---

## 변경 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|---------|
| 1.0 | 2026-05-27 | 최초 작성 |
