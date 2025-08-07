# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.apps.billing.curd import billing_curd
from src.apps.channel.curd import channel_curd
from src.global_server_job import global_task
from src.job.clean_files_job import clean_expired_files
from src.setting import settings


@global_task('全局定时任务')
def global_cron_job():
    # 创建一个新的事件循环，用来执行定时任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    scheduler = AsyncIOScheduler()

    # token 计费任务
    if settings.BILLING_ENABLE:
        scheduler.add_job(billing_curd.async_charge, 'interval', seconds=settings.BILLING_TASK_INTERVAL, next_run_time=datetime.now())

    scheduler.add_job(channel_curd.health_check, 'interval', seconds=settings.HEALTH_CHECK_INTERVAL, next_run_time=datetime.now())

    # 文件清理任务
    scheduler.add_job(clean_expired_files, CronTrigger.from_crontab(settings.FILE_CLEANUP_CRON))

    scheduler.start()

    if not asyncio.get_event_loop().is_running():
        asyncio.get_event_loop().run_forever()
