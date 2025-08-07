import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.common.context import Context
from src.common.loggers import logger
from src.common.utils.data import uuid


class LoggerMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        """
        Process request
        :param request:
        :param call_next:
        """
        start_time = time.time()
        trace_id = uuid(None)
        token = Context.TRACE_ID.set(trace_id)
        try:
            result = await call_next(request)
            result.headers.setdefault("trace-id", trace_id)
            return result
        finally:
            cost_time = time.time() - start_time
            req_info = f"[{Context.USER.get().user_id}][{request.method}][{request.url.path}]"
            logger.info(f"request: {req_info} ({cost_time: .2f}s)")
            Context.TRACE_ID.reset(token)
