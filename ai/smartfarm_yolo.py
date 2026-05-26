import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
from ultralytics import YOLO

RESULT_IMG = './smartfarm_result.png'

# ── 슬라이딩 윈도우 추론 ────────────────────────────
def slice_image(image, tile_size=640, overlap=0.2):
    h, w = image.shape[:2]
    stride = int(tile_size * (1 - overlap))
    tiles = []
    for y in range(0, h, stride):
        for x in range(0, w, stride):
            x2 = min(x + tile_size, w)
            y2 = min(y + tile_size, h)
            x1 = max(0, x2 - tile_size)
            y1 = max(0, y2 - tile_size)
            tiles.append((image[y1:y2, x1:x2], x1, y1))
    return tiles


@dataclass
class Det:
    x1: float; y1: float; x2: float; y2: float
    conf: float; cls_id: int; cls_name: str


def infer_on_tiles(model, image, tile_size=640, overlap=0.2, conf=0.25):
    dets = []
    for tile, ox, oy in slice_image(image, tile_size, overlap):
        for r in model(tile, conf=conf, verbose=False):
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                dets.append(Det(
                    x1=x1+ox, y1=y1+oy, x2=x2+ox, y2=y2+oy,
                    conf=float(box.conf[0]),
                    cls_id=int(box.cls[0]),
                    cls_name=model.names[int(box.cls[0])],
                ))
    return dets


def apply_nms(dets, iou_threshold=0.5):
    if not dets:
        return []
    boxes = np.array([[d.x1, d.y1, d.x2, d.y2] for d in dets], dtype=np.float32)
    scores = np.array([d.conf for d in dets], dtype=np.float32)
    cls_ids = np.array([d.cls_id for d in dets])
    keep = []
    for cid in np.unique(cls_ids):
        mask = cls_ids == cid
        idx = np.where(mask)[0]
        picked = cv2.dnn.NMSBoxes(
            boxes[mask].tolist(), scores[mask].tolist(),
            score_threshold=0.0, nms_threshold=iou_threshold,
        )
        if len(picked) > 0:
            keep.extend(idx[picked.flatten()])
    return [dets[i] for i in keep]


def draw_results(image, dets):
    out = image.copy()
    colors = {}
    for d in dets:
        if d.cls_id not in colors:
            np.random.seed(d.cls_id)
            colors[d.cls_id] = tuple(np.random.randint(50, 230, 3).tolist())
        c = colors[d.cls_id]
        cv2.rectangle(out, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), c, 2)
        cv2.putText(out, f'{d.cls_name.split("___")[-1][:15]} {d.conf:.2f}',
                    (int(d.x1), int(d.y1)-6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 2)
    return out


def run_smartfarm_detection(image_path,
                            model_path='./runs/smartfarm/weights/best.pt',
                            tile_size=640, overlap=0.2, conf=0.25, iou=0.5):
    mdl = YOLO(model_path)
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w = image.shape[:2]
    tiles = slice_image(image, tile_size, overlap)
    print(f'원본: {w}x{h} | 타일: {len(tiles)}')

    raw_dets = infer_on_tiles(mdl, image, tile_size, overlap, conf)
    final_dets = apply_nms(raw_dets, iou)
    print(f'Raw: {len(raw_dets)} → NMS 후: {len(final_dets)}')

    for cls, cnt in Counter(d.cls_name for d in final_dets).most_common():
        print(f'  {cls}: {cnt}건')

    result_img = draw_results(image_rgb, final_dets)
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    axes[0].imshow(image_rgb); axes[0].set_title('원본'); axes[0].axis('off')
    axes[1].imshow(result_img); axes[1].set_title(f'탐지 결과 ({len(final_dets)}건)'); axes[1].axis('off')
    plt.tight_layout()
    plt.savefig(RESULT_IMG, dpi=150)
    plt.show()
    return final_dets


# 사용 예시 (학습은 plant_disease_preprocessing.py 먼저 실행)
# dets = run_smartfarm_detection('./greenhouse.jpg')
