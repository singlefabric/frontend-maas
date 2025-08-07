# -*- coding: utf-8 -*-
"""
常量类 / 常量
"""
from enum import Enum
from typing import TypeVar
from zoneinfo import ZoneInfo

from sqlmodel import SQLModel

ModelT = TypeVar("ModelT", bound=SQLModel)
DEF_TZ_INFO = ZoneInfo("Asia/Shanghai")

DEF_PAGE_SIZE = 20  # 默认分页大小
MAX_PAGE_SIZE = 1000
DEF_METRICS_POINTS = 250  # 指标默认时间区间点位数
API_KEY_PREFIX = 'Bearer '
METRICS_MAX_DAYS = 30

# queue
API_INVOKE_EVENT_QUEUE = 'api_invoke_event_queue'
API_ERROR_EVENT_QUEUE = 'api_error_event_queue'
SERVER_EVENT_QUEUE = 'server_event_queue'
API_CONSUME_GROUP = 'api_consume_group'

# redis key
TOKENS_FOR_BILL = 'tokens_for_bill'
WORDS_FOR_BILL = 'words_for_bill'
COUNTS_FOR_BILL = 'counts_for_bill'
SECONDS_FOR_BILL = 'seconds_for_bill'

LOCK_BILL = 'lock_bill'

# 文件上传接口，文件命名长度规定
MIN_FILENAME_LENGTH = 1
MAX_FILENAME_LENGTH = 200

# last time dic
LAST_TIME_DIC = {}


class LANGUAGE(str, Enum):
    auto = "auto"
    zh = "zh"
    en = "en"
    yue = "yue"
    ja = "ja"
    ko = "ko"
    nospeech = "nospeech"


class EmptyModel(SQLModel):
    ...


class ResourceModule(str, Enum):
    SECRET_KEY = "sk"
    MODEL = "md"
    CHANNEL = "ch"
    CHANNEL_TO_MODEL = "ctm"
    PRODUCT = "prd"
    PARAM = "prm"
    FILE = "file"


class UserPlat(str, Enum):
    """
    用户平台  云平台和ks平台
    """
    QC_CONSOLE = "qc_console"
    KS_CONSOLE = "ks_console"
    ALL = "qc_console,ks_console"


class DataOper(str, Enum):
    CREATE = "create"
    UPDATE = "update"


class EmptyData(Enum):
    PAGE = {"response": [], "total": 0}
    LIST = []
    DATA = None


class InferApiStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"


class InferApiHealth(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class TokenType(str, Enum):
    """
    token 计量类型
    """
    INPUT = 'input'
    OUTPUT = 'output'
    CACHED = 'cached'
    IN_OUT = 'io'


class ModelTag(str, Enum):
    """
    推理 api 类型
    """
    CHAT = 'chat'
    ASR = 'asr'
    TTS = 'tts'
    TXT2IMG = 'txt2img'
    IMG2TXT = 'img2txt'
    IMG2IMG = 'img2img'
    EMBEDDING = 'embedding'
    RERANKER = 'reranker'


class Switch(str, Enum):
    ON = 'True'
    OFF = 'False'


class ChannelStatus(str, Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DELETE = 'delete'


class ModelStatus(str, Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'


class ApiKeyStatus(str, Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DELETE = 'delete'


class FileStatus(str, Enum):
    ACTIVE = 'active'
    INACTIVE = 'expired'
    DELETE = 'deleted'


class MetricUnit(str, Enum):
    """
    计量单位
    """
    TOKEN = 'token'
    COUNT = 'count'
    SECONDS = 'seconds'
    WORDS = 'words'


class MetricsAggrType(str, Enum):
    """
    指标汇总方式
    """
    RANGE = 'range'
    SUM = 'sum'


class BillingRate(int, Enum):
    """
    费率
    """
    TOKEN = 1000
    WORDS = 1000
    COUNT = 1
    SECONDS = 1


class TTLTime(int, Enum):
    """
    内存缓存时间
    """
    PRODUCT = 60 * 10
    USER = 60 * 60
    BALANCE = 60 * 2
    APIKEY = 60 * 10
    MODEL_CHANNEL = 60 * 30
    MODEL_PARAM = 60 * 30


class EventAction(str, Enum):
    """
    服务事件动作
    """
    EVICT_CACHE = 'evict_cache'