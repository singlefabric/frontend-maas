# -*- coding: utf-8 -*-
import asyncio
import random
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.apps.apikey.curd import apikey_curd


async def start():
    scheduler = AsyncIOScheduler()
    start_time = datetime.now() + timedelta(seconds=random.randint(1, 60))
    scheduler.add_job(apikey_curd.save_last_time, 'interval', minutes=10, next_run_time=start_time)

    scheduler.start()
    # 使用 asyncio.Event().wait() 来避免阻塞
    stop_event = asyncio.Event()
    await stop_event.wait()
