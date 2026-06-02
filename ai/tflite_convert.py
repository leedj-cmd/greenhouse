# ── TFLite 변환 스크립트 ────────────────────────────────────────────────────
#
# 실행 순서:
#   1. python plant_disease_preprocessing.py   # 모델 학습 (최초 1회)
#   2. python tflite_convert.py                # TFLite 변환
#
# 출력 파일:
#   - best_plant_model.onnx    (중간 변환본)
#   - best_plant_model.tflite  (앱에 넣을 최종 파일)
#   - yolo_smartfarm.tflite    (YOLO TFLite — ultralytics 내장 변환)
#
# 앱 연동:
#   변환된 .tflite 파일을 Android 앱의 assets/ 폴더에 복사하세요.
#   (C:\mobileprogram\SmartFarm\app\src\main\assets\)
#
# 설치 필요 패키지:
#   pip install torch torchvision onnx onnxruntime
#   pip install ai-edge-torch          # Google 공식 PyTorch→TFLite 변환기
#   pip install ultralytics            # YOLO TFLite 변환 내장

import os
import torch
import torch.nn as nn
from torchvision.models import efficientnet_b3, EfficientNet_B3_Weights
from pathlib import Path

# plant_disease_preprocessing.py 와 동일한 클래스 수
NUM_CLASSES = 23
IMG_SIZE    = 224
MODEL_PATH  = "./best_plant_model.pth"
ONNX_PATH   = "./best_plant_model.onnx"
TFLITE_PATH = "./best_plant_model.tflite"
YOLO_WEIGHTS = "./runs/smartfarm/weights/best.pt"


# ── Step 1: EfficientNet-B3 로드 ─────────────────────────────────────────────
def load_efficientnet(model_path: str, num_classes: int):
    model = efficientnet_b3(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, num_classes),
    )
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    return model


# ── Step 2: PyTorch → ONNX 변환 ──────────────────────────────────────────────
def export_to_onnx(model, onnx_path: str):
    dummy_input = torch.randn(1, 3, IMG_SIZE, IMG_SIZE)
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        opset_version=17,
    )
    print(f"✅ ONNX 저장 완료: {onnx_path}")


# ── Step 3: ONNX → TFLite 변환 ───────────────────────────────────────────────
def export_onnx_to_tflite(onnx_path: str, tflite_path: str):
    try:
        # ai-edge-torch 방식 (권장)
        import ai_edge_torch
        import torch

        model = load_efficientnet(MODEL_PATH, NUM_CLASSES)
        sample_input = (torch.randn(1, 3, IMG_SIZE, IMG_SIZE),)
        edge_model = ai_edge_torch.convert(model.eval(), sample_input)
        edge_model.export(tflite_path)
        print(f"✅ TFLite 저장 완료 (ai-edge-torch): {tflite_path}")

    except ImportError:
        # ai-edge-torch 없으면 onnx-tf 방식으로 fallback
        print("ai-edge-torch 없음 → onnx-tf 방식 시도")
        try:
            import onnx
            from onnx_tf.backend import prepare
            import tensorflow as tf

            onnx_model = onnx.load(onnx_path)
            tf_rep = prepare(onnx_model)
            tf_model_path = tflite_path.replace(".tflite", "_tf")
            tf_rep.export_graph(tf_model_path)

            converter = tf.lite.TFLiteConverter.from_saved_model(tf_model_path)
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            tflite_model = converter.convert()

            with open(tflite_path, "wb") as f:
                f.write(tflite_model)
            print(f"✅ TFLite 저장 완료 (onnx-tf): {tflite_path}")

        except ImportError:
            print("❌ ai-edge-torch 또는 onnx-tf 설치 필요:")
            print("   pip install ai-edge-torch")
            print("   또는: pip install onnx-tf tensorflow")


# ── Step 4: YOLO TFLite 변환 ─────────────────────────────────────────────────
def export_yolo_to_tflite(yolo_weights: str):
    if not Path(yolo_weights).exists():
        print(f"⚠️  YOLO 가중치 없음: {yolo_weights} (학습 후 실행하세요)")
        return
    try:
        from ultralytics import YOLO
        model = YOLO(yolo_weights)
        model.export(format="tflite", imgsz=IMG_SIZE, int8=False)
        print("✅ YOLO TFLite 변환 완료 (runs/smartfarm/weights/best_float32.tflite)")
    except Exception as e:
        print(f"❌ YOLO TFLite 변환 실패: {e}")


# ── 실행 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("TFLite 변환 시작")
    print("=" * 50)

    # EfficientNet 변환
    if not Path(MODEL_PATH).exists():
        print(f"❌ 모델 파일 없음: {MODEL_PATH}")
        print("   먼저 plant_disease_preprocessing.py 를 실행하세요.")
    else:
        print("\n[1/3] EfficientNet 로드 중...")
        model = load_efficientnet(MODEL_PATH, NUM_CLASSES)

        print("[2/3] ONNX 변환 중...")
        export_to_onnx(model, ONNX_PATH)

        print("[3/3] TFLite 변환 중...")
        export_onnx_to_tflite(ONNX_PATH, TFLITE_PATH)

    # YOLO 변환
    print("\n[YOLO] TFLite 변환 중...")
    export_yolo_to_tflite(YOLO_WEIGHTS)

    print("\n변환 완료!")
    print(f"앱 assets 폴더에 복사하세요:")
    print(f"  {TFLITE_PATH} → SmartFarm/app/src/main/assets/plant_model.tflite")
    print(f"  runs/smartfarm/weights/best_float32.tflite → SmartFarm/app/src/main/assets/yolo_model.tflite")
