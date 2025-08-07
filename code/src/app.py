# -*- coding: utf-8 -*-
import importlib
import asyncio
import os
import threading
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.apps.gateway.api_file import api_router as gateway_api_file_router
from src.apps.channel.api import api_channel_type_api_router as channel_type_api_router
from src.apps.channel.api import admin_channel_type_api_router as channel_type_admin_router
from src.apps.rate_limiter.limiter import limiter
from src.common.event_manage import event_manager
from src.common.exceptions import MaaSBaseException, GatewayException
from src.common.loggers import logger
from src.common.rsp_schema import R
from src.job.refresh_last_time_job import start as refresh_last_time_job_start
from src.middlewares.logger import LoggerMiddleware
from src.middlewares.user_loader import UserLoaderMiddleware
from src.setting import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get('ENV_CONF') != 'dev':
        # 启动定时任务作业
        asyncio.create_task(refresh_last_time_job_start())
        threading.Thread(target=event_manager.consume_event_msg, daemon=True).start()
    await limiter.refresh_all_limit()
    yield
    # 清理资源


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    docs_url=f"{settings.API_PREFIX}-docs",
    openapi_url=f"{settings.API_PREFIX}-openapi.json",
    redoc_url=None,
    lifespan=lifespan
)

# 中间件
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(LoggerMiddleware)
app.add_middleware(UserLoaderMiddleware)

cors_headers = {"access-control-allow-credentials": "true", "access-control-allow-origin": "*"}


def res_err(exc):
    base_rsp = R.err(exc)
    err_data = base_rsp.json(ensure_ascii=False)
    logger.warn(f'[SYS ERR]: {err_data}')
    return Response(err_data, media_type="application/json", headers=cors_headers, status_code=base_rsp.ret_code)


@app.exception_handler(MaaSBaseException)
async def http_exception_handler(request: Request, exc: Exception):
    return res_err(exc)


@app.exception_handler(GatewayException)
async def gateway_exception_handler(request: Request, exc: GatewayException):
    api_key = request.headers.get("Authorization", '')
    logger.warn(f'[API ERR][{api_key}]: {exc.code}: {exc.msg}')
    return JSONResponse({
        'object': 'error', 'message': exc.msg, 'code': exc.code
    }, headers=cors_headers, status_code=exc.code)


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger.error('捕获异常', exc_info=exc)
    return res_err(exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    if request.url.path.removeprefix(settings.API_PREFIX).startswith('/v1/'):
        return await gateway_exception_handler(request, GatewayException(f'参数校验失败: {exc.errors()}', HTTPStatus.UNPROCESSABLE_ENTITY))
    return res_err(exc)

app.include_router(gateway_api_file_router, prefix=settings.API_PREFIX)
app.include_router(channel_type_api_router, prefix=settings.API_PREFIX)
app.include_router(channel_type_admin_router, prefix=settings.API_PREFIX)

APP_PATH = os.path.join(os.path.dirname(__file__), "apps")
for app_name in os.listdir(APP_PATH):
    if os.path.isdir(os.path.join(APP_PATH, app_name)):
        try:
            if not os.path.exists(os.path.join(APP_PATH, app_name, "api.py")):
                continue

            api = importlib.import_module(f"src.apps.{app_name}.api")
            for name in ['api_router', 'admin_router']:
                if hasattr(api, name):
                    logger.info(f"import app.apps.{app_name}.{name} success")
                    app.include_router(getattr(api, name), prefix=settings.API_PREFIX)

        except Exception as e:
            raise e


