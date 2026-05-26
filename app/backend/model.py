import io
import json
import torch
import torch.nn as nn
from pathlib import Path
from PIL import Image
from torchvision import transforms
from torchvision.models import efficientnet_b3, EfficientNet_B3_Weights

# ── 경로 설정 ─────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent.parent  # 프로젝트 루트
MODEL_PATH  = BASE_DIR / "best_plant_model.pth"
META_PATH   = BASE_DIR / "dataset_metadata.json"

# ── 메타데이터 로드 ───────────────────────────────────────
with open(META_PATH, "r") as f:
    meta = json.load(f)

CLASS_NAMES  = meta["class_names"]
CLASS_TO_IDX = meta["class_to_idx"]
IDX_TO_CLASS = {v: k for k, v in CLASS_TO_IDX.items()}
IMG_SIZE     = meta["img_size"]
MEAN         = meta["mean"]
STD          = meta["std"]

# ── 질병 정보 매핑 ────────────────────────────────────────
DISEASE_INFO = {
    "Potato___Early_blight":   {"plant": "감자", "disease": "초기 마름병",   "symptoms": "잎에 갈색 동심원 반점이 생기며 점차 커집니다. 아래 잎부터 시작해 위로 퍼집니다.",         "feedback": ["감염된 잎을 즉시 제거하고 소각하세요.", "만코제브 또는 클로로탈로닐 계열 살균제를 7~10일 간격으로 살포하세요.", "물을 줄 때 잎에 닿지 않도록 뿌리 쪽에 주세요.", "통풍이 잘 되도록 과밀 재배를 피하세요."]},
    "Potato___Late_blight":    {"plant": "감자", "disease": "후기 마름병",   "symptoms": "잎 가장자리에 물에 젖은 듯한 암녹색 반점이 나타나고, 흰색 곰팡이가 핍니다.",         "feedback": ["감염 즉시 해당 식물을 격리하세요.", "메탈락실 계열 살균제를 긴급 살포하세요.", "감염된 식물 잔재는 모두 제거해 토양 내 전염을 막으세요.", "습도를 낮추고 환기를 강화하세요."]},
    "Potato___healthy":        {"plant": "감자", "disease": "건강함",         "symptoms": "잎이 균일한 녹색이며 반점, 변색, 시듦 등의 이상 증상이 없습니다.",             "feedback": ["현재 상태를 유지하세요.", "주 1~2회 정기적으로 잎 상태를 점검하세요.", "과습하지 않도록 배수 관리를 해주세요.", "비료는 과하지 않게 균형 있게 주세요."]},
    "Tomato___Bacterial_spot": {"plant": "토마토", "disease": "세균성 반점병", "symptoms": "작고 수침상인 갈색 반점이 잎, 줄기, 열매에 발생하며 반점 주위가 노랗게 변합니다.",    "feedback": ["감염된 잎과 열매를 즉시 제거하세요.", "구리 계열 살균제(동수화제)를 5~7일 간격으로 살포하세요.", "작업 도구를 70% 알코올로 소독하세요.", "위에서 물을 주는 방식을 피하고 지면 관수로 바꾸세요."]},
    "Tomato___Early_blight":   {"plant": "토마토", "disease": "초기 마름병",  "symptoms": "아래 잎부터 갈색 동심원 무늬 반점이 생기며 잎이 노랗게 변해 떨어집니다.",          "feedback": ["아래쪽 감염 잎을 제거하세요.", "만코제브 살균제를 7일 간격으로 살포하세요.", "멀칭을 해서 토양에서의 포자 비산을 막으세요.", "식물 간격을 넓혀 통풍을 개선하세요."]},
    "Tomato___Late_blight":    {"plant": "토마토", "disease": "후기 마름병",  "symptoms": "잎에 암녹색 기름진 반점이 생기고 빠르게 갈색으로 변하며 줄기도 썩습니다.",          "feedback": ["즉시 감염 식물을 격리하세요.", "메탈락실+만코제브 혼합 살균제를 살포하세요.", "감염 잔재는 비닐백에 밀봉해 폐기하세요.", "이후 저항성 품종으로 교체를 고려하세요."]},
    "Tomato___Leaf_Mold":      {"plant": "토마토", "disease": "잎 곰팡이병", "symptoms": "잎 앞면에 노란 반점, 뒷면에 회녹색 곰팡이가 핍니다. 주로 시설 재배에서 발생합니다.",   "feedback": ["온실 환기를 즉시 강화하세요.", "클로로탈로닐 살균제를 살포하세요.", "습도를 65% 이하로 유지하세요.", "감염된 잎을 제거 후 소각하세요."]},
    "Tomato___Septoria_leaf_spot": {"plant": "토마토", "disease": "셉토리아 잎반점", "symptoms": "작고 둥근 회백색 반점 중앙에 검은 점(포자낭)이 생기며 아래 잎부터 퍼집니다.",  "feedback": ["감염 잎을 제거하세요.", "만코제브 또는 구리 살균제를 7~10일 간격으로 살포하세요.", "잎에 물이 닿지 않게 관수 방법을 바꾸세요.", "수확 후 식물 잔재를 완전히 제거하세요."]},
    "Tomato___Spider_mites Two-spotted_spider_mite": {"plant": "토마토", "disease": "점박이응애", "symptoms": "잎 뒷면에 작은 흰 점이 생기고 잎이 청동색으로 변하며, 심하면 거미줄이 보입니다.", "feedback": ["살비제(아바멕틴 계열)를 잎 뒷면 위주로 살포하세요.", "물로 잎을 세게 씻어 응애를 물리적으로 제거하세요.", "고온 건조 환경을 피하고 습도를 올리세요.", "천적(칠레이리응애)을 활용한 생물적 방제를 고려하세요."]},
    "Tomato___Target_Spot":    {"plant": "토마토", "disease": "타겟 반점병",  "symptoms": "잎에 동심원 고리 모양의 갈색 반점이 생기고 잎이 황화되며 조기 낙엽됩니다.",         "feedback": ["감염 잎을 제거하세요.", "보스칼리드 또는 아족시스트로빈 살균제를 살포하세요.", "식물 하부 잎을 쳐내 통기를 개선하세요.", "토양 멀칭으로 포자 비산을 억제하세요."]},
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {"plant": "토마토", "disease": "황화잎말림바이러스", "symptoms": "잎이 위쪽으로 말리고 노랗게 변하며, 성장이 멈추고 열매 착과가 줄어듭니다.",  "feedback": ["감염 식물을 즉시 제거하세요 (바이러스는 치료 불가).", "매개 해충인 담배가루이를 방제하세요 (이미다클로프리드 살포).", "방충망으로 시설을 밀폐하세요.", "저항성 품종을 사용하세요."]},
    "Tomato___Tomato_mosaic_virus": {"plant": "토마토", "disease": "모자이크바이러스", "symptoms": "잎에 녹색과 황색이 섞인 모자이크 무늬가 생기고, 잎이 주름지거나 뒤틀립니다.",    "feedback": ["감염 식물을 즉시 제거하세요 (치료 불가).", "작업 전후 손과 도구를 철저히 소독하세요.", "진딧물 등 매개 해충을 방제하세요.", "저항성 품종을 사용하세요."]},
    "Tomato___healthy":        {"plant": "토마토", "disease": "건강함",        "symptoms": "잎이 진한 녹색이며 광택이 있고 병반, 변색, 시듦이 없습니다.",                    "feedback": ["현재 상태를 유지하세요.", "주 1~2회 잎 뒷면까지 꼼꼼히 점검하세요.", "과습 방지를 위해 배수 관리를 철저히 하세요.", "균형 잡힌 영양 공급을 지속하세요."]},
    "Pepper,_bell___Bacterial_spot": {"plant": "고추", "disease": "세균성 반점병", "symptoms": "잎과 열매에 작고 수침상인 갈색 반점이 생기며 반점 주위가 노랗게 변합니다.",       "feedback": ["감염 잎과 열매를 즉시 제거하세요.", "구리 계열 살균제를 5~7일 간격으로 살포하세요.", "비가 온 후 즉시 살균제를 추가 살포하세요.", "작업 도구를 소독하고 이동 시 전파에 주의하세요."]},
    "Pepper,_bell___healthy":  {"plant": "고추", "disease": "건강함",          "symptoms": "잎이 광택 있는 녹색이며 반점, 기형, 변색이 없습니다.",                          "feedback": ["현재 상태를 유지하세요.", "고온다습 환경은 병 발생을 높이니 환기를 유지하세요.", "정기적으로 잎 상태를 점검하세요.", "예방 차원의 살균제를 2주 간격으로 살포하세요."]},
    "Apple___Apple_scab":      {"plant": "사과", "disease": "사과 딱지병",    "symptoms": "잎과 열매에 올리브색 또는 갈색 벨벳 질감의 반점이 생기고 열매가 기형이 됩니다.",  "feedback": ["감염 잎과 열매를 수거해 소각하세요.", "캡탄 또는 마이클로부타닐 살균제를 개화 전후 살포하세요.", "나무 아래 낙엽을 제거해 2차 감염원을 없애세요.", "가지치기로 수관 내 통풍을 개선하세요."]},
    "Apple___Black_rot":       {"plant": "사과", "disease": "검은썩음병",     "symptoms": "잎에 자주색 반점이 생기고, 열매는 썩으며 검게 주름집니다.",                      "feedback": ["감염된 열매와 가지를 즉시 제거하세요.", "캡탄 살균제를 2주 간격으로 살포하세요.", "상처 부위는 보호제를 바르세요.", "죽은 나무껍질(궤양 부위)을 긁어내 제거하세요."]},
    "Apple___Cedar_apple_rust": {"plant": "사과", "disease": "붉은별무늬병",  "symptoms": "잎 앞면에 밝은 주황색 반점이 생기고, 뒷면에는 관 모양의 포자각이 형성됩니다.",    "feedback": ["마이클로부타닐 살균제를 개화기부터 살포하세요.", "근처의 향나무류(중간 기주)를 제거하세요.", "감염 잎을 수거해 소각하세요.", "저항성 품종으로의 교체를 검토하세요."]},
    "Apple___healthy":         {"plant": "사과", "disease": "건강함",         "symptoms": "잎이 선명한 녹색이고 반점, 변색, 기형이 없습니다.",                            "feedback": ["현재 상태를 유지하세요.", "예방적 살균제를 정기 살포하세요.", "낙엽과 열매 잔재를 수시로 제거하세요.", "가지치기로 통풍을 유지하세요."]},
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {"plant": "옥수수", "disease": "회색잎반점병", "symptoms": "잎맥 사이에 회색~갈색의 긴 직사각형 병반이 생기며 심하면 잎 전체가 고사합니다.", "feedback": ["아족시스트로빈 또는 프로피코나졸 살균제를 살포하세요.", "수확 후 식물 잔재를 완전히 제거하세요.", "저항성 품종을 사용하세요.", "연작을 피하고 윤작을 실시하세요."]},
    "Corn_(maize)___Common_rust_": {"plant": "옥수수", "disease": "일반 녹병",  "symptoms": "잎 양면에 계피색 작은 포자 덩어리가 산재하며 심하면 잎이 말라 죽습니다.",        "feedback": ["마이클로부타닐 또는 트리플록시스트로빈 살균제를 살포하세요.", "발병 초기에 방제해야 효과적입니다.", "저항성 품종을 선택하세요.", "밀식 재배를 피하세요."]},
    "Corn_(maize)___Northern_Leaf_Blight": {"plant": "옥수수", "disease": "북부잎마름병", "symptoms": "잎에 회녹색~갈색의 긴 방추형 병반이 생기며 잎 전체로 퍼져 조기 고사합니다.",  "feedback": ["아족시스트로빈 살균제를 초기에 살포하세요.", "수확 후 잔재물을 갈아엎어 분해시키세요.", "저항성 품종을 사용하세요.", "질소 비료를 적정량으로 조절하세요."]},
    "Corn_(maize)___healthy":  {"plant": "옥수수", "disease": "건강함",        "symptoms": "잎이 선명한 녹색이고 반점, 병반, 시듦이 없습니다.",                            "feedback": ["현재 상태를 유지하세요.", "적정 수분과 비료를 유지하세요.", "주기적으로 병해충 발생 여부를 점검하세요.", "예방적 살균제를 생육 중기에 한 번 살포하세요."]},
}

# ── Transform ─────────────────────────────────────────────
val_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])

# ── 모델 로드 ─────────────────────────────────────────────
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

def _load_model():
    model = efficientnet_b3(weights=EfficientNet_B3_Weights.DEFAULT)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, len(CLASS_NAMES)),
    )
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    model.to(DEVICE)
    model.eval()
    return model

_model = _load_model()

# ── 추론 ──────────────────────────────────────────────────
def predict(image_bytes: bytes) -> dict:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = val_transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        outputs = _model(tensor)
        probs   = torch.softmax(outputs, dim=1)
        conf, pred_idx = torch.max(probs, 1)

    class_name = IDX_TO_CLASS[pred_idx.item()]
    info = DISEASE_INFO.get(class_name, {
        "plant":    class_name,
        "disease":  "알 수 없음",
        "symptoms": "정보 없음",
        "feedback": ["전문가에게 문의하세요."]
    })

    return {
        "plantName":   info["plant"],
        "diseaseName": info["disease"],
        "symptoms":    info["symptoms"],
        "feedback":    info["feedback"],
        "confidence":  round(conf.item() * 100, 1),
    }
