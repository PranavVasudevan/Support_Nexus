from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from core.config import settings


def start_scheduler(classifier):
    scheduler = AsyncIOScheduler()

    async def nightly_retrain():
        logger.info("Nightly retrain job started")
        from services.trainer import retrain_model
        await retrain_model(classifier)

    scheduler.add_job(
        nightly_retrain,
        trigger="cron",
        hour=settings.retrain_schedule_hour,
        minute=0,
        id="nightly_retrain",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — retraining at {settings.retrain_schedule_hour}:00 UTC daily")
