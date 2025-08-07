import logging

from src.common.context import Context
from src.setting import settings

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(process)d - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s(%(traceid)s)')


class TraceIDFilter(logging.Filter):
    def filter(self, record):
        record.traceid = Context.TRACE_ID.get() or 'no-trace'
        return True


console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 获取或创建一个日志记录器
logger = logging.getLogger("maas")
logger.setLevel(logging.getLevelName(settings.LOGGING_LEVEL))
logger.addHandler(console_handler)
logger.addFilter(TraceIDFilter("maas"))
