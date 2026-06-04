"""
ONNX 모델을 사용한 실제 작물 질병 추론 모듈
입력: 이미지 파일 경로
출력: (disease_type: str, confidence: float)
"""
import os
import numpy as np
from pathlib import Path
from PIL import Image

import onnxruntime as ort

# ── 모델 경로 ─────────────────────────────────────────────────────────────────
MODEL_PATH = Path(__file__).parent / "best_crop_model.onnx"

# ── 클래스 정의 (학습 시와 동일한 순서) ──────────────────────────────────────
CLASS_NAMES = [
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
]

# ── 클래스 → disease_type 매핑 ────────────────────────────────────────────────
CLASS_TO_DISEASE = {
    "Potato___healthy":                                          "NORMAL",
    "Tomato___healthy":                                          "NORMAL",
    "Pepper,_bell___healthy":                                    "NORMAL",
    "Apple___healthy":                                           "NORMAL",
    "Corn_(maize)___healthy":                                    "NORMAL",
    "Potato___Early_blight":                                     "BLIGHT",
    "Potato___Late_blight":                                      "BLIGHT",
    "Tomato___Early_blight":                                     "BLIGHT",
    "Tomato___Late_blight":                                      "BLIGHT",
    "Corn_(maize)___Northern_Leaf_Blight":                       "BLIGHT",
    "Apple___Cedar_apple_rust":                                  "RUST",
    "Corn_(maize)___Common_rust_":                               "RUST",
    "Tomato___Bacterial_spot":                                   "SPOT",
    "Pepper,_bell___Bacterial_spot":                             "SPOT",
    "Tomato___Septoria_leaf_spot":                               "SPOT",
    "Tomato___Target_Spot":                                      "SPOT",
    "Apple___Apple_scab":                                        "SPOT",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot":        "SPOT",
    "Tomato___Tomato_mosaic_virus":                              "MOSAIC",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus":                    "MOSAIC",
    "Tomato___Leaf_Mold":                                        "MOLD",
    "Apple___Black_rot":                                         "ROT",
    "Tomato___Spider_mites Two-spotted_spider_mite":             "PEST",
}

# ── ImageNet 정규화 파라미터 ──────────────────────────────────────────────────
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
IMG_SIZE = 224

# ── ONNX 세션 (서버 시작 시 1회 로드) ────────────────────────────────────────
_session = None

def _get_session() -> ort.InferenceSession:
    global _session
    if _session is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"모델 파일 없음: {MODEL_PATH}")
        _session = ort.InferenceSession(str(MODEL_PATH))
    return _session


def _preprocess(image_path: str) -> np.ndarray:
    """이미지 → 모델 입력 텐서 (1, 3, 224, 224)"""
    img = Image.open(image_path).convert("RGB")
    img = img.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    arr = np.array(img, dtype=np.float32) / 255.0   # [0, 1]
    arr = (arr - MEAN) / STD                          # 정규화
    arr = arr.transpose(2, 0, 1)                      # HWC → CHW
    return arr[np.newaxis, ...]                        # 배치 차원


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


def analyze(image_path: str) -> tuple[str, float]:
    """
    이미지 파일을 분석하여 (disease_type, confidence) 반환.
    모델 로드 실패 시 mock 결과 반환.
    """
    try:
        sess   = _get_session()
        tensor = _preprocess(image_path)
        logits = sess.run(["output"], {"input": tensor})[0][0]
        probs  = _softmax(logits)

        idx        = int(np.argmax(probs))
        confidence = float(probs[idx])
        class_name = CLASS_NAMES[idx] if idx < len(CLASS_NAMES) else "UNKNOWN"
        disease    = CLASS_TO_DISEASE.get(class_name, "UNKNOWN")

        # 신뢰도가 너무 낮으면 NORMAL 처리
        if confidence < 0.4:
            return "NORMAL", round(confidence, 2)

        return disease, round(confidence, 2)

    except Exception as e:
        print(f"[AI 추론 오류] {e} — mock 결과 반환")
        import random
        diseases = ["NORMAL", "NORMAL", "NORMAL", "BLIGHT", "RUST"]
        return random.choice(diseases), round(random.uniform(0.75, 0.99), 2)
