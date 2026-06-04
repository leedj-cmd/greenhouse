"""
테스트용 이미지 업로드 클라이언트.

에뮬레이터/실제 카메라 없이 .jpg 파일로 백엔드 동작을 검증합니다.

사용 예:
    # 단일 업로드 (서버 ONNX 추론)
    ~/venv/bin/python test_upload.py --image test.jpg --field a1

    # 앱 TFLite 결과 시뮬레이션 (서버 추론 건너뜀)
    ~/venv/bin/python test_upload.py --image test.jpg --field a1 \\
        --disease BLIGHT --confidence 0.92

    # 폴더 일괄 업로드 (구역마다 순환)
    ~/venv/bin/python test_upload.py --batch ./test_images --field a1

    # 호스트 변경
    ~/venv/bin/python test_upload.py --image test.jpg --field a1 \\
        --host http://192.168.0.10:8000
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid as _uuid
from pathlib import Path


# ── 최소 multipart 인코더 (외부 의존성 없이) ─────────────────────────────────
def encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = f"----test-upload-{_uuid.uuid4().hex}"
    lines = []

    for name, value in fields.items():
        if value is None:
            continue
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        lines.append(b"")
        lines.append(str(value).encode())

    for name, (filename, content, mime) in files.items():
        lines.append(f"--{boundary}".encode())
        lines.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode()
        )
        lines.append(f"Content-Type: {mime}".encode())
        lines.append(b"")
        lines.append(content)

    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    body = b"\r\n".join(lines)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def http_request(method: str, url: str, body: bytes = None, content_type: str = None) -> dict:
    req = urllib.request.Request(url, data=body, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[HTTP {e.code}] {body}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"[연결 실패] {e.reason} — 서버({url})가 실행 중인지 확인", file=sys.stderr)
        raise SystemExit(1)


# ── 구역 이름 → UUID 조회 (서버 /fields 호출) ────────────────────────────────
def resolve_field_id(host: str, name: str) -> str:
    fields = http_request("GET", f"{host}/fields")
    for f in fields:
        if f["name"].lower() == name.lower():
            return f["id"]
    available = ", ".join(sorted(f["name"] for f in fields))
    raise SystemExit(f"[오류] 구역 '{name}' 없음. 사용 가능: {available}")


# ── 단일 이미지 업로드 ────────────────────────────────────────────────────────
def upload_one(host: str, image_path: Path, field_id: str,
               disease: str = None, confidence: float = None) -> dict:
    if not image_path.exists():
        raise SystemExit(f"[오류] 이미지 파일 없음: {image_path}")

    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    files = {"file": (image_path.name, image_path.read_bytes(), mime)}
    fields = {
        "field_id": field_id,
        "disease_type": disease,
        "confidence": confidence,
    }
    body, ctype = encode_multipart(fields, files)
    return http_request("POST", f"{host}/analyze", body=body, content_type=ctype)


def print_result(image: Path, result: dict):
    mark = "[DISEASE]" if result["disease_type"] != "NORMAL" else "[OK]    "
    print(
        f"{mark} {image.name:30s} "
        f"-> {result['disease_type']:8s} "
        f"conf={result['confidence']:.2f} "
        f"status={result['field_status']:7s} "
        f"src={result['inference_source']:8s} "
        f"notif={'Y' if result['notification_sent'] else 'N'}"
    )


def main():
    p = argparse.ArgumentParser(description="Greenhouse 백엔드 테스트 업로더")
    p.add_argument("--host", default="http://localhost:8000",
                   help="서버 base URL (기본: http://localhost:8000)")
    p.add_argument("--field", required=True,
                   help="구역 이름 (a1, b2 등)")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--image", type=Path, help="업로드할 단일 이미지 경로")
    grp.add_argument("--batch", type=Path, help="이미지 폴더 (재귀적으로 .jpg/.png 업로드)")
    p.add_argument("--disease", help="앱 TFLite 결과 시뮬레이션 (예: BLIGHT)")
    p.add_argument("--confidence", type=float, help="앱 TFLite 신뢰도 (0.0~1.0)")
    args = p.parse_args()

    if (args.disease is None) != (args.confidence is None):
        p.error("--disease 와 --confidence 는 같이 사용해야 합니다.")

    field_id = resolve_field_id(args.host, args.field)
    print(f"[구역] {args.field} → {field_id}")

    if args.image:
        result = upload_one(args.host, args.image, field_id, args.disease, args.confidence)
        print_result(args.image, result)
        return

    # batch
    if not args.batch.is_dir():
        raise SystemExit(f"[오류] 폴더 없음: {args.batch}")
    images = sorted(
        p for p in args.batch.rglob("*")
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    if not images:
        raise SystemExit(f"[오류] {args.batch} 안에 이미지 없음")
    print(f"[배치] {len(images)}장 업로드 시작\n")
    for img in images:
        try:
            result = upload_one(args.host, img, field_id, args.disease, args.confidence)
            print_result(img, result)
        except urllib.error.HTTPError:
            continue


if __name__ == "__main__":
    main()
