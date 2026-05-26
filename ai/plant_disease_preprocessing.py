import os, shutil, random, json, time, copy
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image
import torch, torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import efficientnet_b3, EfficientNet_B3_Weights
from tqdm.auto import tqdm
import yaml

SEED = 42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"PyTorch: {torch.__version__} | Device: {DEVICE}")

# ── 경로 설정 ──────────────────────────────────────────────
import kagglehub
DATASET_ROOT = Path(kagglehub.dataset_download("vipoooool/new-plant-diseases-dataset"))
BASE = DATASET_ROOT / "New Plant Diseases Dataset(Augmented)" / "New Plant Diseases Dataset(Augmented)"
TRAIN_DIR = BASE / "train"
VAL_DIR   = BASE / "valid"
print(f"Train: {TRAIN_DIR}")
print(f"Val:   {VAL_DIR}")

# ── 클래스 정의 (23개) ────────────────────────────────────
TARGET_CLASSES = {
    "Potato___Early_blight": {"crop": "Potato", "label": "Potato_Early_blight"},
    "Potato___Late_blight":  {"crop": "Potato", "label": "Potato_Late_blight"},
    "Potato___healthy":      {"crop": "Potato", "label": "Potato_healthy"},
    "Tomato___Bacterial_spot":                       {"crop": "Tomato", "label": "Tomato_Bacterial_spot"},
    "Tomato___Early_blight":                         {"crop": "Tomato", "label": "Tomato_Early_blight"},
    "Tomato___Late_blight":                          {"crop": "Tomato", "label": "Tomato_Late_blight"},
    "Tomato___Leaf_Mold":                            {"crop": "Tomato", "label": "Tomato_Leaf_Mold"},
    "Tomato___Septoria_leaf_spot":                   {"crop": "Tomato", "label": "Tomato_Septoria"},
    "Tomato___Spider_mites Two-spotted_spider_mite": {"crop": "Tomato", "label": "Tomato_Spider_mites"},
    "Tomato___Target_Spot":                          {"crop": "Tomato", "label": "Tomato_Target_Spot"},
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus":        {"crop": "Tomato", "label": "Tomato_YellowCurl"},
    "Tomato___Tomato_mosaic_virus":                  {"crop": "Tomato", "label": "Tomato_Mosaic"},
    "Tomato___healthy":                              {"crop": "Tomato", "label": "Tomato_healthy"},
    "Pepper,_bell___Bacterial_spot": {"crop": "Pepper", "label": "Pepper_Bacterial_spot"},
    "Pepper,_bell___healthy":        {"crop": "Pepper", "label": "Pepper_healthy"},
    "Apple___Apple_scab":       {"crop": "Apple", "label": "Apple_scab"},
    "Apple___Black_rot":        {"crop": "Apple", "label": "Apple_Black_rot"},
    "Apple___Cedar_apple_rust": {"crop": "Apple", "label": "Apple_Cedar_rust"},
    "Apple___healthy":          {"crop": "Apple", "label": "Apple_healthy"},
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {"crop": "Corn", "label": "Corn_Cercospora"},
    "Corn_(maize)___Common_rust_":                        {"crop": "Corn", "label": "Corn_Common_rust"},
    "Corn_(maize)___Northern_Leaf_Blight":                {"crop": "Corn", "label": "Corn_Northern_Blight"},
    "Corn_(maize)___healthy":                             {"crop": "Corn", "label": "Corn_healthy"},
}
CLASS_NAMES  = list(TARGET_CLASSES.keys())
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASS_NAMES)}
print(f"총 클래스: {len(CLASS_NAMES)}개")

# ── 클래스별 이미지 수 확인 ──────────────────────────────
class_counts = {}
for cls in CLASS_NAMES:
    p = TRAIN_DIR / cls
    if p.exists():
        class_counts[cls] = len(list(p.glob("*.jpg"))) + len(list(p.glob("*.JPG")))
print(f"총 선택 이미지: {sum(class_counts.values()):,}장")

# ── 클래스 분포 시각화 ────────────────────────────────────
crop_colors = {"Potato": "#8B6914", "Tomato": "#E74C3C", "Pepper": "#E67E22",
               "Apple": "#27AE60", "Corn": "#F1C40F"}
labels_en = [TARGET_CLASSES[c]["label"] for c in class_counts]
counts    = list(class_counts.values())
bar_colors = [crop_colors[TARGET_CLASSES[c]["crop"]] for c in class_counts]
fig, ax = plt.subplots(figsize=(14, 7))
bars = ax.barh(labels_en, counts, color=bar_colors, edgecolor="white", height=0.7)
for bar, cnt in zip(bars, counts):
    ax.text(bar.get_width() + 15, bar.get_y() + bar.get_height()/2,
            f"{cnt:,}", va="center", fontsize=8)
patches = [mpatches.Patch(color=v, label=k) for k, v in crop_colors.items()]
ax.legend(handles=patches, loc="lower right")
ax.set_xlabel("Image count")
ax.set_title("Class Distribution (Train)", fontsize=13, fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig("./class_distribution.png", dpi=150)
plt.close()
print("class_distribution.png 저장 완료")

# ── Transforms ────────────────────────────────────────────
IMG_SIZE = 224
MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]
train_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE + 20, IMG_SIZE + 20)),
    transforms.RandomCrop(IMG_SIZE),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomVerticalFlip(p=0.2),
    transforms.RandomRotation(degrees=15),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1),
    transforms.RandomGrayscale(p=0.05),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])
val_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])

# ── Dataset ───────────────────────────────────────────────
class PlantDiseaseDataset(Dataset):
    EXTENSIONS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

    def __init__(self, root_dir, class_names, class_to_idx, transform=None):
        self.root_dir     = Path(root_dir)
        self.class_names  = class_names
        self.class_to_idx = class_to_idx
        self.transform    = transform
        self.samples      = []
        self._load_samples()

    def _load_samples(self):
        for cls in self.class_names:
            cls_dir = self.root_dir / cls
            if not cls_dir.exists():
                continue
            for img_path in cls_dir.iterdir():
                if img_path.suffix in self.EXTENSIONS:
                    self.samples.append((img_path, self.class_to_idx[cls]))
        print(f"  로드 완료: {len(self.samples):,}개 샘플")

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        img = Image.open(img_path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label

    def class_distribution(self):
        dist = defaultdict(int)
        idx_to_cls = {v: k for k, v in self.class_to_idx.items()}
        for _, label in self.samples:
            dist[idx_to_cls[label]] += 1
        return dict(dist)

print("\n[Train Dataset]")
train_dataset = PlantDiseaseDataset(TRAIN_DIR, CLASS_NAMES, CLASS_TO_IDX, train_transform)
print("[Val Dataset]")
val_dataset   = PlantDiseaseDataset(VAL_DIR,   CLASS_NAMES, CLASS_TO_IDX, val_transform)
print(f"Train: {len(train_dataset):,}장 | Val: {len(val_dataset):,}장")

# ── DataLoader ────────────────────────────────────────────
BATCH_SIZE  = 32
NUM_WORKERS = 0   # MPS에서는 0이 안전
train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True,
                          num_workers=NUM_WORKERS, drop_last=True)
val_loader   = DataLoader(val_dataset,   batch_size=BATCH_SIZE, shuffle=False,
                          num_workers=NUM_WORKERS)
print(f"Train batches: {len(train_loader)} | Val batches: {len(val_loader)}")

# ── 클래스 가중치 (불균형 보정) ───────────────────────────
dist = train_dataset.class_distribution()
counts_arr   = np.array([dist.get(cls, 0) for cls in CLASS_NAMES], dtype=np.float32)
class_weights = 1.0 / counts_arr
loss_weights  = torch.tensor(class_weights / class_weights.sum() * len(CLASS_NAMES))
print(f"\n클래스 불균형 비율: {counts_arr.max() / counts_arr.min():.2f}x")

# ── 메타데이터 저장 ───────────────────────────────────────
metadata = {
    "num_classes":    len(CLASS_NAMES),
    "class_names":    CLASS_NAMES,
    "class_to_idx":   CLASS_TO_IDX,
    "img_size":       IMG_SIZE,
    "mean":           MEAN,
    "std":            STD,
    "train_size":     len(train_dataset),
    "val_size":       len(val_dataset),
    "loss_weights":   loss_weights.tolist(),
}
with open("./dataset_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
print("dataset_metadata.json 저장 완료")

# ── YOLO 데이터셋 구조 생성 ───────────────────────────────
YOLO_DIR = Path('./yolo_dataset')
for split_name in ['train', 'val']:
    (YOLO_DIR / split_name / 'images').mkdir(parents=True, exist_ok=True)
    (YOLO_DIR / split_name / 'labels').mkdir(parents=True, exist_ok=True)

split_map = {'train': TRAIN_DIR, 'val': VAL_DIR}
for dst_split, src_dir in split_map.items():
    count = 0
    for class_dir in src_dir.iterdir():
        if not class_dir.is_dir(): continue
        class_name = class_dir.name
        if class_name not in CLASS_TO_IDX: continue
        class_id = CLASS_TO_IDX[class_name]
        for img_path in list(class_dir.glob('*.jpg')) + list(class_dir.glob('*.JPG')):
            dst_img = YOLO_DIR / dst_split / 'images' / img_path.name
            dst_lbl = YOLO_DIR / dst_split / 'labels' / (img_path.stem + '.txt')
            if not dst_img.exists():
                shutil.copy(img_path, dst_img)
            dst_lbl.write_text(f'{class_id} 0.5 0.5 1.0 1.0\n')
            count += 1
    print(f'YOLO {dst_split}: {count}장 완료')

data_yaml = {
    'path': str(YOLO_DIR.resolve()),
    'train': 'train/images',
    'val':   'val/images',
    'nc':    len(CLASS_NAMES),
    'names': CLASS_NAMES,
}
with open(YOLO_DIR / 'data.yaml', 'w') as f:
    yaml.dump(data_yaml, f, allow_unicode=True)
print('data.yaml 생성 완료')

# ── YOLOv8 학습 ───────────────────────────────────────────
from ultralytics import YOLO as UltralyticsYOLO

yolo_model = UltralyticsYOLO('yolov8s.pt')
yolo_model.train(
    data=str(YOLO_DIR / 'data.yaml'),
    epochs=30, imgsz=224, batch=32,
    lr0=1e-4, weight_decay=0.01,
    optimizer='AdamW',
    project='./runs', name='smartfarm',
    exist_ok=True,
    device='mps',
    flipud=0.2, fliplr=0.5, degrees=15, hsv_s=0.3, hsv_v=0.3,
)
print('YOLOv8 학습 완료')

# ── EfficientNet-B3 모델 ──────────────────────────────────
def create_model(num_classes):
    model = efficientnet_b3(weights=EfficientNet_B3_Weights.DEFAULT)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features, num_classes),
    )
    return model

model = create_model(len(CLASS_NAMES)).to(DEVICE)
print(f"\nEfficientNet-B3 로드 완료 (device: {DEVICE})")

# ── Loss / Optimizer / Scheduler ─────────────────────────
criterion = nn.CrossEntropyLoss(weight=loss_weights.to(DEVICE))
optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
scheduler = lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)

# ── 학습 ─────────────────────────────────────────────────
def train_model(model, criterion, optimizer, scheduler, num_epochs=10):
    best_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0
    history  = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch+1}/{num_epochs} " + "-"*20)
        for phase in ["train", "val"]:
            if phase == "train": model.train(); loader = train_loader
            else:                model.eval();  loader = val_loader

            running_loss = 0.0; running_corrects = 0
            for inputs, labels in tqdm(loader, desc=phase):
                inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
                optimizer.zero_grad()
                with torch.set_grad_enabled(phase == "train"):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)
                    if phase == "train":
                        loss.backward(); optimizer.step()
                running_loss     += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            if phase == "train": scheduler.step()
            epoch_loss = running_loss / len(loader.dataset)
            epoch_acc  = running_corrects.double() / len(loader.dataset)
            print(f"  {phase} — Loss: {epoch_loss:.4f}  Acc: {epoch_acc:.4f}")
            history[f"{phase}_loss"].append(epoch_loss)
            history[f"{phase}_acc"].append(epoch_acc.item())

            if phase == "val" and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_wts = copy.deepcopy(model.state_dict())
                torch.save(model.state_dict(), "./best_plant_model.pth")
                print(f"  ★ best model 저장 (acc={best_acc:.4f})")

    print(f"\n학습 완료 | Best Val Acc: {best_acc:.4f}")
    model.load_state_dict(best_wts)
    return model, history

model, history = train_model(model, criterion, optimizer, scheduler, num_epochs=10)

# ── 학습 곡선 저장 ────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
epochs_range = range(len(history["train_acc"]))
axes[0].plot(epochs_range, history["train_acc"], label="Train")
axes[0].plot(epochs_range, history["val_acc"],   label="Val")
axes[0].set_title("Accuracy"); axes[0].legend()
axes[1].plot(epochs_range, history["train_loss"], label="Train")
axes[1].plot(epochs_range, history["val_loss"],   label="Val")
axes[1].set_title("Loss"); axes[1].legend()
plt.tight_layout()
plt.savefig("./training_history.png", dpi=150)
plt.close()
print("training_history.png 저장 완료")
print("모델 저장 위치: ./best_plant_model.pth")
