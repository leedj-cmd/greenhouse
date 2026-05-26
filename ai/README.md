# AI 모듈

비닐하우스 식물 잎 질병 탐지를 위한 AI 파이프라인입니다.

## 파일 구성

### `plant_disease_preprocessing.py` — 데이터 전처리 + 모델 학습

모델 학습 전 최초 1회 실행합니다.

**수행 작업**
- Kaggle 데이터셋 다운로드 (`vipoooool/new-plant-diseases-dataset`)
- 23개 클래스 정의 (Potato / Tomato / Pepper / Apple / Corn)
- YOLO 형식 데이터셋 구조 생성 (`yolo_dataset/train|val/images+labels`)
- YOLOv8s 학습 (30 epochs, AdamW, MPS)
- EfficientNet-B3 학습 (10 epochs, AdamW + StepLR, 클래스 가중치 보정)

**출력물**
```
runs/smartfarm/weights/best.pt   # YOLOv8 학습 가중치
best_plant_model.pth             # EfficientNet-B3 학습 가중치
dataset_metadata.json            # 클래스 정보 및 데이터셋 메타데이터
class_distribution.png           # 클래스별 이미지 수 분포 차트
training_history.png             # 학습 곡선 (Loss / Accuracy)
```

---

### `smartfarm_yolo.py` — 슬라이딩 윈도우 추론

`plant_disease_preprocessing.py` 실행 후 사용합니다.

**수행 작업**
- 대형 이미지를 타일로 분할 (`slice_image`)
- 각 타일에 YOLOv8 추론 적용 (`infer_on_tiles`)
- 타일 간 중복 박스 제거 NMS (`apply_nms`)
- 원본 이미지 위에 탐지 결과 시각화 (`draw_results`)

**사용법**
```python
from smartfarm_yolo import run_smartfarm_detection

dets = run_smartfarm_detection('./greenhouse.jpg')
# smartfarm_result.png 로 결과 저장
```

---

## 실행 순서

```
1. python plant_disease_preprocessing.py   # 학습 (최초 1회)
2. python smartfarm_yolo.py               # 추론 (이미지 경로 지정 후)
```

## 환경

- Python 3.14 / PyTorch (Apple Silicon MPS)
- YOLOv8s (`ultralytics`), EfficientNet-B3 (`torchvision`)
- Kaggle 인증 필요 (`~/.kaggle/kaggle.json`)
