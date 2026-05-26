# Backend — Dr. Plant API

## 실행 전 준비

학습된 모델 파일이 프로젝트 루트에 있어야 합니다.

```
greenhouse/
├── best_plant_model.pth     # EfficientNet-B3 학습 가중치
├── dataset_metadata.json    # 클래스 정보
└── app/backend/
    ├── main.py
    ├── model.py
    └── requirements.txt
```

`best_plant_model.pth`와 `dataset_metadata.json`은 `ai/plant_disease_preprocessing.py`를 먼저 실행해야 생성됩니다.

## 설치 및 실행

```bash
cd app/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API

### POST /diagnose

| 항목 | 내용 |
|---|---|
| Content-Type | multipart/form-data |
| 파라미터 | `image` (이미지 파일) |

**응답 예시**
```json
{
  "plantName": "토마토",
  "diseaseName": "초기 마름병",
  "symptoms": "아래 잎부터 갈색 동심원 무늬 반점이 생기며...",
  "feedback": ["아래쪽 감염 잎을 제거하세요.", "..."]
  "confidence": 94.3
}
```

### GET /

서버 상태 확인
```json
{"status": "ok"}
```

## Flutter 연결

`lib/services/ai_service.dart`의 서버 주소를 본인 IP로 변경:
```dart
static const String _serverUrl = 'http://본인IP:8000';
```

본인 IP 확인 방법:
```bash
# macOS
ifconfig | grep "inet " | grep -v 127

# Windows
ipconfig
```
