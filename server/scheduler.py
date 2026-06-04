"""
매일 14:00 KST 자동 캡처 시뮬레이터.

실제 카메라가 연동되기 전까지 SCHEDULER_IMAGE_DIR 의 테스트 이미지를
각 구역마다 1장씩 무작위로 골라 /analyze 와 동일한 흐름을 수행한다.
"""
import logging
import os
import random
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from core.database import AsyncSessionLocal
from models.models import Field
from services.analysis_service import run_analysis

log = logging.getLogger("scheduler")

# 환경 변수
SCHEDULER_ENABLED  = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
SCHEDULE_HOUR      = int(os.getenv("SCHEDULE_HOUR", "14"))
SCHEDULE_MINUTE    = int(os.getenv("SCHEDULE_MINUTE", "0"))
SCHEDULE_TZ        = os.getenv("SCHEDULE_TZ", "Asia/Seoul")
SCHEDULER_IMAGE_DIR = Path(
    os.getenv("SCHEDULER_IMAGE_DIR", "../kaggle_dataset/test/test")
).resolve()

_scheduler: AsyncIOScheduler | None = None


def _pick_image_files() -> list[Path]:
    if not SCHEDULER_IMAGE_DIR.is_dir():
        return []
    return [
        p for p in SCHEDULER_IMAGE_DIR.rglob("*")
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ]


async def run_daily_capture() -> dict:
    """전 구역에 대해 테스트 이미지 1장씩 처리. 반환값은 manual trigger 응답용 요약."""
    images = _pick_image_files()
    if not images:
        log.warning(f"이미지 디렉토리 비어있음: {SCHEDULER_IMAGE_DIR}")
        return {"processed": 0, "reason": "no_images", "image_dir": str(SCHEDULER_IMAGE_DIR)}

    summary = {"processed": 0, "alerts": 0, "details": []}

    async with AsyncSessionLocal() as db:
        fields = (await db.execute(select(Field))).scalars().all()
        for field in fields:
            img_path = random.choice(images)
            try:
                outcome = await run_analysis(
                    db, field, img_path.read_bytes(), img_path.name,
                )
                summary["processed"] += 1
                if outcome.notification_sent:
                    summary["alerts"] += 1
                summary["details"].append({
                    "field": field.name,
                    "image": img_path.name,
                    "disease": outcome.result.disease_type,
                    "confidence": outcome.result.confidence,
                    "status": outcome.field_status,
                    "alert": outcome.notification_sent,
                })
                log.info(
                    f"[일일캡처] {field.name} ← {img_path.name} "
                    f"→ {outcome.result.disease_type} "
                    f"({outcome.result.confidence:.0%}) {outcome.field_status}"
                )
            except Exception as e:
                log.error(f"[일일캡처] {field.name} 실패: {e}")
                summary["details"].append({
                    "field": field.name, "error": str(e),
                })

    log.info(
        f"[일일캡처] 완료 — {summary['processed']}/{len(fields)} 구역, "
        f"질병 알림 {summary['alerts']}건"
    )
    return summary


def start(app_logger: logging.Logger | None = None) -> AsyncIOScheduler | None:
    global _scheduler
    if not SCHEDULER_ENABLED:
        (app_logger or log).info("스케줄러 비활성 (SCHEDULER_ENABLED=false)")
        return None

    _scheduler = AsyncIOScheduler(timezone=ZoneInfo(SCHEDULE_TZ))
    _scheduler.add_job(
        run_daily_capture,
        CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="daily_capture",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    (app_logger or log).info(
        f"스케줄러 활성: 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} "
        f"{SCHEDULE_TZ} · 이미지={SCHEDULER_IMAGE_DIR}"
    )
    return _scheduler


def shutdown() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
