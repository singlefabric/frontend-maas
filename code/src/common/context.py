# -*- coding: utf-8 -*-
import dataclasses
from contextvars import ContextVar
from typing import Optional

from sqlmodel import Session

from src.common.dto import EMPTY_USER, User


class Context:
    """
    协程变量封装
    """

    # 上下文中用户信息，生命周期为一个 http 请求
    USER: ContextVar[User] = ContextVar("user_info", default=EMPTY_USER)

    # 上下文中 session，生命周期为 session_manage 装饰器内部
    THREAD_SESSION: ContextVar[Optional[Session]] = ContextVar("thread_session", default=None)

    # 接口调用请求 trace_id
    TRACE_ID: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


@dataclasses.dataclass
class ChatUsage:
    prompt_tokens: int = 0
    total_tokens: int = 0
    completion_tokens: int = 0
