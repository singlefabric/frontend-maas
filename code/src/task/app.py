# -*- coding: utf-8 -*-
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import generate_latest, REGISTRY

from src.common.event_manage import event_manager
from src.common.loggers import logger
from src.common.rsp_schema import R
from src.global_server_job import global_job


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get('ENV_CONF') != 'dev':
        # 消费api调用消息线程
        import src.task.api_consumer  # noqa
        # 定时任务（计费）
        import src.task.job  # noqa
        # 消费服务事件线程
        threading.Thread(target=event_manager.consume_event_msg, daemon=True).start()
    # 启动全局任务
    threading.Thread(target=global_job.start, args=('maas-task-server',), daemon=True).start()
    yield
    logger.info('清理资源')
    global_job.release()


app = FastAPI(lifespan=lifespan)


@app.get('/metrics')
async def metrics():
    return Response(generate_latest(REGISTRY), media_type="text/plain; version=0.0.4")


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return Response(R.err(exc).json(), media_type="application/json")
