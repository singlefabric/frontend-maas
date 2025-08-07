# -*- coding: utf-8 -*-

from pydantic.dataclasses import dataclass

from src.common.const.comm_const import ModelTag, TokenType, TOKENS_FOR_BILL, WORDS_FOR_BILL, SECONDS_FOR_BILL, \
    MetricUnit, BillingRate, COUNTS_FOR_BILL
from src.common.const.err_const import Err
from src.common.exceptions import MaaSBaseException


@dataclass
class BaseApiInvokeInfo:
    user_id: str  # 用户
    channel_id: str  # 渠道 id
    model: str  # 模型名称
    model_tag: ModelTag  # 推理 api 类型
    api_key: str  # 令牌
    date_time: str
    cost_time: float  # 耗时(秒)
    trace_id: str = ''
    cache_key: str = ''

    def token_type_mount(self):
        raise MaaSBaseException(Err.NOT_IMPLEMENT)


@dataclass
class ChatApiInvokeInfo(BaseApiInvokeInfo):
    cache_key: str = TOKENS_FOR_BILL
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    def token_type_mount(self) -> list[tuple[str, int, str]]:
        return [
            (TokenType.INPUT.value, self.prompt_tokens, MetricUnit.TOKEN.value),
            (TokenType.OUTPUT.value, self.completion_tokens, MetricUnit.TOKEN.value),
            (TokenType.CACHED.value, self.cached_tokens, MetricUnit.TOKEN.value),
        ]


@dataclass
class ASRApiInvokeInfo(BaseApiInvokeInfo):
    cache_key: str = SECONDS_FOR_BILL
    speech_length: int = 0

    def token_type_mount(self) -> list[tuple[str, int, str]]:
        return [
            (TokenType.INPUT.value, self.speech_length, MetricUnit.SECONDS.value),
        ]


@dataclass
class TTSApiInvokeInfo(BaseApiInvokeInfo):
    cache_key: str = WORDS_FOR_BILL
    words: int = 0

    def token_type_mount(self) -> list[tuple[str, int, str]]:
        return [
            (TokenType.INPUT.value, self.words, MetricUnit.WORDS.value),
        ]


@dataclass
class EmbeddingApiInvokeInfo(BaseApiInvokeInfo):
    cache_key: str = TOKENS_FOR_BILL
    total_tokens: int = 0

    def token_type_mount(self) -> list[tuple[str, int, str]]:
        return [
            (TokenType.INPUT.value, self.total_tokens, MetricUnit.TOKEN.value),
        ]


@dataclass
class RerankerApiInvokeInfo(BaseApiInvokeInfo):
    cache_key: str = TOKENS_FOR_BILL
    total_tokens: int = 0

    def token_type_mount(self) -> list[tuple[str, int, str]]:
        return [
            (TokenType.INPUT.value, self.total_tokens, MetricUnit.TOKEN.value),
        ]


@dataclass
class BillMetaInfo:
    cache_key: str
    rate: BillingRate
    unit: MetricUnit


class ApiInvokeInfoBuilder:

    BillMetaInfo = [
        BillMetaInfo(TOKENS_FOR_BILL, BillingRate.TOKEN, MetricUnit.TOKEN),
        BillMetaInfo(WORDS_FOR_BILL, BillingRate.WORDS, MetricUnit.WORDS),
        BillMetaInfo(COUNTS_FOR_BILL, BillingRate.COUNT, MetricUnit.COUNT),
        BillMetaInfo(SECONDS_FOR_BILL, BillingRate.SECONDS, MetricUnit.SECONDS),
    ]

    @staticmethod
    def build(data: dict) -> BaseApiInvokeInfo:
        model_tag = data.get('model_tag')
        if model_tag == ModelTag.CHAT.value:
            return ChatApiInvokeInfo(**data)
        if model_tag == ModelTag.ASR.value:
            return ASRApiInvokeInfo(**data)
        if model_tag == ModelTag.TTS.value:
            return TTSApiInvokeInfo(**data)
        if model_tag == ModelTag.EMBEDDING.value:
            return EmbeddingApiInvokeInfo(**data)
        if model_tag == ModelTag.RERANKER.value:
            return RerankerApiInvokeInfo(**data)
        raise MaaSBaseException(Err.NOT_SUPPORT, message=model_tag)
