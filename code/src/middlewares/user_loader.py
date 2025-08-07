# -*- coding: utf-8 -*-
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.common.context import Context
from src.common.dto import KS_ADMIN_USER
from src.setting import settings
from src.system.interface import PI


class UserLoaderMiddleware(BaseHTTPMiddleware):
    """
    获取用户信息并设置到上下文中
    """

    async def dispatch(self, request: Request, call_next):

        # 网关路由跳过用户相关逻辑
        if request.url.path.startswith(f'{settings.API_PREFIX}/v1'):
            return await call_next(request)

        if os.getenv("ENV_CONF", None) == "dev":
            if request.url.path.startswith(f'{settings.API_PREFIX}/admin'):
                request.headers._list.append((b"x-remote-group", b"system:authenticated"))
                request.headers._list.append((b"x-remote-user", b"admin"))
            else:
                request.headers._list.append((b"aicp-userid", settings.mock_user_id.encode()))

        # console 端请求 header 中有 aicp-userid，即云平台账户
        # 管理端(KS) 请求 header 中有 X-Remote-Group 和 X-Remote-User
        if request.headers.get("X-Remote-Group") == "system:authenticated" and request.headers.get("X-Remote-User") == "admin":
            user = KS_ADMIN_USER
        else:
            user = PI.user_interface.get_user_by_id(request.headers.get("aicp-userid"))

        token = Context.USER.set(user)
        try:
            return await call_next(request)
        finally:
            Context.USER.reset(token)
