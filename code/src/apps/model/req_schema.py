# -*- coding: utf-8 -*-
from typing import Optional

from pydantic import Field

from src.apps.channel.req_schema import ChannelReq
from src.common.req_schema import BasePageReq, BaseReq


class ModelQueryReq(BasePageReq):
    key_words: Optional[str] = ''
    model_tag: Optional[str] = ''  # 查询标签，用逗号分隔


class ModelSaveReq(BaseReq):
    id: Optional[str]
    name: str = Field(..., min_length=2, max_length=32)
    icon: Optional[str] = Field('', max_length=10240)
    brief: Optional[str] = Field('', max_length=10240)
    developer: Optional[str] = Field('', max_length=32)
    maas_id_map: Optional[dict] = Field({})
    is_experience: Optional[int] = Field(0, ge=0, le=1)

    tag_ids: Optional[list[str]] = Field([], max_items=20)
    channels: list[ChannelReq] = []