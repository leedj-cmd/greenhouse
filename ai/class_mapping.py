# ── 23개 AI 클래스 → 서버 disease_type 매핑 ─────────────────────────────────
#
# 서버 DB의 disease_type 필드에 저장되는 값입니다.
# 앱의 isDiseased() 는 disease_type != "NORMAL" 이면 질병으로 판단합니다.
#
# 서버 api.py의 _mock_analyze() 를 실제 모델로 교체할 때 이 매핑을 사용하세요.

CLASS_TO_DISEASE_TYPE = {
    # ── 정상 (NORMAL) ──────────────────────────────────────
    "Potato___healthy":            "NORMAL",
    "Tomato___healthy":            "NORMAL",
    "Pepper,_bell___healthy":      "NORMAL",
    "Apple___healthy":             "NORMAL",
    "Corn_(maize)___healthy":      "NORMAL",

    # ── 역병 / 마름병 (BLIGHT) ──────────────────────────────
    "Potato___Early_blight":                    "BLIGHT",
    "Potato___Late_blight":                     "BLIGHT",
    "Tomato___Early_blight":                    "BLIGHT",
    "Tomato___Late_blight":                     "BLIGHT",
    "Corn_(maize)___Northern_Leaf_Blight":      "BLIGHT",

    # ── 녹병 (RUST) ────────────────────────────────────────
    "Apple___Cedar_apple_rust":        "RUST",
    "Corn_(maize)___Common_rust_":     "RUST",

    # ── 반점 / 세균성 (SPOT) ───────────────────────────────
    "Tomato___Bacterial_spot":                              "SPOT",
    "Pepper,_bell___Bacterial_spot":                        "SPOT",
    "Tomato___Septoria_leaf_spot":                          "SPOT",
    "Tomato___Target_Spot":                                 "SPOT",
    "Apple___Apple_scab":                                   "SPOT",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot":   "SPOT",

    # ── 바이러스 / 모자이크 (MOSAIC) ──────────────────────
    "Tomato___Tomato_mosaic_virus":              "MOSAIC",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus":    "MOSAIC",

    # ── 곰팡이 (MOLD) ──────────────────────────────────────
    "Tomato___Leaf_Mold":   "MOLD",

    # ── 썩음병 (ROT) ───────────────────────────────────────
    "Apple___Black_rot":    "ROT",

    # ── 해충 (PEST) ────────────────────────────────────────
    "Tomato___Spider_mites Two-spotted_spider_mite": "PEST",
}

# 신뢰도 임계값 — 이 값 미만이면 NORMAL로 처리
CONFIDENCE_THRESHOLD = 0.5


def map_to_disease_type(class_name: str, confidence: float) -> str:
    """
    AI 모델 출력 클래스명 + 신뢰도를 서버 disease_type으로 변환합니다.

    Args:
        class_name:  plant_disease_preprocessing.py의 CLASS_NAMES 중 하나
        confidence:  0.0 ~ 1.0 사이의 모델 신뢰도

    Returns:
        서버 DB에 저장할 disease_type 문자열
    """
    if confidence < CONFIDENCE_THRESHOLD:
        return "NORMAL"
    return CLASS_TO_DISEASE_TYPE.get(class_name, "UNKNOWN")


# ── 서버 연동 예시 (api.py의 _mock_analyze 교체용) ──────────────────────────
#
# from ai.class_mapping import map_to_disease_type
#
# def real_analyze(image_path: str) -> tuple[str, float]:
#     # EfficientNet 추론
#     predicted_class, confidence = efficientnet_infer(image_path)
#     disease_type = map_to_disease_type(predicted_class, confidence)
#     return disease_type, round(confidence, 2)
